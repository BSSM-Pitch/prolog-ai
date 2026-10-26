"""LLM API 호출 (OpenRouter 또는 NVIDIA의 OpenAI 호환 API).

호출은 call_llm() 한 함수로 모은다. PROLOG_AI_PROVIDER로 제공사를 고르고,
PROLOG_AI_MODEL을 비우면 제공사별 기본 모델을 쓴다. 각 제공사의 키만 사용한다.

USE_FAKE_LLM=1이면 실제 API를 호출하지 않고, 넘겨받은 pydantic 스키마를
만족하는 가짜 응답을 만들어 돌려준다. 실제 API를 호출하는 경로는
tests/test_llm_real_path.py에서 가짜 openai 클라이언트로 검증한다(네트워크 호출 없음).
"""

import enum
import json
import os
import time
import types
import typing
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
NVIDIA_DEFAULT_MODEL = "z-ai/glm-5.3-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2  # 최초 시도 포함 최대 3회 시도
# OpenRouter는 추론(thinking) 토큰도 max_tokens에 함께 센다(openrouter.ai/docs/use-cases/reasoning-tokens).
# DeepSeek은 추론이 기본으로 켜져 있어 4096이면 추론만으로 한도를 채워 출력이 잘리는 일이 실제로 생겼다
# (2026-09-29, REX 호출 2번). 보이는 출력은 수백~2천 토큰이라 한도만 넉넉히 둔다.
MAX_OUTPUT_TOKENS = 16384
# 추출·판정의 변동을 줄이도록 무작위성을 낮춘다. 결정성을 보장하지는 않는다.
TEMPERATURE = 0.0
# 요청 시간 초과(408)·충돌(409)·속도 제한(429)과 5xx만 다시 시도한다. 인증 오류 등은 다시 해도 같다.
_RETRYABLE_STATUS = {408, 409, 429}


class LLMFailedError(Exception):
    """LLM 호출이 재시도 후에도 실패했을 때."""


