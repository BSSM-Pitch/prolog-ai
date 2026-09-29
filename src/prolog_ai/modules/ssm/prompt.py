"""SSM 모듈의 프롬프트."""

PLACEHOLDER_PROMPT = "다음 원고(챕터)를 분석해 발단/전개/위기/절정/결말과 주요 사건을 정리해줘."
CHARACTER_INSTRUCTION = "노드의 character_ids에는 아래 캐릭터 목록의 ID만 적어줘."


def build_prompt(data: dict) -> str:
    prompt = PLACEHOLDER_PROMPT
    if data["characters"]:
        roster = "\n".join(f"- {c['character_id']}: {c['name']}" for c in data["characters"])
        prompt += f"\n{CHARACTER_INSTRUCTION}\n{roster}"
    return f"{prompt}\n\n{data['chapter_text']}"
