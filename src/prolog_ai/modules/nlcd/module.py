"""NLCD 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.modules.nlcd.prompt import build_prompt
from prolog_ai.modules.nlcd.schema import NLCDOutput

EVIDENCE_FIELDS = ["personality_tags", "core_values", "influence_relations", "emotion_keywords"]


def _validate(source_text: str) -> str:
    if not source_text or not source_text.strip():
        raise InputValidationError("source_text가 비어 있습니다.", {"field": "source_text"})
    return source_text


def run_nlcd(source_text: str) -> dict[str, Any]:
    return run_module(
        module="nlcd",
        input_data=source_text,
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=NLCDOutput,
        evidence_text=source_text,
        evidence_fields=EVIDENCE_FIELDS,
    )
