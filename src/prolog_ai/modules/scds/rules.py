"""룰 기반 충돌 후보 검출.

docs/specs/claude/api 명세/SCDS.md 2.6 RuleResult 형태로 검출 결과를 반환한다.
world_rules가 없으면(참조할 기존 설정 없음) 검사를 생략(skipped=True)한다.

TODO: RULE-01~04의 정확한 판정 기준은 원본 기능 명세서(SCDS 기능 명세서 v0.1)가 없어
확인되지 않았다(0단계 TODO#6). 여기서는 SCDS API 명세에 명시적으로 나온 한 가지 기준,
즉 WorldRule.violation_keywords(2.2, "RULE-02 판정에 사용되는 위반 키워드")가
사건 내용에 문자열로 등장하는지만 확인하는 최소 구현을 둔다. 캐릭터의 values를
직접 대조하는 판정(예시의 RULE-01)은 별도 키워드 사전이 필요해 구현하지 않았다.
"""

from typing import Any

from prolog_ai.core.status import SkippedReason


def detect_conflict_candidates(
    event: dict[str, Any], world_rules: list[dict[str, Any]]
) -> dict[str, Any]:
    """event={"character_ids": [...], "content": "..."}, world_rules=WorldRule 딕셔너리 목록."""
    if not world_rules:
        return {
            "has_candidate": False,
            "skipped": True,
            "skipped_reason": SkippedReason.NO_REFERENCE_DATA.value,
            "candidates": [],
        }

    content = event.get("content", "")
    candidates = [
        {
            "rule_id": rule.get("rule_id"),
            "character_id": character_id,
            "conflict_target": rule.get("description"),
            "matched_keyword": keyword,
        }
        for character_id in event.get("character_ids", [])
        for rule in world_rules
        for keyword in rule.get("violation_keywords") or []
        if keyword and keyword in content
    ]

    return {
        "has_candidate": bool(candidates),
        "skipped": False,
        "skipped_reason": None,
        "candidates": candidates,
    }
