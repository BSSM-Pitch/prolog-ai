"""AIQ 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.modules.aiq.prompt import build_prompt
from prolog_ai.modules.aiq.schema import AIQOutput

SCOPES = ("whole", "selection")
# AIQ 2.2 QAMessage.role
MESSAGE_ROLES = ("user", "assistant")
# 답변은 긴 글이라 다른 모듈보다 오래 걸린다(실측 약 30초). 명세상 AIQ는 폴링(비동기)이라
# 시간 상한이 없으므로 기본값(30초)보다 넉넉하게 둔다. 재시도 포함 최악 약 4분 40초.
AIQ_TIMEOUT_SECONDS = 90.0


def _invalid_range(message: str, selection_range: Any) -> InputValidationError:
    return InputValidationError(
        message, {"selection_range": selection_range}, code=ErrorCode.INVALID_SELECTION_RANGE
    )


def _validate(data: dict) -> dict:
    expect_text(data["question"], "question")
    manuscript_text = expect_type(data["manuscript_text"], str, "manuscript_text")

    scope = data["scope"]
    if scope not in SCOPES:
        raise InputValidationError(
            "scope는 whole 또는 selection이어야 합니다.", {"field": "scope", "received": scope}
        )

    if scope == "selection":
        selection_range = data["selection_range"]
        if not isinstance(selection_range, dict):
            raise _invalid_range("scope=selection이지만 selection_range가 없습니다.", selection_range)
        start, end = selection_range.get("start"), selection_range.get("end")
        if any(not isinstance(v, int) or isinstance(v, bool) for v in (start, end)):
            raise _invalid_range("selection_range의 start, end는 정수여야 합니다.", selection_range)
        if not 0 <= start < end <= len(manuscript_text):
            raise _invalid_range("selection_range가 원고 범위를 벗어났습니다.", selection_range)

    data["messages"] = _validate_messages(data["messages"])
    return data


def _validate_messages(messages: Any) -> list[dict[str, str]]:
    """같은 스레드의 이전 메시지(AIQ 2.2 QAMessage)에서 role, content만 꺼낸다.

    그 밖의 필드(message_id, status 등)는 무시한다. 답변이 아직 없거나 실패한
    assistant 메시지(content가 null)는 백엔드가 빼고 넘긴다.
    """
    if messages is None:
        return []
    expect_list_of(messages, dict, "messages")
    cleaned = []
    for index, message in enumerate(messages):
        role = message.get("role")
        if role not in MESSAGE_ROLES:
            raise InputValidationError(
                "messages의 role은 user 또는 assistant여야 합니다.",
                {"field": f"messages[{index}].role", "received": role},
            )
        content = expect_text(message.get("content"), f"messages[{index}].content")
        cleaned.append({"role": role, "content": content})
    return cleaned


@public_api("aiq")
def run_aiq(
    question: str,
    manuscript_text: str,
    scope: str = "whole",
    selection_range: dict[str, int] | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """원고에 대한 질문에 답한다.

    messages는 같은 스레드의 이전 메시지(시간순, AIQ 4.4 후속 질문)다. 첫 질문이면 비워 둔다.
    """
    return run_module(
        module="aiq",
        input_data={
            "question": question,
            "manuscript_text": manuscript_text,
            "scope": scope,
            "selection_range": selection_range,
            "messages": messages,
        },
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=AIQOutput,
        timeout=AIQ_TIMEOUT_SECONDS,
    )
