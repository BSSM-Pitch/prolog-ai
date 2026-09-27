"""NLCD 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 문장에서 성격 태그, 핵심 가치, 영향 관계, 감정 키워드를 근거 구절과 함께 추출해줘."


def build_prompt(source_text: str) -> str:
    return f"{PLACEHOLDER_PROMPT}\n\n{source_text}"
