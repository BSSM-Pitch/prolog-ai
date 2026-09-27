"""AIQ 모듈의 출력 스키마.

docs/specs/claude/api 명세/AIQ.md 2.2 QAMessage.content를 따른다.

TODO: QAMessage에는 근거(evidence) 필드가 없어, 이 모듈은 근거 대조를 적용하지 않는다
(NLCD/REX와 달리 자유 형식 답변이라 원문 대조 대상이 명확하지 않음).
"""

from pydantic import BaseModel


class AIQOutput(BaseModel):
    content: str
