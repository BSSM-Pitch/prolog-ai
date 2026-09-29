"""SCDS 모듈의 출력 스키마.

docs/specs/claude/api 명세/SCDS.md 2.7 Conflict를 따르되, check_id/status/created_at처럼
백엔드가 관리하는 리소스 필드는 제외하고 AI가 생성하는 필드만 담는다.

AI는 character_id와 conflict_target을 직접 쓰지 않고 룰 검출 후보의 번호(candidate_index)를 고른다.
문자열을 다시 쓰게 하면 한 글자만 달라도 후보와 대조할 수 없어 충돌이 버려지기 때문이다.
module.py가 번호로 후보를 찾아 SCDS 2.7 Conflict 필드(character_id, conflict_target)를 채운다.

TODO: related_chapter_ref(관련 설정이 정의된 챕터 참조)를 이 함수가 채울 수 있는 근거가
없어 필드 자체를 만들지 않았다. 필요하면 어떻게 계산할지 팀 확인 필요.
"""

from typing import Literal

from pydantic import BaseModel, Field, StrictInt


class ConflictAdvice(BaseModel):
    # true나 "0"이 후보 번호로 바뀌지 않도록 엄격한 정수만 받는다.
    candidate_index: StrictInt = Field(description="충돌로 판단한 룰 검출 후보의 번호 ([번호])")
    severity: Literal["low", "medium", "high"]
    advice: str


class SCDSOutput(BaseModel):
    conflicts: list[ConflictAdvice]
