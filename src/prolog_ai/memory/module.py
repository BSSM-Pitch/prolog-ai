"""전체 장면 관찰 → 인물별 후보 발견 → 전 관찰에서 지지/반례 재검토.

프롬프트는 크기가 제한된 묶음으로 만들고, 완료한 요청을 캐시하여 수정/실패 후
재실행한다. 원문 전체를 축약해 덮어쓰지 않는다. 저장은 호출자가 맡는다.
"""

import os
from collections import Counter

from prolog_ai.core.errors import ErrorCode, make_error, make_success
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.llm import MAX_OUTPUT_TOKENS, LLMFailedError, get_llm_config
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.memory import prompt
from prolog_ai.memory.schema import (
    AssessmentOutput,
    Character,
    DiscoveryOutput,
    Evidence,
    ExtractionOutput,
    Hypothesis,
    Memory,
    Observation,
    Pattern,
    Scene,
)
from prolog_ai.memory.source import (
    batches,
    chunks,
    digest,
    identity,
    parse,
    quote_start,
    snapshot_id,
    unique,
    validate_memory,
)
from prolog_ai.memory.speakers import verify_speakers

# 추출 캐시의 네임스페이스. 단계별 프롬프트/출력 스키마/입력 전체가 캐시 키에
# 포함되므로 새 화자 검증 단계는 기존 추출만 재사용하고 검증을 건너뛰지 않는다.
PIPELINE_VERSION = "character-memory-v2-behavior"
MAX_PROMPT_CHARS = 32000


class AnalysisStopped(Exception):
    def __init__(self, result):
        self.result = result


class Session:
    def __init__(self, memory, max_calls):
        self.memory = memory
        self.max_calls = max_calls
        self.used_keys = set()
        self.meta = {
            "llm_calls": 0,
            "cache_hits": 0,
            "removed_observations": 0,
            "removed_proposals": 0,
            "verified_speakers": 0,
            "corrected_speakers": 0,
            "adjudicated_speakers": 0,
        }

    def fail(self, message, **details):
        if details.get("internal_code") == "INVALID_REFERENCE":
            self.memory.call_cache.pop(self.last_key, None)
        raise AnalysisStopped(make_error(ErrorCode.AI_ANALYSIS_FAILED, message, details))

    def call(self, schema, instruction, data, stage):
        built = prompt.build(instruction, data)
        if len(built) > MAX_PROMPT_CHARS:
            self.fail(
                "요청 문맥 한도를 넘었습니다. 인물 목록/묶음 크기를 줄이세요.",
                stage=stage,
                internal_code="CONTEXT_BUDGET_EXCEEDED",
            )
        key = digest([self.memory.analysis_key, schema.model_json_schema(), built])
        self.last_key = key
        self.used_keys.add(key)
        if key in self.memory.call_cache:
            # 캐시에도 현재 스키마 검증을 적용한다.
            cached = parse(schema, self.memory.call_cache[key], "call_cache")
            self.meta["cache_hits"] += 1
            return cached
        if self.meta["llm_calls"] >= self.max_calls:
            self.fail(
                "이번 실행의 호출 예산을 사용했습니다. checkpoint로 재개하세요.",
                stage=stage,
                internal_code="CALL_BUDGET_EXCEEDED",
            )
        self.meta["llm_calls"] += 1
        result = run_module(
            module="memory",
            input_data=data,
            validate=lambda x: x,
            build_prompt=lambda _: built,
            output_schema=schema,
            timeout=180.0,
            max_retries=1,
        )
        if "error" in result:
            result["error"]["details"]["stage"] = stage
            raise AnalysisStopped(result)
        self.memory.call_cache[key] = result["data"]
        return schema.model_validate(result["data"])


def _extract(session, chunk_chars):
    memory = session.memory
    known = {c.character_id for c in memory.characters}
    roster = [c.model_dump() for c in memory.characters]
    seen = set()
    for scene in memory.scenes:
        source_key = digest([memory.project_id, scene.model_dump()])
        for offset, text in chunks(scene.text, chunk_chars):
            output = session.call(
                ExtractionOutput,
                prompt.EXTRACT,
                {
                    "characters": roster,
                    "scene": scene.model_dump(exclude={"text"}),
                    "chunk_start": offset,
                    "text": text,
                },
                f"extract:{scene.scene_id}:{offset}",
            )
            for draft in output.observations:
                local = quote_start(text, draft.quote, draft.occurrence)
                if (
                    local is None
                    or not draft.quote.strip()
                    or (draft.character_id is not None and draft.character_id not in known)
                    or (draft.attribution == "certain" and draft.character_id is None)
                    or not set(draft.interlocutor_ids) <= known
                ):
                    session.meta["removed_observations"] += 1
                    continue
                start = offset + local
                evidence = Evidence(
                    scene_id=scene.scene_id,
                    revision=scene.revision,
                    start=start,
                    end=start + len(draft.quote),
                    quote=draft.quote,
                )
                oid = identity(
                    "obs",
                    [
                        source_key,
                        start,
                        evidence.end,
                        draft.character_id,
                        draft.kind,
                        draft.presentation,
                        draft.behavior_role,
                    ],
                )
                if oid in seen:
                    continue
                seen.add(oid)
                memory.observations.append(
                    Observation(
                        **draft.model_dump(exclude={"quote", "occurrence"}),
                        observation_id=oid,
                        evidence=evidence,
                    )
                )
        memory.processed_scene_ids.append(scene.scene_id)


