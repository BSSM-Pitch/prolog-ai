"""인물·어휘 검색과 근거 연결을 결합한다. 검색 누락을 작품 전체의 부재로 해석하지 않는다.

임베딩 서버 없이 동작하는 첫 구현이다. 큰 패턴은 지지와 반례 양쪽의 대표 근거를
선택하고 생략량을 표시한다. 시점 제한 뒤의 자료로 만든 가설은 과거에 유출하지 않는다.
"""

import math
import re
from collections import Counter

from prolog_ai.core.errors import make_success
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import InputValidationError
from prolog_ai.memory.module import observation_record
from prolog_ai.memory.source import encode, validate_memory


# 내용 검색과 출력 형식 지시를 분리한다. 원래 질문은 답변 생성기에 그대로 전달한다.
def content_query(query):
    lines = query.splitlines()
    kept = [
        line
        for line in lines
        if not re.match(
            r"^\s*(?:답변|응답|출력|answer|response)\s*(?:은|는|을|를|:|in\b|with\b)",
            line,
            re.IGNORECASE,
        )
    ]
    return "\n".join(kept).strip() or query


STOPWORDS = {
    "근거",
    "질문",
    "답변",
    "제공",
    "설명",
    "하라",
    "있는",
    "없는",
    "하는",
    "어떻게",
    "무엇",
    "인지",
    "판단",
    "각각",
    "구별",
    "추적",
    "확인",
}


def _terms(text):
    words = [w for w in re.findall(r"[\w]+", text.lower()) if w not in STOPWORDS]
    return (
        set(words)
        | {word[i : i + n] for word in words for n in (2, 3) for i in range(len(word) - n + 1)}
    ) - STOPWORDS


class LexicalIndex:
    """문서 빈도로 흔한 어휘를 낮추고 짧고 구체적인 근거를 우선하는 검색 점수."""

    def __init__(self, texts):
        self.documents = [_terms(t) for t in texts]
        counts = Counter(t for terms in self.documents for t in terms)
        self.idf = {t: math.log(1 + (len(texts) + 0.5) / (n + 0.5)) for t, n in counts.items()}
        self.average = sum(map(len, self.documents)) / max(1, len(texts))

    def score(self, query, text):
        terms = _terms(text)
        score = sum(
            self.idf.get(t, 0) * (0.65 if len(t) == 2 else 1) for t in _terms(query) & terms
        )
        return score / (0.6 + 0.4 * len(terms) / max(1, self.average))


