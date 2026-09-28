"""SCDS 모듈의 공개 함수.

SCDS 4.6·4.7·5항 흐름대로 룰 검출과 AI 분석을 나눠 쓸 수 있게 공개 함수를 세 개 둔다.
- run_scds_rules: 룰 검출만 한다(LLM 호출 없음). 사건 저장 시 동기로 호출한다.
- run_scds_analysis: 룰 검출 결과(RuleResult)를 받아 AI 분석만 한다. 워커·재시도(4.8)에서 호출한다.
- run_scds: 위 둘을 차례로 한다. 후보가 없으면 LLM을 부르지 않는다.

3단계에서 정한 경계대로, 룰 검출(rules.py)은 run_module 밖에서 실행한다.
run_scds_rules·run_scds에서 run_module 밖의 예상 못 한 예외는 명세의 RULE_ENGINE_ERROR로 반환한다.

characters는 ASS ConfirmedCharacter(ASS 2.4) 목록이며, 2단계 결정대로
core/mapping.py로 SCDS Character 필드(traits/values/influences)로 바꿔 쓴다.

응답은 SCDS 2.5 ConflictCheck와 같은 모양으로 맞춘다.
- 룰 검출: data = {"status": skipped | no_candidate | queued, "rule_result"}
- AI 분석 성공: data = {"status": "completed", "rule_result", "conflicts"}
- AI 실패: error.details.rule_result에 룰 후보를 남긴다 (SCDS 4.7 "failed면 후보만 표시")
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.mapping import map_confirmed_character_to_scds
from prolog_ai.core.runner import InputValidationError, make_status_response, run_module
from prolog_ai.core.status import RunStatus
from prolog_ai.modules.scds.prompt import build_prompt
from prolog_ai.modules.scds.rules import detect_conflict_candidates
from prolog_ai.modules.scds.schema import SCDSOutput

# 조언 생성이 기본 제한(30초)을 넘는 경우가 있다(실측 약 32초). 명세상 AI 분석은 비동기(폴링)라
# 시간 상한이 없으므로 AIQ와 같이 넉넉하게 둔다. 재시도 포함 최악 약 4분 40초.
SCDS_TIMEOUT_SECONDS = 90.0


def _validate_event(event: Any) -> None:
    expect_type(event, dict, "event")
    expect_list_of(event.get("character_ids"), str, "event.character_ids")
    expect_text(event.get("content"), "event.content")


def _validate_world_rules(world_rules: Any) -> None:
    expect_list_of(world_rules, dict, "world_rules")
    for index, rule in enumerate(world_rules):
        field = f"world_rules[{index}]"
        expect_type(rule.get("rule_id"), str, f"{field}.rule_id")
        expect_text(rule.get("description"), f"{field}.description")
        if rule.get("violation_keywords") is not None:
            expect_list_of(rule["violation_keywords"], str, f"{field}.violation_keywords")


def _validate_characters(characters: Any) -> None:
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


def _validate_rule_result(rule_result: Any) -> None:
    """SCDS 2.6 RuleResult 형태인지 확인한다."""
    expect_type(rule_result, dict, "rule_result")
    expect_type(rule_result.get("has_candidate"), bool, "rule_result.has_candidate")
    expect_type(rule_result.get("skipped"), bool, "rule_result.skipped")
    if rule_result.get("skipped_reason") is not None:
        expect_type(rule_result["skipped_reason"], str, "rule_result.skipped_reason")
    candidates = expect_list_of(rule_result.get("candidates"), dict, "rule_result.candidates")
    for index, candidate in enumerate(candidates):
        field = f"rule_result.candidates[{index}]"
        expect_type(candidate.get("rule_id"), str, f"{field}.rule_id")
        expect_type(candidate.get("character_id"), str, f"{field}.character_id")
        expect_text(candidate.get("conflict_target"), f"{field}.conflict_target")
        expect_type(candidate.get("matched_keyword"), str, f"{field}.matched_keyword")
    if rule_result["has_candidate"] != bool(candidates):
        raise InputValidationError(
            "rule_result.has_candidate와 candidates가 맞지 않습니다.",
            {"field": "rule_result.has_candidate", "candidate_count": len(candidates)},
        )


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


def _conflicts_from_candidates(conflicts: list[dict], candidates: list[dict]) -> list[dict]:
    """AI가 고른 후보 번호로 SCDS 2.7 Conflict 필드를 채운다. 없는 번호를 가리키는 충돌은 버린다."""
    return [
        {
            "character_id": candidates[c["candidate_index"]]["character_id"],
            "conflict_target": candidates[c["candidate_index"]]["conflict_target"],
            "severity": c["severity"],
            "advice": c["advice"],
        }
        for c in conflicts
        if 0 <= c["candidate_index"] < len(candidates)
    ]


def _rule_status_response(rule_result: dict[str, Any]) -> dict[str, Any]:
    if rule_result["skipped"]:
        status = RunStatus.SKIPPED
    elif not rule_result["has_candidate"]:
        status = RunStatus.NO_CANDIDATE
    else:
        status = RunStatus.QUEUED
    return make_status_response(status, {"rule_result": rule_result})


def _analyze(
    event: dict[str, Any], rule_result: dict[str, Any], character_settings: list[dict]
) -> dict[str, Any]:
    """후보가 있는 rule_result로 AI 분석을 한다."""
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
        timeout=SCDS_TIMEOUT_SECONDS,
    )

    if "error" in result:
        result["error"]["details"]["rule_result"] = rule_result
        return result

    conflicts = result["data"]["conflicts"]
    kept = _conflicts_from_candidates(conflicts, rule_result["candidates"])
    return make_status_response(
        RunStatus.COMPLETED,
        {"rule_result": rule_result, "conflicts": kept},
        {"removed_conflict_count": len(conflicts) - len(kept)},
    )


@public_api("scds", unexpected_code=ErrorCode.RULE_ENGINE_ERROR)
def run_scds_rules(
    event: dict[str, Any],
    world_rules: list[dict[str, Any]],
    characters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """룰 검출만 한다(LLM 호출 없음). status가 queued면 run_scds_analysis로 AI 분석을 한다."""
    characters = [] if characters is None else characters
    _validate_event(event)
    _validate_world_rules(world_rules)
    _validate_characters(characters)

    rule_result = detect_conflict_candidates(event, world_rules, _character_settings(event, characters))
    return _rule_status_response(rule_result)


@public_api("scds")
def run_scds_analysis(
    event: dict[str, Any],
    rule_result: dict[str, Any],
    characters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """run_scds_rules가 돌려준 rule_result로 AI 분석만 한다. 재시도(SCDS 4.8)도 이 함수를 다시 부른다.

    후보가 없는 rule_result(skipped/no_candidate)를 받으면 LLM을 부르지 않고 그 상태를 그대로 돌려준다.
    """
    characters = [] if characters is None else characters
    _validate_event(event)
    _validate_rule_result(rule_result)
    _validate_characters(characters)

    if rule_result["skipped"] or not rule_result["has_candidate"]:
        return _rule_status_response(rule_result)
    return _analyze(event, rule_result, _character_settings(event, characters))


@public_api("scds", unexpected_code=ErrorCode.RULE_ENGINE_ERROR)
def run_scds(
    event: dict[str, Any],
    world_rules: list[dict[str, Any]],
    characters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """룰 검출과 AI 분석을 한 번에 한다. 후보가 없으면 LLM을 부르지 않는다."""
    characters = [] if characters is None else characters
    _validate_event(event)
    _validate_world_rules(world_rules)
    _validate_characters(characters)

    character_settings = _character_settings(event, characters)
    rule_result = detect_conflict_candidates(event, world_rules, character_settings)
    if rule_result["skipped"] or not rule_result["has_candidate"]:
        return _rule_status_response(rule_result)
    return _analyze(event, rule_result, character_settings)