def observation_record(observation, scenes):
    record = observation.model_dump()
    scene = scenes[observation.evidence.scene_id]
    record["scene_order"] = scene.order
    record["story_time"] = scene.story_time
    return record


def _discover(session, character, records, speech_baseline, batch_chars):
    proposals, seen = [], set()
    for index, batch in enumerate(batches(records, batch_chars)):
        ids = {r["observation_id"] for r in batch}
        output = session.call(
            DiscoveryOutput,
            prompt.DISCOVER,
            {
                "character": character.model_dump(),
                "observations": batch,
                "speech_baseline": [
                    speech_baseline[i] for i in sorted(ids) if i in speech_baseline
                ],
            },
            f"discover:{character.character_id}:{index}",
        )
        for p in output.proposals:
            if not set(p.seed_observation_ids) <= ids:
                session.meta["removed_proposals"] += 1
                continue
            key = ("".join(p.description.split()), "".join(p.condition.split()))
            if key not in seen:
                seen.add(key)
                proposals.append(p)
    return proposals


def _analyze_character(session, character, observations, scenes, baseline, batch_chars):
    if len({o.evidence.scene_id for o in observations}) < 2:
        return  # 단일 장면의 디테일은 관찰로 보존하지만 반복 패턴으로 승격하지 않는다.
    records = [observation_record(o, scenes) for o in observations]
    proposals = _discover(session, character, records, baseline, batch_chars)
    assessments = [{"support": set(), "counter": set()} for _ in proposals]
    numbered = [
        {"proposal_index": i, "description": p.description, "condition": p.condition}
        for i, p in enumerate(proposals)
    ]
    for group in batches(numbered, 5000):
        indexes = {p["proposal_index"] for p in group}
        for index, batch in enumerate(batches(records, batch_chars)):
            allowed = {r["observation_id"] for r in batch}
            output = session.call(
                AssessmentOutput,
                prompt.ASSESS,
                {
                    "character": character.model_dump(),
                    "proposals": group,
                    "observations": batch,
                },
                f"assess:{character.character_id}:{group[0]['proposal_index']}:{index}",
            )
            returned = [a.proposal_index for a in output.assessments]
            if set(returned) != indexes or len(returned) != len(indexes):
                session.fail(
                    "패턴 재검토 응답에 누락/중복 후보가 있습니다.",
                    stage="assess",
                    internal_code="INVALID_REFERENCE",
                )
            for a in output.assessments:
                support, counter = (
                    set(a.supporting_observation_ids),
                    set(a.counterexample_observation_ids),
                )
                if not (support | counter) <= allowed or support & counter:
                    session.fail(
                        "패턴 재검토의 근거 참조가 올바르지 않습니다.",
                        stage="assess",
                        internal_code="INVALID_REFERENCE",
                    )
                assessments[a.proposal_index]["support"].update(support)
                assessments[a.proposal_index]["counter"].update(counter)

    by_id = {o.observation_id: o for o in observations}
    position = {o.observation_id: i for i, o in enumerate(observations)}
    for proposal, assessment in zip(proposals, assessments, strict=True):
        support = sorted(assessment["support"], key=position.get)
        counter = sorted(assessment["counter"], key=position.get)
        supporting_scenes = {by_id[i].evidence.scene_id for i in support}
        if len(supporting_scenes) < 2:
            continue
        pid = identity(
            "pattern",
            [character.character_id, proposal.description, proposal.condition, support, counter],
        )
        session.memory.patterns.append(
            Pattern(
                pattern_id=pid,
                character_id=character.character_id,
                description=proposal.description,
                condition=proposal.condition,
                supporting_observation_ids=support,
                counterexample_observation_ids=counter,
                supporting_scene_count=len(supporting_scenes),
                counterexample_scene_count=len({by_id[i].evidence.scene_id for i in counter}),
                evaluated_observation_count=len(observations),
                analyzed_through_order=max(s.order for s in session.memory.scenes),
                status="contested" if counter else "recurring",
            )
        )
        if proposal.hypothesis:
            session.memory.hypotheses.append(
                Hypothesis(
                    hypothesis_id=identity("hypothesis", [pid, proposal.hypothesis]),
                    character_id=character.character_id,
                    pattern_id=pid,
                    statement=proposal.hypothesis,
                    alternatives=proposal.alternatives,
                )
            )


