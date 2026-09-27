"""SCDS 모듈의 공개 함수.

3단계에서 정한 경계대로, 룰 검출(rules.py)은 run_module 밖에서 먼저 실행한다.
검사가 생략되거나(skipped) 후보가 없으면(no_candidate) LLM을 부르지 않고
make_skip_response()로 바로 반환한다.
"""

from typing import Any

from prolog_ai.core.runner import InputValidationError, make_skip_response, run_module
from prolog_ai.core.status import RunStatus
from prolog_ai.modules.scds.prompt import build_prompt
from prolog_ai.modules.scds.rules import detect_conflict_candidates
from prolog_ai.modules.scds.schema import SCDSOutput


def _validate(data: dict) -> dict:
    if not data.get("event", {}).get("content"):
        raise InputValidationError("event.content가 비어 있습니다.", {"field": "event.content"})
    return data


def run_scds(event: dict[str, Any], world_rules: list[dict[str, Any]]) -> dict[str, Any]:
    rule_result = detect_conflict_candidates(event, world_rules)

    if rule_result["skipped"]:
        return make_skip_response(RunStatus.SKIPPED, {"rule_result": rule_result})
    if not rule_result["has_candidate"]:
        return make_skip_response(RunStatus.NO_CANDIDATE, {"rule_result": rule_result})

    return run_module(
        module="scds",
        input_data={"event": event, "rule_result": rule_result},
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=SCDSOutput,
    )
