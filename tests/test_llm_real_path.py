"""core/llm.py의 실제 API 경로를 가짜 openai 클라이언트로 검증한다. 네트워크 호출 없음."""

import json
from types import SimpleNamespace

import httpx2 as httpx
import openai
import pytest
from pydantic import BaseModel

from prolog_ai.core import llm
from prolog_ai.core.llm import LLMFailedError, LLMTimeoutError, call_llm


class Output(BaseModel):
    value: str


REQUEST = httpx.Request("POST", "https://example.invalid")


def status_error(cls, status_code):
    response = httpx.Response(status_code, request=REQUEST)
    return cls(f"status {status_code}", response=response, body=None)


def tool_response(payload, finish_reason="tool_calls", name="respond"):
    arguments = payload if isinstance(payload, str) else json.dumps(payload)
    tool_call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))
    message = SimpleNamespace(content=None, tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def text_response():
    message = SimpleNamespace(content="글로만 답함", tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


@pytest.fixture
def fake_client(monkeypatch):
    """create()가 behaviors를 순서대로 돌려주거나(예외면 raise) 하는 가짜 클라이언트."""
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("PROLOG_AI_MODEL", "test-model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    sleeps = []
    monkeypatch.setattr(llm, "sleep_before_retry", sleeps.append)
    state = SimpleNamespace(behaviors=[], calls=[], init_kwargs=None, sleeps=sleeps)

    class FakeCompletions:
        def create(self, **kwargs):
            state.calls.append(kwargs)
            behavior = state.behaviors[min(len(state.calls), len(state.behaviors)) - 1]
            if isinstance(behavior, Exception):
                raise behavior
            return behavior

    class FakeClient:
        def __init__(self, **kwargs):
            state.init_kwargs = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    return state


def test_returns_tool_call_arguments(fake_client):
    fake_client.behaviors = [tool_response({"value": "ok"})]
    assert call_llm("p", schema=Output) == {"value": "ok"}
    assert len(fake_client.calls) == 1


def test_request_uses_env_model_schema_and_forced_tool(fake_client):
    fake_client.behaviors = [tool_response({"value": "ok"})]
    call_llm("프롬프트", schema=Output, timeout=12.0)
    request = fake_client.calls[0]
    assert request["model"] == "test-model"
    assert request["messages"] == [{"role": "user", "content": "프롬프트"}]
    assert request["tools"][0]["function"]["parameters"] == Output.model_json_schema()
    assert request["tool_choice"] == {"type": "function", "function": {"name": "respond"}}
    assert fake_client.init_kwargs["api_key"] == "test-key"
    assert fake_client.init_kwargs["base_url"] == llm.OPENROUTER_BASE_URL
    assert fake_client.init_kwargs["timeout"] == 12.0


def test_default_model_when_env_is_empty(fake_client, monkeypatch):
    monkeypatch.setenv("PROLOG_AI_MODEL", "")
    fake_client.behaviors = [tool_response({"value": "ok"})]
    call_llm("p", schema=Output)
    assert fake_client.calls[0]["model"] == llm.DEFAULT_MODEL


def test_sdk_internal_retries_are_disabled(fake_client):
    fake_client.behaviors = [tool_response({"value": "ok"})]
    call_llm("p", schema=Output)
    assert fake_client.init_kwargs["max_retries"] == 0


def test_timeout_retries_then_raises_timeout(fake_client):
    fake_client.behaviors = [openai.APITimeoutError(request=REQUEST)]
    with pytest.raises(LLMTimeoutError):
        call_llm("p", schema=Output, max_retries=2)
    assert len(fake_client.calls) == 3
    assert fake_client.sleeps == [0, 1]


def test_recovers_when_a_retry_succeeds(fake_client):
    fake_client.behaviors = [
        openai.APIConnectionError(request=REQUEST),
        tool_response({"value": "ok"}),
    ]
    assert call_llm("p", schema=Output) == {"value": "ok"}
    assert len(fake_client.calls) == 2


@pytest.mark.parametrize(
    "cls, status_code",
    [
        (openai.AuthenticationError, 401),
        (openai.PermissionDeniedError, 403),
        (openai.BadRequestError, 400),
        (openai.NotFoundError, 404),
    ],
)
def test_non_retryable_status_fails_immediately(fake_client, cls, status_code):
    fake_client.behaviors = [status_error(cls, status_code)]
    with pytest.raises(LLMFailedError):
        call_llm("p", schema=Output)
    assert len(fake_client.calls) == 1


@pytest.mark.parametrize(
    "cls, status_code",
    [(openai.RateLimitError, 429), (openai.InternalServerError, 500)],
)
def test_retryable_status_is_retried(fake_client, cls, status_code):
    fake_client.behaviors = [status_error(cls, status_code)]
    with pytest.raises(LLMFailedError):
        call_llm("p", schema=Output, max_retries=2)
    assert len(fake_client.calls) == 3


def test_missing_tool_call_is_retried_then_fails(fake_client):
    fake_client.behaviors = [text_response()]
    with pytest.raises(LLMFailedError, match="respond"):
        call_llm("p", schema=Output, max_retries=2)
    assert len(fake_client.calls) == 3


def test_other_tool_name_is_treated_as_missing(fake_client):
    fake_client.behaviors = [tool_response({"value": "ok"}, name="other")]
    with pytest.raises(LLMFailedError, match="respond"):
        call_llm("p", schema=Output, max_retries=0)


@pytest.mark.parametrize("arguments", ["{잘못된 json", "[1, 2]"])
def test_invalid_arguments_are_retried_then_fail(fake_client, arguments):
    fake_client.behaviors = [tool_response(arguments)]
    with pytest.raises(LLMFailedError, match="JSON"):
        call_llm("p", schema=Output, max_retries=1)
    assert len(fake_client.calls) == 2


def test_empty_choices_is_retried_then_fails(fake_client):
    fake_client.behaviors = [SimpleNamespace(choices=[])]
    with pytest.raises(LLMFailedError, match="choices"):
        call_llm("p", schema=Output, max_retries=1)
    assert len(fake_client.calls) == 2


def test_truncated_output_fails_without_retry(fake_client):
    fake_client.behaviors = [tool_response('{"value": "잘', finish_reason="length")]
    with pytest.raises(LLMFailedError, match="잘렸"):
        call_llm("p", schema=Output)
    assert len(fake_client.calls) == 1


def test_public_function_maps_real_path_failures_to_module_codes(fake_client):
    from prolog_ai import run_nlcd

    fake_client.behaviors = [openai.APITimeoutError(request=REQUEST)]
    assert run_nlcd("피터는 책임감이 강하다.")["error"]["code"] == "AI_EXTRACTION_TIMEOUT"

    fake_client.calls.clear()
    fake_client.behaviors = [tool_response("{}", finish_reason="length")]
    assert run_nlcd("피터는 책임감이 강하다.")["error"]["code"] == "AI_EXTRACTION_FAILED"


def test_aiq_uses_longer_timeout_than_other_modules(fake_client):
    from prolog_ai import run_aiq, run_nlcd
    from prolog_ai.modules.aiq.module import AIQ_TIMEOUT_SECONDS

    fake_client.behaviors = [tool_response({"content": "답"})]
    run_aiq("질문", "원고", "project")
    assert fake_client.init_kwargs["timeout"] == AIQ_TIMEOUT_SECONDS > llm.DEFAULT_TIMEOUT_SECONDS

    fake_client.behaviors = [tool_response({})]
    run_nlcd("피터는 책임감이 강하다.")
    assert fake_client.init_kwargs["timeout"] == llm.DEFAULT_TIMEOUT_SECONDS


def test_scds_analysis_uses_longer_timeout(fake_client):
    from prolog_ai import run_scds_analysis
    from prolog_ai.modules.scds.module import SCDS_TIMEOUT_SECONDS

    rule_result = {
        "has_candidate": True,
        "skipped": False,
        "skipped_reason": None,
        "candidates": [
            {"rule_id": "r", "character_id": "c", "conflict_target": "폭력 회피", "matched_keyword": "살해"}
        ],
    }
    fake_client.behaviors = [tool_response({"conflicts": []})]
    run_scds_analysis({"character_ids": ["c"], "content": "살해"}, rule_result)
    assert fake_client.init_kwargs["timeout"] == SCDS_TIMEOUT_SECONDS > llm.DEFAULT_TIMEOUT_SECONDS


def test_missing_api_key_fails_before_creating_client(fake_client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-should-not-be-sent")
    with pytest.raises(LLMFailedError, match="OPENROUTER_API_KEY"):
        call_llm("p", schema=Output)
    assert fake_client.init_kwargs is None


def test_requests_only_tool_capable_providers(fake_client):
    fake_client.behaviors = [tool_response({"value": "ok"})]
    call_llm("p", schema=Output)
    assert fake_client.calls[0]["extra_body"] == {"provider": {"require_parameters": True}}


def test_http_408_after_retries_is_timeout(fake_client):
    fake_client.behaviors = [status_error(openai.APIStatusError, 408)]
    with pytest.raises(LLMTimeoutError):
        call_llm("p", schema=Output)


def test_rex_and_ssm_use_longer_timeout(fake_client):
    from prolog_ai import run_rex, run_ssm

    fake_client.behaviors = [tool_response({"extracted_rules": []})]
    run_rex("원고")
    assert fake_client.init_kwargs["timeout"] > llm.DEFAULT_TIMEOUT_SECONDS

    fake_client.behaviors = [tool_response({"acts": [], "nodes": []})]
    run_ssm("원고")
    assert fake_client.init_kwargs["timeout"] > llm.DEFAULT_TIMEOUT_SECONDS
