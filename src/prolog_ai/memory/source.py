"""정확한 원문 좌표, 안정적인 ID, 입력/스냅샷 무결성 검증."""

import hashlib
import json
from collections import Counter

from pydantic import ValidationError

from prolog_ai.core.runner import InputValidationError
from prolog_ai.memory.schema import Memory


def encode(value) -> str:
    # 태그를 입력 자료로 사용할 때 자료가 태그를 닫지 못하게 한다.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def digest(value) -> str:
    return hashlib.sha256(encode(value).encode()).hexdigest()


def identity(prefix: str, value) -> str:
    return f"{prefix}_{digest(value)[:24]}"


def parse(model, value, field):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise InputValidationError(
            f"{field} 형식이 올바르지 않습니다.",
            {"field": field, "errors": exc.errors(include_url=False, include_input=False)},
        ) from exc


def unique(items, attribute: str):
    values = [getattr(item, attribute) for item in items]
    if len(set(values)) != len(values):
        raise InputValidationError(f"{attribute}가 중복되었습니다.", {"field": attribute})


def snapshot_id(project_id, characters, scenes):
    return identity(
        "memory",
        [project_id, [c.model_dump() for c in characters], [s.model_dump() for s in scenes]],
    )


def validate_memory(value, *, require_complete=False) -> Memory:
    memory = parse(Memory, value, "memory")
    for items, attr in [
        (memory.characters, "character_id"),
        (memory.scenes, "scene_id"),
        (memory.scenes, "order"),
        (memory.observations, "observation_id"),
        (memory.patterns, "pattern_id"),
        (memory.hypotheses, "hypothesis_id"),
        (memory.speaker_verifications, "observation_id"),
    ]:
        unique(items, attr)
    chars = {c.character_id for c in memory.characters}
    scenes = {s.scene_id: s for s in memory.scenes}
    observations = {o.observation_id: o for o in memory.observations}
    patterns = {p.pattern_id: p for p in memory.patterns}
    character_counts = Counter(
        o.character_id for o in memory.observations if o.attribution == "certain"
    )
    expected_id = snapshot_id(memory.project_id, memory.characters, memory.scenes)
    if memory.snapshot_id != expected_id:
        raise InputValidationError("memory의 원문/인물 목록과 snapshot_id가 맞지 않습니다.")
    processed = set(memory.processed_scene_ids)
    if len(processed) != len(memory.processed_scene_ids) or not processed <= scenes.keys():
        raise InputValidationError("처리한 장면 목록이 올바르지 않습니다.")
    if memory.complete and processed != scenes.keys():
        raise InputValidationError("완료된 기억에 미처리 장면이 있습니다.")
    if require_complete and not memory.complete:
        raise InputValidationError("미완료 기억입니다. checkpoint로 분석을 재개하세요.")
    for o in observations.values():
        e = o.evidence
        scene = scenes.get(e.scene_id)
        if (
            scene is None
            or e.scene_id not in processed
            or e.revision != scene.revision
            or not 0 <= e.start < e.end <= len(scene.text)
            or scene.text[e.start : e.end] != e.quote
            or (o.character_id is not None and o.character_id not in chars)
            or (o.attribution == "certain" and o.character_id is None)
            or not set(o.interlocutor_ids) <= chars
        ):
            raise InputValidationError("관찰의 원문 출처 또는 인물 참조가 올바르지 않습니다.")
    for check in memory.speaker_verifications:
        e = check.evidence
        scene = scenes.get(e.scene_id)
        o = observations.get(check.observation_id)
        if (
            o is None
            or o.kind != "speech"
            or e.scene_id != o.evidence.scene_id
            or scene is None
            or e.revision != scene.revision
            or not 0 <= e.start < e.end <= len(scene.text)
            or scene.text[e.start : e.end] != e.quote
            or (
                check.original_character_id is not None and check.original_character_id not in chars
            )
        ):
            raise InputValidationError("화자 검증의 원문 출처 또는 관찰 참조가 올바르지 않습니다.")
    if memory.speaker_verification_version == "v1" and (
        {v.observation_id for v in memory.speaker_verifications}
        != {o.observation_id for o in memory.observations if o.kind == "speech"}
    ):
        raise InputValidationError("화자 검증을 완료했다고 표시했지만 일부 대사가 빠졌습니다.")
    for p in patterns.values():
        support, counter = p.supporting_observation_ids, p.counterexample_observation_ids
        ids = support + counter
        if (
            p.character_id not in chars
            or len(ids) != len(set(ids))
            or any(
                i not in observations
                or observations[i].character_id != p.character_id
                or observations[i].attribution != "certain"
                for i in ids
            )
        ):
            raise InputValidationError("패턴의 관찰 참조가 올바르지 않습니다.")
        support_scenes = {observations[i].evidence.scene_id for i in support}
        counter_scenes = {observations[i].evidence.scene_id for i in counter}
        if (
            len(support_scenes) < 2
            or p.supporting_scene_count != len(support_scenes)
            or p.counterexample_scene_count != len(counter_scenes)
            or p.analyzed_through_order != max(s.order for s in memory.scenes)
            or p.status != ("contested" if counter else "recurring")
            or p.evaluated_observation_count != character_counts[p.character_id]
        ):
            raise InputValidationError("패턴의 근거 수/검토 범위가 올바르지 않습니다.")
    for h in memory.hypotheses:
        if h.pattern_id not in patterns or patterns[h.pattern_id].character_id != h.character_id:
            raise InputValidationError("가설의 패턴 참조가 올바르지 않습니다.")
    return memory


def chunks(text: str, size: int, overlap: int = 200):
    """원문을 손실 없이 덮는다. 겹침으로 경계 주변의 발화/행동을 다시 읽는다."""
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            newline = text.rfind("\n", start + size // 2, end)
            if newline >= 0:
                end = newline + 1
        yield start, text[start:end]
        if end == len(text):
            return
        start = end - min(overlap, (end - start) // 4)


def quote_start(text: str, quote: str, occurrence: int):
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(quote, start + 1)
        if start < 0:
            return None
    return start


def batches(items: list[dict], max_chars: int):
    batch, size = [], 2
    for item in items:
        length = len(encode(item)) + 1
        if length + 2 > max_chars:
            raise InputValidationError("한 항목이 분석 문맥 한도를 넘습니다.")
        if batch and size + length > max_chars:
            yield batch
            batch, size = [], 2
        batch.append(item)
        size += length
    if batch:
        yield batch
