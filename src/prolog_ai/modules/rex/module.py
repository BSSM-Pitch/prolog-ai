"""REX 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.guard import expect_text, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.rex.prompt import build_prompt
from prolog_ai.modules.rex.schema import REXOutput

# 원고 전체를 한 번에 넣어 기본 제한(30초)을 넘기기 쉽다. 명세상 REX는 비동기(폴링)라
# 시간 상한이 없으므로 AIQ·SCDS와 같이 둔다(WARN.md T35).
REX_TIMEOUT_SECONDS = 90.0


def clean_keywords(keywords: list[str]) -> list[str]:
    """앞뒤 공백을 지우고, 빈 키워드와 중복 키워드를 버린다."""
    cleaned: list[str] = []
    for keyword in keywords:
        keyword = keyword.strip()
        if keyword and keyword not in cleaned:
            cleaned.append(keyword)
    return cleaned


def _clean_rules(rules: list[dict]) -> list[dict]:
    """설명이 빈 규칙을 버리고, 키워드를 정리하고, 지어낸 source_chapter를 지운다."""
    return [
        {
            **rule,
            "description": rule["description"].strip(),
            "violation_keywords": clean_keywords(rule["violation_keywords"]),
            "source_chapter": None,
        }
        for rule in rules
        if rule["description"].strip()
    ]


@public_api("rex")
def run_rex(manuscript_text: str) -> dict[str, Any]:
    result = run_module(
        module="rex",
        input_data=manuscript_text,
        validate=lambda text: expect_text(text, "manuscript_text"),
        build_prompt=build_prompt,
        output_schema=REXOutput,
        evidence_text=manuscript_text,
        evidence_fields=["extracted_rules"],
        timeout=REX_TIMEOUT_SECONDS,
    )
    if "data" in result:
        result["data"]["extracted_rules"] = _clean_rules(result["data"]["extracted_rules"])
    return result
