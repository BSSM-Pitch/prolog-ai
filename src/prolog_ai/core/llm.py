"""Claude API 호출.

호출은 call_llm() 한 함수로 모은다. 모델 이름과 API 키는 환경변수
(PROLOG_AI_MODEL, ANTHROPIC_API_KEY)로 받는다.

USE_FAKE_LLM=1이면 실제 API를 호출하지 않고, 넘겨받은 pydantic 스키마를
만족하는 가짜 응답을 만들어 돌려준다. 이 저장소의 모든 테스트와 CI는
USE_FAKE_LLM=1로 실행되므로, 실제 API를 호출하는 경로는 이 파일 안에서
구조로만 존재하고 테스트로 검증되지 않는다.
"""

import os
import time
import types
import typing
from typing import Any

from pydantic import BaseModel

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2  # 최초 시도 포함 최대 3회 시도


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
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
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
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_before_retry(attempt)
            continue
        except anthropic.AnthropicError as exc:
            last_error = exc
            if attempt < max_retries:
                sleep_before_retry(attempt)
            continue
        else:
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    return block.input
            last_error = LLMFailedError("LLM 응답에 tool_use 블록이 없습니다.")

    if isinstance(last_error, anthropic.APITimeoutError):
        raise LLMTimeoutError(str(last_error)) from last_error
    raise LLMFailedError(str(last_error)) from last_error


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
    """실제 API 재시도 사이의 대기. 테스트(USE_FAKE_LLM=1)에서는 호출되지 않는다."""
    time.sleep(min(2**attempt, 5))
