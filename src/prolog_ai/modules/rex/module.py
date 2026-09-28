"""REX 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.guard import expect_text, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.rex.prompt import build_prompt
from prolog_ai.modules.rex.schema import REXOutput


@public_api("rex")
def run_rex(manuscript_text: str) -> dict[str, Any]:
    return run_module(
        module="rex",
        input_data=manuscript_text,
        validate=lambda text: expect_text(text, "manuscript_text"),
        build_prompt=build_prompt,
        output_schema=REXOutput,
        evidence_text=manuscript_text,
        evidence_fields=["extracted_rules"],
    )
