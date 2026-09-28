"""SCDS 모듈의 공개 함수.

3단계에서 정한 경계대로, 룰 검출(rules.py)은 run_module 밖에서 먼저 실행한다.
검사가 생략되거나(skipped) 후보가 없으면(no_candidate) LLM을 부르지 않고
바로 반환한다. run_module 밖에서 나는 예상 못 한 예외는
명세의 RULE_ENGINE_ERROR로 반환한다.

characters는 ASS ConfirmedCharacter(ASS 2.4) 목록이며, 2단계 결정대로
core/mapping.py로 SCDS Character 필드(traits/values/influences)로 바꿔 쓴다.

응답은 SCDS 2.5 ConflictCheck와 같은 모양으로 맞춘다.
- 성공·건너뜀: data = {"status", "rule_result"} (+ 성공이면 "conflicts")
- AI 실패: error.details.rule_result에 룰 후보를 남긴다 (SCDS 4.7 "failed면 후보만 표시")
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.evidence import normalize
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.mapping import map_confirmed_character_to_scds
from prolog_ai.core.runner import make_status_response, run_module
from prolog_ai.core.status import RunStatus
from prolog_ai.modules.scds.prompt import build_prompt
from prolog_ai.modules.scds.rules import detect_conflict_candidates
from prolog_ai.modules.scds.schema import SCDSOutput


def _validate_inputs(event: Any, world_rules: Any, characters: Any) -> None:
    expect_type(event, dict, "event")
    expect_list_of(event.get("character_ids"), str, "event.character_ids")
    expect_text(event.get("content"), "event.content")

    expect_list_of(world_rules, dict, "world_rules")
    for index, rule in enumerate(world_rules):
        field = f"world_rules[{index}]"
        expect_type(rule.get("rule_id"), str, f"{field}.rule_id")
        expect_text(rule.get("description"), f"{field}.description")
        if rule.get("violation_keywords") is not None:
            expect_list_of(rule["violation_keywords"], str, f"{field}.violation_keywords")

    expect_list_of(characters, dict, "characters")
    for index, character in enumerate(characters):
        field = f"characters[{index}]"
        expect_type(character.get("character_id"), str, f"{field}.character_id")
        for key in ("personality_tags", "core_values", "emotion_keywords"):
            if character.get(key) is not None:
                expect_list_of(character[key], str, f"{field}.{key}")
        if character.get("influence_relations") is not None:
            relations = expect_list_of(character["influence_relations"], dict, f"{field}.influence_relations")
            for r_index, relation in enumerate(relations):
                expect_type(relation.get("target"), str, f"{field}.influence_relations[{r_index}].target")


def _character_settings(event: dict[str, Any], characters: list[dict[str, Any]]) -> list[dict]:
    """사건에 관련된 캐릭터만 골라 SCDS Character 필드로 바꾼다."""
    settings = []
    for character in characters:
        if character["character_id"] not in event["character_ids"]:
            continue
        mapped = map_confirmed_character_to_scds(character)
        settings.append(
            {
                "character_id": character["character_id"],
                "name": character.get("name"),
                "traits": mapped["traits"],
                "values": mapped["values"],
                "influences": mapped["influences"],
            }
        )
    return settings


def _keep_candidate_conflicts(conflicts: list[dict], candidates: list[dict]) -> list[dict]:
    """룰 후보에 있는 (캐릭터, 충돌 대상) 조합으로 만든 충돌만 남긴다."""
    allowed = {(c["character_id"], normalize(c["conflict_target"])) for c in candidates}
    return [c for c in conflicts if (c["character_id"], normalize(c["conflict_target"])) in allowed]


@public_api("scds", unexpected_code=ErrorCode.RULE_ENGINE_ERROR)
def run_scds(
    event: dict[str, Any],
    world_rules: list[dict[str, Any]],
    characters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    characters = [] if characters is None else characters
    _validate_inputs(event, world_rules, characters)

    character_settings = _character_settings(event, characters)
    rule_result = detect_conflict_candidates(event, world_rules, character_settings)

    if rule_result["skipped"]:
        return make_status_response(RunStatus.SKIPPED, {"rule_result": rule_result})
    if not rule_result["has_candidate"]:
        return make_status_response(RunStatus.NO_CANDIDATE, {"rule_result": rule_result})

    result = run_module(
        module="scds",
        input_data={
            "event": event,
            "character_settings": character_settings,
            "rule_result": rule_result,
        },
        validate=lambda data: data,
        build_prompt=build_prompt,
        output_schema=SCDSOutput,
    )

    if "error" in result:
        result["error"]["details"]["rule_result"] = rule_result
        return result

    conflicts = result["data"]["conflicts"]
    kept = _keep_candidate_conflicts(conflicts, rule_result["candidates"])
    return make_status_response(
        RunStatus.COMPLETED,
        {"rule_result": rule_result, "conflicts": kept},
        {"removed_conflict_count": len(conflicts) - len(kept)},
    )
