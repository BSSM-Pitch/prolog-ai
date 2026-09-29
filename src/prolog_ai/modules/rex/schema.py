"""REX 모듈의 출력 스키마.

docs/specs/claude/api 명세/REX.md 2.1 RuleExtraction.extracted_rules를 따른다.
"""

from pydantic import BaseModel, Field

# DB authoring.world_rules.title은 varchar(200) NOT NULL이다(REX 2.1·2.2).
TITLE_MAX_LENGTH = 200


class ExtractedRule(BaseModel):
    title: str = Field(description=f"규칙을 짧게 부르는 제목 (최대 {TITLE_MAX_LENGTH}자)")
    description: str
    # SCDS 룰 검출(RULE-02)은 이 키워드로만 후보를 찾는다(SCDS 2.2). 비어 있으면 REX → SCDS가 끊기므로
    # 기본값 없이 필수로 둔다.
    violation_keywords: list[str] = Field(
        description="이 규칙을 어기는 사건 본문에 나올 만한 위반 키워드 목록 (SCDS RULE-02 판정에 사용)"
    )
    evidence: str
    # 이 함수는 원고 텍스트만 받아 챕터 번호를 알 수 없다. LLM이 넣은 값은 module.py가 null로 덮어쓴다
    # (WARN.md A6, T30). 챕터 목록 입력이 정해지면 채운다.
    source_chapter: int | None = None


class REXOutput(BaseModel):
    extracted_rules: list[ExtractedRule]