def prepare_context(memory, query, character_ids=None, as_of_order=None, max_context_chars=16000):
    memory = validate_memory(memory, require_complete=True)
    expect_text(query, "query")
    expect_type(max_context_chars, int, "max_context_chars")
    if not 2000 <= max_context_chars <= 24000:
        raise InputValidationError("max_context_chars는 2000~24000이어야 합니다.")
    if as_of_order is not None:
        expect_type(as_of_order, int, "as_of_order")
        if as_of_order < 0:
            raise InputValidationError("as_of_order는 0 이상이어야 합니다.")
    known = {c.character_id for c in memory.characters}
    if character_ids is not None:
        expect_list_of(character_ids, str, "character_ids")
        if not set(character_ids) <= known:
            raise InputValidationError("기억에 없는 character_id입니다.")
        wanted = set(character_ids)
    else:
        wanted = {
            c.character_id
            for c in memory.characters
            if any(name in query for name in [c.name, *c.aliases])
        } or known
    scenes = {s.scene_id: s for s in memory.scenes if as_of_order is None or s.order <= as_of_order}
    eligible = {
        o.observation_id: o
        for o in memory.observations
        if o.evidence.scene_id in scenes
        and (o.character_id in wanted or (o.character_id is None and character_ids is None))
    }
    query = content_query(query)
    index = LexicalIndex(
        [o.evidence.quote + " " + o.summary + " " + o.context for o in eligible.values()]
    )

    def score(text):
        return index.score(query, text)

    def record(oid):
        o = eligible[oid]
        result = observation_record(o, scenes)
        e = o.evidence
        scene = scenes[e.scene_id]
        start, end = max(0, e.start - 120), min(len(scene.text), e.end + 120)
        result["source_context"] = {"start": start, "end": end, "text": scene.text[start:end]}
        return result

    result = {
        "project_id": memory.project_id,
        "snapshot_id": memory.snapshot_id,
        "mode": memory.mode,
        "retrieval_method": "idf+observation_first+character+evidence_links",
        "observations": [],
        "patterns": [],
        "hypotheses": [],
        "coverage": {
            "as_of_order": as_of_order,
            "character_ids": sorted(wanted),
            "explicit_character_filter": character_ids is not None,
            "source_scene_count": len(memory.scenes),
            "visible_scene_count": len(scenes),
            "eligible_observation_count": len(eligible),
            "returned_observation_count": 0,
            "omitted_pattern_count": 0,
            "sampled_pattern_count": 0,
            "exhaustive": False,
            "truncated": False,
        },
    }
    selected = set()
    # 마지막에 채우는 카운터의 자릿수가 늘어날 공간을 예약한다.
    limit = max_context_chars - 128
    patterns = sorted(
        [p for p in memory.patterns if p.character_id in wanted],
        key=lambda p: (-score(p.description + " " + p.condition), p.pattern_id),
    )
    hypotheses = {h.pattern_id: h for h in memory.hypotheses}

    def representatives(ids, count):
        # 같은 장면의 관찰만 반복되지 않도록 장면을 먼저 다양화하고 앞/뒤 시점을 보존한다.
        by_scene = {}
        for oid in ids:
            by_scene.setdefault(eligible[oid].evidence.scene_id, oid)
        distinct = list(by_scene.values())
        if len(distinct) <= count:
            return distinct
        return [distinct[round(i * (len(distinct) - 1) / (count - 1))] for i in range(count)]

    # 일회성 전환도 패턴보다 먼저 자리를 확보한다. 같은 장면 독점을 줄인다.
    remaining = sorted(
        eligible.values(),
        key=lambda o: (
            -score(o.evidence.quote + " " + o.summary + " " + o.context),
            scenes[o.evidence.scene_id].order,
            o.evidence.start,
            o.observation_id,
        ),
    )
    scene_counts = Counter()
    observation_scores = {
        o.observation_id: score(o.evidence.quote + " " + o.summary + " " + o.context)
        for o in remaining
    }
    for _ in range(min(24, len(remaining))):
        o = max(
            remaining,
            key=lambda o: (
                observation_scores[o.observation_id]
                / (1 + 0.35 * scene_counts[o.evidence.scene_id])
            ),
        )
        remaining.remove(o)
        candidate = {**result, "observations": result["observations"] + [record(o.observation_id)]}
        if len(encode(candidate)) <= limit * 0.5:
            result = candidate
            selected.add(o.observation_id)
            scene_counts[o.evidence.scene_id] += 1
        if len(selected) >= 12:
            break

    for p in patterns:
        if as_of_order is not None and p.analyzed_through_order > as_of_order:
            continue
        ids = p.supporting_observation_ids + p.counterexample_observation_ids
        # 미래의 지지/반례를 지우고 가설만 과거로 전달하면 스포일러가 생긴다.
        if not set(ids) <= eligible.keys():
            continue
        hypothesis = [hypotheses[p.pattern_id].model_dump()] if p.pattern_id in hypotheses else []
        variants = []
        if len(ids) <= 8:
            variants.append((p.supporting_observation_ids, p.counterexample_observation_ids))
        variants.extend(
            [
                (
                    representatives(p.supporting_observation_ids, 4),
                    representatives(p.counterexample_observation_ids, 2),
                ),
                (
                    representatives(p.supporting_observation_ids, 2),
                    representatives(p.counterexample_observation_ids, 2)[:1],
                ),
            ]
        )
        included = False
        for support, counter in variants:
            chosen_ids = support + counter
            sampled = len(chosen_ids) < len(ids)
            entry = {
                **p.model_dump(),
                "supporting_observation_ids": support,
                "counterexample_observation_ids": counter,
                "evidence_selection": {
                    "sampled": sampled,
                    "omitted_support_observation_count": len(p.supporting_observation_ids)
                    - len(support),
                    "omitted_counterexample_observation_count": len(
                        p.counterexample_observation_ids
                    )
                    - len(counter),
                    "method": "scene_and_reading_order" if sampled else "all",
                },
            }
            candidate = {
                **result,
                "observations": result["observations"]
                + [record(i) for i in chosen_ids if i not in selected],
                "patterns": result["patterns"] + [entry],
                "hypotheses": result["hypotheses"] + hypothesis,
            }
            if len(encode(candidate)) <= limit:
                result = candidate
                result["coverage"]["sampled_pattern_count"] += int(sampled)
                selected.update(chosen_ids)
                included = True
                break
        if not included:
            result["coverage"]["omitted_pattern_count"] += 1
    ranked = sorted(
        eligible.values(),
        key=lambda o: (
            -score(o.evidence.quote + " " + o.summary + " " + o.context),
            scenes[o.evidence.scene_id].order,
            o.evidence.start,
        ),
    )
    for o in ranked:
        if o.observation_id in selected:
            continue
        candidate = {**result, "observations": result["observations"] + [record(o.observation_id)]}
        if len(encode(candidate)) <= limit:
            result = candidate
            selected.add(o.observation_id)
    result["coverage"]["returned_observation_count"] = len(selected)
    result["coverage"]["truncated"] = (
        len(selected) < len(eligible)
        or result["coverage"]["omitted_pattern_count"] > 0
        or result["coverage"]["sampled_pattern_count"] > 0
    )
    return result


@public_api("memory")
def query_character_memory(
    memory: dict,
    query: str,
    character_ids: list[str] | None = None,
    *,
    as_of_order: int | None = None,
    max_context_chars: int = 16000,
) -> dict:
    """네트워크 호출 없이 근거가 포함된 제한 길이 문맥을 만든다. order는 독서 순서다."""
    return make_success(
        prepare_context(memory, query, character_ids, as_of_order, max_context_chars)
    )
