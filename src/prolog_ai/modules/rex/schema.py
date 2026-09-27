"""REX 모듈의 출력 스키마.

docs/specs/claude/api 명세/REX.md 2.1 RuleExtraction.extracted_rules를 따른다.
"""

from pydantic import BaseModel, Field


class ExtractedRule(BaseModel):
    description: str
    violation_keywords: list[str] = Field(default_factory=list)
    evidence: str
    # TODO: 이 함수는 원고 텍스트 조각 하나만 받으므로 어느 챕터에서 나온 규칙인지 알 수 없다.
    # 여러 챕터가 섞인 입력을 여러 번 호출하는 구조라면 호출자가 채워야 한다.
    source_chapter: int | None = None


class REXOutput(BaseModel):
    extracted_rules: list[ExtractedRule]
