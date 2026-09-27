"""AIQ 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.modules.aiq.prompt import build_prompt
from prolog_ai.modules.aiq.schema import AIQOutput


def _validate(data: dict) -> dict:
    question = data.get("question", "")
    if not question or not question.strip():
        raise InputValidationError("question이 비어 있습니다.", {"field": "question"})

    if data.get("scope") == "selection":
        selection_range = data.get("selection_range")
        if not selection_range or "start" not in selection_range or "end" not in selection_range:
            raise InputValidationError(
                "scope=selection이지만 selection_range가 없습니다.",
                {"field": "selection_range"},
                code=ErrorCode.INVALID_SELECTION_RANGE,
            )
        if selection_range["start"] >= selection_range["end"]:
            raise InputValidationError(
                "selection_range가 올바르지 않습니다.",
                {"selection_range": selection_range},
                code=ErrorCode.INVALID_SELECTION_RANGE,
            )

    return data


def run_aiq(
    question: str,
    manuscript_text: str,
    scope: str = "whole",
    selection_range: dict[str, int] | None = None,
) -> dict[str, Any]:
    return run_module(
        module="aiq",
        input_data={
            "question": question,
            "manuscript_text": manuscript_text,
            "scope": scope,
            "selection_range": selection_range,
        },
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=AIQOutput,
    )
