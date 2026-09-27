"""SCDS 모듈의 출력 스키마.

docs/specs/claude/api 명세/SCDS.md 2.7 Conflict를 따르되, check_id/status/created_at처럼
백엔드가 관리하는 리소스 필드는 제외하고 AI가 생성하는 필드만 담는다.

TODO: related_chapter_ref(관련 설정이 정의된 챕터 참조)를 이 함수가 채울 수 있는 근거가
없어 필드 자체를 만들지 않았다. 필요하면 어떻게 계산할지 팀 확인 필요.
"""

from typing import Literal

from pydantic import BaseModel


class ConflictAdvice(BaseModel):
    character_id: str
    conflict_target: str
    severity: Literal["low", "medium", "high"]
    advice: str


class SCDSOutput(BaseModel):
    conflicts: list[ConflictAdvice]
