"""REX 모듈의 출력 스키마.

docs/specs/claude/api 명세/REX.md 2.1 RuleExtraction.extracted_rules를 따른다.
"""

from pydantic import BaseModel, Field

# DB authoring.world_rules.title은 varchar(200) NOT NULL이다(REX 2.1·2.2).
TITLE_MAX_LENGTH = 200


class ExtractedRule(BaseModel):
    title: str = Field(description=f"규칙을 짧게 부르는 이름 (2~15자 권장, 최대 {TITLE_MAX_LENGTH}자)")
    description: str = Field(description="규칙을 한 문장의 제약으로 정리 (예: ~는 ~없이 ~할 수 없다)")
    # SCDS 룰 검출(RULE-02)은 이 키워드로만 후보를 찾는다(SCDS 2.2). 비어 있으면 REX → SCDS가 끊기므로
    # 기본값 없이 필수로 둔다.
    violation_keywords: list[str] = Field(
        description=(
            "위반 장면 문장에 나올 금지 조건 쪽 일상 표현, 1~2어절로 4~10개. 사건 본문에서 글자 그대로 "
            "찾는다. 행동과 묶지 말고, 동사는 어간까지만 (예: 허락 없이, 몰래 들어, 대낮)"
        )
    )
    evidence: str = Field(description="근거가 된 원문 구절. 이어진 한 구간을 한 글자도 바꾸지 않고 그대로 복사")
    # 이 함수는 원고 텍스트만 받아 챕터 번호를 알 수 없다. LLM이 넣은 값은 module.py가 null로 덮어쓴다
    # (WARN.md A6, T30). 챕터 목록 입력이 정해지면 채운다.
    source_chapter: int | None = Field(default=None, description="비워 둔다 (null)")


class REXOutput(BaseModel):
    extracted_rules: list[ExtractedRule]
