"""NLCD 모듈의 출력 스키마.

docs/specs/claude/api 명세/NLCD.md 2.2, 2.3의 ExtractedItem/ExtractedInfluenceItem을 따른다.
항목이 없는 카테고리는 에러가 아니라 빈 배열이므로, 각 필드는 필수(빈 배열 허용)로 둔다.

TODO: NLCD가 캐릭터 이름(character_name)도 추출해야 하는지 명세에 없어 확인 필요
(ASS 확정 시 character_name이 필수인데, NLCD 출력에는 이름 필드가 없음).
"""

from pydantic import BaseModel


class ExtractedItem(BaseModel):
    value: str
    evidence: str


class ExtractedInfluenceItem(BaseModel):
    value: str
    type: str | None = None
    evidence: str


class NLCDOutput(BaseModel):
    personality_tags: list[ExtractedItem]
    core_values: list[ExtractedItem]
    influence_relations: list[ExtractedInfluenceItem]
    emotion_keywords: list[ExtractedItem]
