"""룰 기반 충돌 후보 검출.

docs/specs/claude/api 명세/SCDS.md 2.6 RuleResult 형태로 검출 결과를 반환한다.
세계관 규칙도, 사건 관련 캐릭터의 설정(traits/values/influences)도 없으면
참조할 기존 설정이 없는 것으로 보고 검사를 생략(skipped=True)한다.

TODO: RULE-01~04의 정확한 판정 기준은 원본 기능 명세서(SCDS 기능 명세서 v0.1)가 없어
확인되지 않았다(0단계 TODO#6). 여기서는 SCDS API 명세에 명시적으로 나온 한 가지 기준,
즉 WorldRule.violation_keywords(2.2, "RULE-02 판정에 사용되는 위반 키워드")가
사건 내용에 문자열로 등장하는지만 확인하는 최소 구현을 둔다. 캐릭터의 values를
직접 대조하는 판정(예시의 RULE-01)은 별도 키워드 사전이 필요해 구현하지 않았다.
"""

import re
from typing import Any

from prolog_ai.core.status import SkippedReason


def _normalize_spaces(text: str) -> str:
    """연속된 공백·줄바꿈을 한 칸으로 바꾼다. "잔혹하게  살해"도 "잔혹하게 살해"로 찾기 위해서다."""
    return re.sub(r"\s+", " ", text).strip()


def _first_matched_keyword(keywords: list[str], normalized_content: str) -> str | None:
    """사건 본문에 나오는 첫 키워드. 공백만 있는 키워드는 모든 본문에 걸리므로 무시한다."""
    for keyword in keywords:
        normalized = _normalize_spaces(keyword)
        if normalized and normalized in normalized_content:
            return keyword
    return None


def detect_conflict_candidates(
    event: dict[str, Any],
    world_rules: list[dict[str, Any]],
    character_settings: list[dict[str, Any]] = (),
) -> dict[str, Any]:
    """event={"character_ids": [...], "content": "..."}, world_rules=WorldRule 딕셔너리 목록,
    character_settings=사건 관련 캐릭터의 SCDS Character 필드(traits/values/influences) 목록.
    """
    has_character_settings = any(
        s.get("traits") or s.get("values") or s.get("influences") for s in character_settings
    )
    if not world_rules and not has_character_settings:
        return {
            "has_candidate": False,
            "skipped": True,
            "skipped_reason": SkippedReason.NO_REFERENCE_DATA.value,
            "candidates": [],
        }

    content = _normalize_spaces(event.get("content", ""))
    # 같은 (캐릭터, 규칙)은 키워드가 여러 개 걸려도 후보 하나로 합친다. 첫 번째로 걸린 키워드를 남긴다.
    candidates = []
    seen: set[tuple[str, str]] = set()
    for character_id in dict.fromkeys(event.get("character_ids", [])):
        for rule in world_rules:
            keyword = _first_matched_keyword(rule.get("violation_keywords") or [], content)
            key = (character_id, rule.get("rule_id"))
            if keyword is None or key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "character_id": character_id,
                    "conflict_target": rule.get("description"),
                    "matched_keyword": keyword,
                }
            )

    return {
        "has_candidate": bool(candidates),
        "skipped": False,
        "skipped_reason": None,
        "candidates": candidates,
    }
