"""NLCD 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.guard import expect_text, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.nlcd.prompt import build_prompt
from prolog_ai.modules.nlcd.schema import NLCDOutput

EVIDENCE_FIELDS = ["personality_tags", "core_values", "influence_relations", "emotion_keywords"]


@public_api("nlcd")
def run_nlcd(source_text: str) -> dict[str, Any]:
    return run_module(
        module="nlcd",
        input_data=source_text,
        validate=lambda text: expect_text(text, "source_text"),
        build_prompt=build_prompt,
        output_schema=NLCDOutput,
        evidence_text=source_text,
        evidence_fields=EVIDENCE_FIELDS,
    )