class LLMTimeoutError(Exception):
    """LLM 호출이 재시도 후에도 시간 초과됐을 때."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    temperature: float
    top_p: float
    reasoning_effort: str | None = None

    def request_options(self) -> dict[str, Any]:
        if self.provider == "openrouter":
            return {"extra_body": {"provider": {"require_parameters": True}}}
        if self.reasoning_effort is not None:
            return {
                "reasoning_effort": self.reasoning_effort,
                "extra_body": {"chat_template_kwargs": {"clear_thinking": True}},
            }
        return {}

    def require_api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise LLMFailedError(f"{self.api_key_env}가 설정되지 않았습니다.")
        return key


def get_llm_config() -> LLMConfig:
    """키를 포함하지 않는 설정. 실행 경로와 기억 캐시의 제공사/모델을 일치시킨다."""
    provider = os.environ.get("PROLOG_AI_PROVIDER", "").strip().lower() or "nvidia"
    providers = {
        "openrouter": (OPENROUTER_BASE_URL, DEFAULT_MODEL, "OPENROUTER_API_KEY"),
        "nvidia": (NVIDIA_BASE_URL, NVIDIA_DEFAULT_MODEL, "NVIDIA_API_KEY"),
    }
    if provider not in providers:
        raise LLMFailedError("PROLOG_AI_PROVIDER는 openrouter 또는 nvidia여야 합니다.")
    base_url, default_model, key_env = providers[provider]
    model = os.environ.get("PROLOG_AI_MODEL", "").strip() or default_model
    temperature, top_p = TEMPERATURE, 1.0
    effort = None
    if provider == "nvidia":
        temperature = 0.5
        if model == "stepfun-ai/step-5-preview":
            temperature, top_p = 1.0, 0.95
        if model == NVIDIA_DEFAULT_MODEL:
            effort = os.environ.get("PROLOG_AI_REASONING_EFFORT", "").strip() or "low"
            if effort not in {"low", "high", "max"}:
                raise LLMFailedError("GLM reasoning_effort는 low, high, max여야 합니다.")
    return LLMConfig(provider, base_url, model, key_env, temperature, top_p, effort)


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
    import openai

    config = get_llm_config()
    # 다른 제공사나 OPENAI_API_KEY로 대체하지 않는다.
    api_key = config.require_api_key()
    # SDK도 자체 재시도(기본 2회)를 하므로 끄지 않으면 이 함수의 재시도와 겹쳐 요청이 최대 9번 나간다.
    client = openai.OpenAI(
        api_key=api_key, base_url=config.base_url, timeout=timeout, max_retries=0
    )
    try:
        return _request_with_client(client, config, prompt, schema, timeout, max_retries)
    finally:
        client.close()


def _request_with_client(client, config, prompt, schema, timeout, max_retries):
    import openai

    # OpenRouter 라우팅 옵션은 NVIDIA에 보내지 않는다.
    provider_options = config.request_options()

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            sleep_before_retry(attempt - 1)
        attempt_started = time.monotonic()
        try:
            response = client.chat.completions.create(
                model=config.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=config.temperature,
                top_p=config.top_p,
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "respond",
                            "description": "정해진 스키마로 응답한다.",
                            "parameters": schema.model_json_schema(),
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": "respond"}},
                stream=config.provider == "nvidia",
                **provider_options,
            )
            if config.provider == "nvidia":
                response = _collect_stream(response, timeout, started=attempt_started)
        except LLMTimeoutError as exc:
            last_error = exc
            continue
        except openai.APIStatusError as exc:
            if not _is_retryable_status(exc.status_code):
                raise LLMFailedError(
                    f"LLM 요청이 거부되었습니다({exc.status_code}): {exc}"
                ) from exc
            last_error = exc
            continue
        except openai.OpenAIError as exc:
            last_error = exc
            continue

        if not response.choices:
            last_error = LLMFailedError("LLM 응답에 choices가 없습니다.")
            continue
        choice = response.choices[0]
        if choice.finish_reason == "length":
            # 같은 요청을 다시 보내도 또 잘리므로 재시도하지 않는다.
            raise LLMFailedError(f"LLM 출력이 최대 길이({MAX_OUTPUT_TOKENS} 토큰)에서 잘렸습니다.")
        if choice.finish_reason not in {"stop", "tool_calls"}:
            last_error = LLMFailedError("LLM 응답의 완료 신호가 없습니다.")
            continue
        arguments = _find_tool_arguments(choice.message)
        if arguments is None:
            last_error = LLMFailedError("LLM 응답에 respond 도구 호출이 없습니다.")
            continue
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            last_error = LLMFailedError(f"LLM 도구 호출 인자가 JSON이 아닙니다: {exc}")
            continue
        if not isinstance(parsed, dict):
            last_error = LLMFailedError("LLM 도구 호출 인자가 JSON 객체가 아닙니다.")
            continue
        return parsed

    # 408(요청 시간 초과)로 재시도가 끝난 것도 시간 초과로 분류한다.
    timed_out = isinstance(last_error, (openai.APITimeoutError, LLMTimeoutError)) or (
        isinstance(last_error, openai.APIStatusError) and last_error.status_code == 408
    )
    if timed_out:
        raise LLMTimeoutError(str(last_error)) from last_error
    raise LLMFailedError(str(last_error)) from last_error


def _collect_stream(stream, timeout, *, started=None):
    """추론 내용은 저장하지 않는다. 도구 인자를 합치고 완료 신호를 보존한다.

    SDK timeout은 무응답 대기 제한이며, 진행 중 스트림도 timeout을 넘으면 중단한다.
    시간 검사는 청크 수신 시 실행되므로 대기 중에는 SDK의 읽기 제한이 적용된다.
    """
    started = time.monotonic() if started is None else started
    parts = {}
    finish = None
    try:
        for chunk in stream:
            if time.monotonic() - started > timeout:
                raise LLMTimeoutError("LLM 스트리밍 처리 시간 한도를 넘었습니다.")
            for choice in chunk.choices:
                if choice.index != 0:
                    continue
                finish = choice.finish_reason or finish
                for call in choice.delta.tool_calls or []:
                    part = parts.setdefault(call.index, {"name": "", "arguments": ""})
                    if call.function:
                        part["name"] += call.function.name or ""
                        part["arguments"] += call.function.arguments or ""
    finally:
        stream.close()
    calls = [types.SimpleNamespace(function=types.SimpleNamespace(**p)) for p in parts.values()]
    return types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                finish_reason=finish,
                message=types.SimpleNamespace(tool_calls=calls),
            )
        ]
    )


def _find_tool_arguments(message: Any) -> str | None:
    calls = getattr(message, "tool_calls", None) or []
    if len(calls) != 1:
        return None
    for tool_call in calls:
        function = getattr(tool_call, "function", None)
        if getattr(function, "name", None) == "respond":
            return function.arguments
    return None


def _is_retryable_status(status_code: int) -> bool:
    return status_code in _RETRYABLE_STATUS or status_code >= 500


def _build_fake_instance(schema: type[BaseModel]) -> dict[str, Any]:
    """schema(pydantic v2 모델)를 만족하는 최소 형태의 가짜 값을 만든다."""
    factory = getattr(schema, "fake_response", None)
    if callable(factory):
        return schema.model_validate(factory()).model_dump()
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
