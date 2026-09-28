"""AIQ 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.guard import expect_text, expect_type, public_api
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.modules.aiq.prompt import build_prompt
from prolog_ai.modules.aiq.schema import AIQOutput

SCOPES = ("whole", "selection")
# 답변은 긴 글이라 다른 모듈보다 오래 걸린다(실측 약 30초). 명세상 AIQ는 폴링(비동기)이라
# 시간 상한이 없으므로 기본값(30초)보다 넉넉하게 둔다. 재시도 포함 최악 약 4분 40초.
AIQ_TIMEOUT_SECONDS = 90.0


def _invalid_range(message: str, selection_range: Any) -> InputValidationError:
    return InputValidationError(
        message, {"selection_range": selection_range}, code=ErrorCode.INVALID_SELECTION_RANGE
    )


def _validate(data: dict) -> dict:
    expect_text(data["question"], "question")
    manuscript_text = expect_type(data["manuscript_text"], str, "manuscript_text")

    scope = data["scope"]
    if scope not in SCOPES:
        raise InputValidationError(
            "scope는 whole 또는 selection이어야 합니다.", {"field": "scope", "received": scope}
        )

    if scope == "selection":
        selection_range = data["selection_range"]
        if not isinstance(selection_range, dict):
            raise _invalid_range("scope=selection이지만 selection_range가 없습니다.", selection_range)
        start, end = selection_range.get("start"), selection_range.get("end")
        if any(not isinstance(v, int) or isinstance(v, bool) for v in (start, end)):
            raise _invalid_range("selection_range의 start, end는 정수여야 합니다.", selection_range)
        if not 0 <= start < end <= len(manuscript_text):
            raise _invalid_range("selection_range가 원고 범위를 벗어났습니다.", selection_range)

    return data


@public_api("aiq")
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
        timeout=AIQ_TIMEOUT_SECONDS,
    )
