"""NLCD 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.guard import expect_text, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.nlcd.prompt import build_prompt
from prolog_ai.modules.nlcd.schema import NLCDOutput

EVIDENCE_FIELDS = ["personality_tags", "core_values", "influence_relations", "emotion_keywords"]


def _clean_items(items: list[dict]) -> list[dict]:
    """빈 value 항목을 버리고, 같은 카테고리 안의 중복 값은 처음 것만 남긴다.

    백엔드 character_attributes에 (character_id, category, lower(value)) 유니크 인덱스가 있어
    중복 값이 있으면 저장이 실패한다. 같은 기준(앞뒤 공백 제거, 대소문자 무시)으로 합친다.
    """
    seen: set[str] = set()
    kept = []
    for item in items:
        value = item["value"].strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        kept.append({**item, "value": value})
    return kept


@public_api("nlcd")
def run_nlcd(source_text: str) -> dict[str, Any]:
    result = run_module(
        module="nlcd",
        input_data=source_text,
        validate=lambda text: expect_text(text, "source_text"),
        build_prompt=build_prompt,
        output_schema=NLCDOutput,
        evidence_text=source_text,
        evidence_fields=EVIDENCE_FIELDS,
    )
    if "data" in result:
        for field in EVIDENCE_FIELDS:
            result["data"][field] = _clean_items(result["data"][field])
    return result
