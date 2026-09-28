"""Claude API 호출.

호출은 call_llm() 한 함수로 모은다. 모델 이름과 API 키는 환경변수
(PROLOG_AI_MODEL, ANTHROPIC_API_KEY)로 받는다.

USE_FAKE_LLM=1이면 실제 API를 호출하지 않고, 넘겨받은 pydantic 스키마를
만족하는 가짜 응답을 만들어 돌려준다. 실제 API를 호출하는 경로는
tests/test_llm_real_path.py에서 가짜 anthropic 클라이언트로 검증한다(네트워크 호출 없음).
"""

import enum
import os
import time
import types
import typing
from typing import Any

from pydantic import BaseModel

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2  # 최초 시도 포함 최대 3회 시도
MAX_OUTPUT_TOKENS = 4096
# 요청 시간 초과(408)·충돌(409)·속도 제한(429)과 5xx만 다시 시도한다. 인증 오류 등은 다시 해도 같다.
_RETRYABLE_STATUS = {408, 409, 429}


class LLMFailedError(Exception):
    """LLM 호출이 재시도 후에도 실패했을 때."""


class LLMTimeoutError(Exception):
    """LLM 호출이 재시도 후에도 시간 초과됐을 때."""


def _use_fake_llm() -> bool:
    return os.environ.get("USE_FAKE_LLM") == "1"


def call_llm(
    prompt: str,
    *,
    schema: type[BaseModel],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """prompt를 LLM에 보내고 schema 형태의 원시 딕셔너리를 반환한다.

    반환값은 아직 schema로 검증되지 않은 원시 데이터다(스키마 검증은
    core/runner.py의 책임). 실패 시 LLMFailedError, 시간 초과 시
    LLMTimeoutError를 던진다.
    """
    if _use_fake_llm():
        return _build_fake_instance(schema)

    return _call_real_llm(prompt, schema=schema, timeout=timeout, max_retries=max_retries)


def _call_real_llm(
    prompt: str,
    *,
    schema: type[BaseModel],
    timeout: float,
    max_retries: int,
) -> dict[str, Any]:
    import anthropic

    model = os.environ.get("PROLOG_AI_MODEL")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    # SDK도 자체 재시도(기본 2회)를 하므로 끄지 않으면 이 함수의 재시도와 겹쳐 요청이 최대 9번 나간다.
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            sleep_before_retry(attempt - 1)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "name": "respond",
                        "description": "정해진 스키마로 응답한다.",
                        "input_schema": schema.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": "respond"},
            )
        except anthropic.APIStatusError as exc:
            if not _is_retryable_status(exc.status_code):
                raise LLMFailedError(f"LLM 요청이 거부되었습니다({exc.status_code}): {exc}") from exc
            last_error = exc
            continue
        except anthropic.AnthropicError as exc:
            last_error = exc
            continue

        if response.stop_reason == "max_tokens":
            # 같은 요청을 다시 보내도 또 잘리므로 재시도하지 않는다.
            raise LLMFailedError(f"LLM 출력이 최대 길이({MAX_OUTPUT_TOKENS} 토큰)에서 잘렸습니다.")
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        last_error = LLMFailedError("LLM 응답에 tool_use 블록이 없습니다.")

    if isinstance(last_error, anthropic.APITimeoutError):
        raise LLMTimeoutError(str(last_error)) from last_error
    raise LLMFailedError(str(last_error)) from last_error


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500


def _build_fake_instance(schema: type[BaseModel]) -> dict[str, Any]:
    """schema(pydantic v2 모델)를 만족하는 최소 형태의 가짜 값을 만든다."""
    data: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        data[name] = _fake_value_for_type(field.annotation)
    return data


def _fake_value_for_type(annotation: Any) -> Any:
    origin = typing.get_origin(annotation)

    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _fake_value_for_type(non_none[0]) if non_none else None

    if origin in (list, typing.List):  # noqa: UP006
        return []

    if origin in (dict, typing.Dict):  # noqa: UP006
        return {}

    if origin is typing.Literal:
        return typing.get_args(annotation)[0]
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return next(iter(annotation))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _build_fake_instance(annotation)
    if annotation is str:
        return ""
    if annotation is bool:
        return False
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0

    return None


def sleep_before_retry(attempt: int) -> None:
    """실제 API 재시도 사이의 대기. 테스트에서는 monkeypatch로 대기를 없앤다."""
    time.sleep(min(2**attempt, 5))
