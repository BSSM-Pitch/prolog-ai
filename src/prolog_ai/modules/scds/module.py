"""SCDS 모듈의 공개 함수.

3단계에서 정한 경계대로, 룰 검출(rules.py)은 run_module 밖에서 먼저 실행한다.
검사가 생략되거나(skipped) 후보가 없으면(no_candidate) LLM을 부르지 않고
make_skip_response()로 바로 반환한다. run_module 밖에서 나는 예상 못 한 예외는
명세의 RULE_ENGINE_ERROR로 반환한다.
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import make_skip_response, run_module
from prolog_ai.core.status import RunStatus
from prolog_ai.modules.scds.prompt import build_prompt
from prolog_ai.modules.scds.rules import detect_conflict_candidates
from prolog_ai.modules.scds.schema import SCDSOutput


def _validate_inputs(event: Any, world_rules: Any) -> None:
    expect_type(event, dict, "event")
    expect_list_of(event.get("character_ids"), str, "event.character_ids")
    expect_text(event.get("content"), "event.content")

    expect_list_of(world_rules, dict, "world_rules")
    for index, rule in enumerate(world_rules):
        keywords = rule.get("violation_keywords")
        if keywords is not None:
            expect_list_of(keywords, str, f"world_rules[{index}].violation_keywords")


@public_api("scds", unexpected_code=ErrorCode.RULE_ENGINE_ERROR)
def run_scds(event: dict[str, Any], world_rules: list[dict[str, Any]]) -> dict[str, Any]:
    _validate_inputs(event, world_rules)
    rule_result = detect_conflict_candidates(event, world_rules)

    if rule_result["skipped"]:
        return make_skip_response(RunStatus.SKIPPED, {"rule_result": rule_result})
    if not rule_result["has_candidate"]:
        return make_skip_response(RunStatus.NO_CANDIDATE, {"rule_result": rule_result})

    return run_module(
        module="scds",
        input_data={"event": event, "rule_result": rule_result},
        validate=lambda data: data,
        build_prompt=build_prompt,
        output_schema=SCDSOutput,
    )
