"""SSM 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 원고(챕터)를 분석해 발단/전개/위기/절정/결말과 주요 사건을 정리해줘."


def build_prompt(chapter_text: str) -> str:
    return f"{PLACEHOLDER_PROMPT}\n\n{chapter_text}"
