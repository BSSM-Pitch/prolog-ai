"""AIQ 모듈의 공개 함수."""

from typing import Any

from prolog_ai.core.errors import ErrorCode
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.memory.reading import read_from_memory
from prolog_ai.memory.retrieval import prepare_context
from prolog_ai.memory.source import encode
from prolog_ai.modules.aiq.prompt import build_prompt
from prolog_ai.modules.aiq.schema import AIQOutput

# 백엔드 insight.qa_threads.scope 값(qa_threads_scope_chk)을 따른다. 명세 AIQ 2.1의 whole은
# 백엔드에서 project/chapter로 나뉜다(WARN.md D4). project·chapter는 넘겨받은 manuscript_text
# 전체를 보고 답하므로 동작이 같고, 어떤 본문을 넘길지는 백엔드가 정한다.
SCOPES = ("project", "chapter", "selection")
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
    if data["memory"] is None:
        expect_text(manuscript_text, "manuscript_text")
        if data["memory_character_ids"] is not None or data["as_of_order"] is not None:
            raise InputValidationError("기억 검색 옵션에는 memory가 필요합니다.")

    scope = data["scope"]
    if scope not in SCOPES:
        raise InputValidationError(
            "scope는 project, chapter, selection 중 하나여야 합니다.",
            {"field": "scope", "received": scope},
        )

    if scope == "selection":
        selection_range = data["selection_range"]
        if not isinstance(selection_range, dict):
            raise _invalid_range(
                "scope=selection이지만 selection_range가 없습니다.", selection_range
            )
        start, end = selection_range.get("start"), selection_range.get("end")
        if start is None or end is None:
            raise _invalid_range("selection_range에 start, end가 없습니다.", selection_range)
        # 값이 있는데 정수가 아니면 범위 문제가 아니라 입력 형식 오류다.
        expect_type(start, int, "selection_range.start")
        expect_type(end, int, "selection_range.end")
        if not 0 <= start < end <= len(manuscript_text):
            raise _invalid_range("selection_range가 원고 범위를 벗어났습니다.", selection_range)

    data["messages"] = _validate_messages(data["messages"])
    if data["memory"] is not None:
        selection = ""
        if scope == "selection":
            selection = manuscript_text[
                data["selection_range"]["start"] : data["selection_range"]["end"]
            ]
        if len(encode([manuscript_text, selection, data["question"], data["messages"]])) > 8000:
            raise InputValidationError(
                "기억 모드의 현재 원고·질문·대화는 합계 8000자 이하여야 합니다. "
                "전체 원고는 memory에 저장하고 현재 구간만 넘기세요."
            )
        data["memory_context"] = prepare_context(
            data["memory"],
            data["question"],
            data["memory_character_ids"],
            data["as_of_order"],
        )
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
    scope: str = "project",
    selection_range: dict[str, int] | None = None,
    messages: list[dict[str, Any]] | None = None,
    *,
    memory: dict | None = None,
    memory_character_ids: list[str] | None = None,
    as_of_order: int | None = None,
    review_character_details: bool = True,
    previous_analysis: dict | None = None,
) -> dict[str, Any]:
    """원고에 대한 질문에 답한다.

    messages는 같은 스레드의 이전 메시지(시간순, AIQ 4.4 후속 질문)다. 첫 질문이면 비워 둔다.
    지금 묻는 질문은 question으로만 넘기고 messages에는 넣지 않는다(넣으면 두 번 들어간다).
    memory가 있으면 인물 기억의 근거를 함께 검색하며 manuscript_text는 현재 구간 또는 빈 문자열이다.
    as_of_order는 기억의 독서 시점을 제한한다. 현재 원고와 대화의 시점은 호출자가 맞춘다.
    기억 모드는 기본적으로 선택된 원문 장면을 정독하고 별도 호출로 재검토한다.
    review_character_details=False이면 기존 단일 답변 경로를 사용한다.
    검토 실패의 details.checkpoint는 previous_analysis로 넘겨 재개한다.
    """
    expect_type(review_character_details, bool, "review_character_details")
    if previous_analysis is not None and (memory is None or not review_character_details):
        raise InputValidationError("previous_analysis는 기억 정독 모드에서만 사용할 수 있습니다.")
    input_data = {
        "question": question,
        "manuscript_text": manuscript_text,
        "scope": scope,
        "selection_range": selection_range,
        "messages": messages,
        "memory": memory,
        "memory_character_ids": memory_character_ids,
        "as_of_order": as_of_order,
        "previous_analysis": previous_analysis,
    }
    if memory is not None and review_character_details:
        result = read_from_memory(_validate(input_data))
        if "error" in result:
            result["error"]["code"] = {
                ErrorCode.AI_ANALYSIS_FAILED.value: ErrorCode.AI_RESPONSE_FAILED.value,
                ErrorCode.AI_ANALYSIS_TIMEOUT.value: ErrorCode.AI_RESPONSE_TIMEOUT.value,
            }.get(result["error"]["code"], result["error"]["code"])
        return result
    return run_module(
        module="aiq",
        input_data=input_data,
        validate=_validate,
        build_prompt=build_prompt,
        output_schema=AIQOutput,
        timeout=AIQ_TIMEOUT_SECONDS,
    )
