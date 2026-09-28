"""SCDS 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 충돌 후보가 캐릭터 설정과 실제로 충돌하는지 분석하고 조언을 만들어줘."


def build_prompt(data: dict) -> str:
    return (
        f"{PLACEHOLDER_PROMPT}\n\n"
        f"사건: {data['event']}\n"
        f"캐릭터 설정: {data['character_settings']}\n"
        f"룰 검출 후보: {data['rule_result']}"
    )
