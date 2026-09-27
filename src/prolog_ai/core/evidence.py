"""근거 문장이 원문에 있는지 대조.

AI가 반환한 각 항목의 evidence가 입력 원문에 실제로 존재하는지 확인한다.
공백·줄바꿈·따옴표 종류 차이는 정규화 후 비교하며, 원문에 없는 근거를 가진
항목은 제거하고 몇 개를 제거했는지 반환한다(호출자가 meta에 기록).
"""

import re

_QUOTE_MAP = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
    }
)


def normalize(text: str) -> str:
    """공백·줄바꿈·따옴표 차이를 지운 비교용 문자열을 만든다."""
    text = text.translate(_QUOTE_MAP)
    return re.sub(r"\s+", "", text)


def is_present(evidence: str, source_text: str) -> bool:
    """evidence가 source_text 안에 (정규화 후) 실제로 존재하는지 확인한다."""
    if not evidence:
        return False
    return normalize(evidence) in normalize(source_text)


def filter_unverified(
    data: dict, source_text: str, evidence_fields: list[str]
) -> tuple[dict, int]:
    """evidence_fields로 지정된 리스트 필드에서, 원문에 없는 근거를 가진 항목을 제거한다.

    각 필드는 {"evidence": str, ...} 형태의 항목 딕셔너리 리스트여야 한다.
    반환값은 (필터링된 data 사본, 제거된 항목 총 개수)다.
    """
    result = dict(data)
    removed = 0

    for field in evidence_fields:
        items = result.get(field) or []
        kept = []
        for item in items:
            if is_present(item.get("evidence", ""), source_text):
                kept.append(item)
            else:
                removed += 1
        result[field] = kept

    return result, removed
