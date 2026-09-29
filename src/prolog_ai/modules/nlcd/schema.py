"""NLCD 모듈의 출력 스키마.

docs/specs/claude/api 명세/NLCD.md 2.2, 2.3의 ExtractedItem/ExtractedInfluenceItem을 따른다.
항목이 없는 카테고리는 에러가 아니라 빈 배열이므로, 각 필드는 필수(빈 배열 허용)로 둔다.
필드 description은 LLM에 넘기는 도구 스키마에 들어간다(추출 기준은 prompt.py).

TODO: NLCD가 캐릭터 이름(character_name)도 추출해야 하는지 명세에 없어 확인 필요
(ASS 확정 시 character_name이 필수인데, NLCD 출력에는 이름 필드가 없음).
"""

from pydantic import BaseModel, Field

_EVIDENCE = "근거가 된 원문 구절. 원문에서 이어진 한 구간을 한 글자도 바꾸지 않고 그대로 복사"


class ExtractedItem(BaseModel):
    value: str = Field(description="짧은 명사구. 조사·어미 없이 한 가지 특성만 (예: 겁 많음, 가족 우선, 외로움)")
    evidence: str = Field(description=_EVIDENCE)


class ExtractedInfluenceItem(BaseModel):
    value: str = Field(description="영향을 준 대상의 이름만 (예: 할머니). 문장으로 쓰지 않는다")
    type: str | None = Field(default=None, description="관계 유형을 짧게 (예: 영향, 가르침)")
    evidence: str = Field(description=_EVIDENCE)


class NLCDOutput(BaseModel):
    personality_tags: list[ExtractedItem] = Field(description="성격 태그: 성격·기질·태도")
    core_values: list[ExtractedItem] = Field(
        description="핵심 가치: 중요하게 여기거나 지키려는 원칙, 피하려는 것 (예: 가족 우선, 거짓 회피)"
    )
    influence_relations: list[ExtractedInfluenceItem] = Field(
        description="영향 관계: 캐릭터에게 영향을 준 인물·존재"
    )
    emotion_keywords: list[ExtractedItem] = Field(
        description="감정 키워드: 느끼거나 드러내는 감정 이름만 (예: 외로움, 분노). 원칙·태도는 넣지 않는다"
    )
