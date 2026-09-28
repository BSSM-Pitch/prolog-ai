"""SCDS 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 충돌 후보가 캐릭터 설정과 실제로 충돌하는지 분석하고 조언을 만들어줘."
CANDIDATE_INSTRUCTION = "충돌마다 candidate_index에 아래 후보 번호를 적어줘."


def build_prompt(data: dict) -> str:
    candidates = "\n".join(
        f"[{index}] 캐릭터: {c['character_id']} / 충돌 대상: {c['conflict_target']}"
        f" / 일치 키워드: {c['matched_keyword']}"
        for index, c in enumerate(data["rule_result"]["candidates"])
    )
    return (
        f"{PLACEHOLDER_PROMPT}\n{CANDIDATE_INSTRUCTION}\n\n"
        f"사건: {data['event']}\n"
        f"캐릭터 설정: {data['character_settings']}\n"
        f"룰 검출 후보:\n{candidates}"
    )
