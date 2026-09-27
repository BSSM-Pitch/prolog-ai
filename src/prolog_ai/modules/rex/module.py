"""REX 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.modules.rex.prompt import build_prompt
from prolog_ai.modules.rex.schema import REXOutput


def _validate(manuscript_text: str) -> str:
    if not manuscript_text or not manuscript_text.strip():
        raise InputValidationError("manuscript_text가 비어 있습니다.", {"field": "manuscript_text"})
    return manuscript_text


def run_rex(manuscript_text: str) -> dict[str, Any]:
    return run_module(
        module="rex",
        input_data=manuscript_text,
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=REXOutput,
        evidence_text=manuscript_text,
        evidence_fields=["extracted_rules"],
    )