def _synthesize(session, batch_chars):
    memory = session.memory
    scenes = {s.scene_id: s for s in memory.scenes}
    memory.observations.sort(
        key=lambda o: (scenes[o.evidence.scene_id].order, o.evidence.start, o.observation_id)
    )
    by_character = {c.character_id: [] for c in memory.characters}
    total_speech, character_speech = Counter(), Counter()
    for o in memory.observations:
        if o.attribution == "certain":
            by_character[o.character_id].append(o)
            if o.kind == "speech":
                quote = "".join(o.evidence.quote.split())
                total_speech[quote] += 1
                character_speech[(o.character_id, quote)] += 1
    baseline = {}
    for o in memory.observations:
        if o.kind == "speech" and o.attribution == "certain":
            quote = "".join(o.evidence.quote.split())
            count = character_speech[(o.character_id, quote)]
            baseline[o.observation_id] = {
                "observation_id": o.observation_id,
                "same_quote_character_count": count,
                "same_quote_other_characters_count": total_speech[quote] - count,
            }
    for c in memory.characters:
        _analyze_character(session, c, by_character[c.character_id], scenes, baseline, batch_chars)


@public_api("memory")
def run_character_memory(
    project_id: str,
    scenes: list[dict],
    characters: list[dict],
    previous_memory: dict | None = None,
    *,
    chunk_chars: int = 6000,
    batch_chars: int = 12000,
    max_llm_calls: int = 200,
) -> dict:
    """scenes는 현행 원고의 모든 장면이다. 생략한 장면은 삭제한 것으로 처리한다.

    scene_id/revision/order/text는 필수. 실패 시 details.checkpoint를 previous_memory로 넘겨 재개한다.
    호출 예산은 논리적 요청 수(SDK 재시도 별도)이며 캐시 적중은 세지 않는다.
    """
    expect_text(project_id, "project_id")
    if len(project_id.strip()) > 200:
        raise InputValidationError("project_id는 200자 이하여야 합니다.")
    expect_list_of(scenes, dict, "scenes")
    expect_list_of(characters, dict, "characters")
    for name, value, lower, upper in [
        ("chunk_chars", chunk_chars, 1000, 8000),
        ("batch_chars", batch_chars, 4000, 16000),
        ("max_llm_calls", max_llm_calls, 1, 10000),
    ]:
        expect_type(value, int, name)
        if not lower <= value <= upper:
            raise InputValidationError(f"{name}는 {lower}~{upper}여야 합니다.")
    roster = sorted(
        [parse(Character, c, "characters") for c in characters], key=lambda c: c.character_id
    )
    sources = sorted([parse(Scene, s, "scenes") for s in scenes], key=lambda s: s.order)
    unique(roster, "character_id")
    unique(sources, "scene_id")
    unique(sources, "order")
    if sources and not roster:
        raise InputValidationError("원고를 분석하려면 인물 목록이 필요합니다.")
    try:
        config = get_llm_config()
    except LLMFailedError as exc:
        return make_error(ErrorCode.AI_ANALYSIS_FAILED, str(exc))
    analysis_key = digest(
        [
            PIPELINE_VERSION,
            config.provider,
            config.base_url,
            config.model,
            config.temperature,
            config.top_p,
            config.reasoning_effort,
            MAX_OUTPUT_TOKENS,
            os.environ.get("USE_FAKE_LLM") == "1",
            chunk_chars,
            batch_chars,
        ]
    )
    previous = None if previous_memory is None else validate_memory(previous_memory)
    if previous is not None and previous.project_id != project_id.strip():
        raise InputValidationError("다른 프로젝트의 기억을 재사용할 수 없습니다.")
    memory = Memory(
        project_id=project_id.strip(),
        characters=roster,
        scenes=sources,
        snapshot_id=snapshot_id(project_id.strip(), roster, sources),
        analysis_key=analysis_key,
        model=config.model,
        mode="fake" if os.environ.get("USE_FAKE_LLM") == "1" else "real",
        call_cache=dict(previous.call_cache)
        if previous and previous.analysis_key == analysis_key
        else {},
    )
    session = Session(memory, max_llm_calls)
    try:
        _extract(session, chunk_chars)
        verify_speakers(session)
        _synthesize(session, batch_chars)
    except AnalysisStopped as exc:
        # 실패 중인 장면에서 얻은 부분 관찰은 출처 검증이 가능한 완료 장면까지만 보존.
        processed = set(memory.processed_scene_ids)
        memory.observations = [o for o in memory.observations if o.evidence.scene_id in processed]
        exc.result["error"]["details"]["checkpoint"] = memory.model_dump()
        exc.result["error"]["details"]["progress"] = session.meta
        return exc.result
    memory.complete = True
    memory.call_cache = {k: v for k, v in memory.call_cache.items() if k in session.used_keys}
    validate_memory(memory.model_dump(), require_complete=True)
    return make_success(memory.model_dump(), session.meta)
