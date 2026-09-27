"""AIQ 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 원고(또는 선택 구간)를 참고해서 질문에 답해줘."


def build_prompt(data: dict) -> str:
    return f"{PLACEHOLDER_PROMPT}\n\n원고:\n{data['manuscript_text']}\n\n질문: {data['question']}"
