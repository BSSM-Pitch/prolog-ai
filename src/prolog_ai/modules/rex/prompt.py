"""REX 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 원고에서 세계관 중심 규칙을 근거 문장과 함께 추출해줘."


def build_prompt(manuscript_text: str) -> str:
    return f"{PLACEHOLDER_PROMPT}\n\n{manuscript_text}"
