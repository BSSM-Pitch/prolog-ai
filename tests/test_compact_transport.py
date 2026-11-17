from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.core import llm
from prolog_ai.core.request_policy import RequestPolicy, current_policy, request_policy
from prolog_ai.memory import compact, repairs
from prolog_ai.memory import verification_wire as wire
from tests.test_first_pass_verification import fixture


def test_cache_prefix_identical_for_full_focused_and_single_repair(monkeypatch):
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "openai")
    monkeypatch.setenv("PROLOG_AI_MODEL", "gpt-6.1-sol")
    monkeypatch.delenv("PROLOG_AI_QUERY_MODEL", raising=False)
    _, _, _, payload = fixture()
    focused = compact.focused_verification(payload, {1})
    repair = compact.verification_repair_payload(payload, [1])
    packed, _ = repairs.pack("verify", [repair])
    prefixes, prompts = [], []

    def answer(prompt, **kwargs):
        prefixes.append(current_policy.get().prompt_cache_prefix)
        prompts.append(prompt)
        return {"rows": [], "links": []}

    with patch.object(compact, "call_llm", side_effect=answer):
        for p in [payload, focused, packed]:
            with request_policy(RequestPolicy(before_attempt=lambda: None)):
                compact.run_step("verify", {**p, "allow_partial": True})
    assert prefixes[0] == prefixes[1] == prefixes[2]
    assert prompts[0] == wire.INSTRUCTION + wire.COMPACT_INSTRUCTION + "\n" + compact.encode(wire.request(payload))
    assert prompts[0] != prompts[1] == prompts[2]
    assert wire.cache_parts(focused)[1]["requested_targets"] == ["T1.1"]
    assert '"c":' not in prefixes[0]


@pytest.mark.parametrize("change", ["text", "people", "kind", "quote"])
def test_stale_cache_context_rejected_before_model_call(change, monkeypatch):
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "openai")
    monkeypatch.setenv("PROLOG_AI_MODEL", "gpt-6.1-sol")
    monkeypatch.delenv("PROLOG_AI_QUERY_MODEL", raising=False)
    _, _, _, payload = fixture()
    focused = deepcopy(compact.focused_verification(payload, {1}))
    if change == "text":
        focused["units"][0]["text"] = "다른 원문"
    elif change == "people":
        focused["people"].append("새 인물")
    elif change == "kind":
        focused["observations"][0]["kind"] = "action"
    else:
        focused["observations"][0]["q"] = "다른 부분구절"
    with patch.object(compact, "call_llm") as model:
        with (
            request_policy(RequestPolicy(before_attempt=lambda: None)),
            pytest.raises(ValueError, match="Verification cache"),
        ):
            compact.run_step("verify", focused)
        model.assert_not_called()


def test_single_repair_preserves_nonconsecutive_ids_and_invalid_proofs():
    _, _, _, payload = fixture()
    payload["observations"][1]["i"] = 73
    local = compact.verification_repair_payload(payload, [73])
    packed, mappings = repairs.pack("verify", [local])
    assert packed["observations"][0]["i"] == 73
    result = wire.response(
        packed, {"rows": [{"r": "T1.73", "c": "민서", "e": "U2", "n": 1}], "links": []}
    )
    restored = repairs.unpack("verify", [local], result, mappings)[0]
    assert compact.missing_verifications(local, restored) == [73]


@pytest.mark.parametrize(
    "main,query,expected",
    [
        ("", "", "gpt-6-luna"),
        ("gpt-6.1-sol", "", "gpt-6.1-sol"),
        ("gpt-6.1-sol", "gpt-6-luna", "gpt-6-luna"),
    ],
)
def test_explicit_openai_query_model_is_not_silently_overridden(monkeypatch, main, query, expected):
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "openai")
    monkeypatch.setenv("PROLOG_AI_MODEL", main)
    monkeypatch.setenv("PROLOG_AI_QUERY_MODEL", query)
    config = llm.get_llm_config(simple_query=True)
    assert config.model == expected
    assert config.reasoning_effort == "low"


@pytest.mark.parametrize(
    "provider,model", [("nvidia", "z-ai/glm-5.3-flash"), ("openai", "gpt-4.1")]
)
def test_noncacheable_models_keep_original_focused_prompt(monkeypatch, provider, model):
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setenv("PROLOG_AI_PROVIDER", provider)
    monkeypatch.setenv("PROLOG_AI_MODEL", model)
    monkeypatch.delenv("PROLOG_AI_QUERY_MODEL", raising=False)
    _, _, _, payload = fixture()
    focused = compact.focused_verification(payload, {1})

    def answer(prompt, **kwargs):
        assert current_policy.get().prompt_cache_prefix is None
        assert prompt == wire.INSTRUCTION + wire.COMPACT_INSTRUCTION + "\n" + compact.encode(wire.request(focused))
        return {"rows": [], "links": []}

    with (
        patch.object(compact, "call_llm", side_effect=answer),
        request_policy(RequestPolicy(before_attempt=lambda: None)),
    ):
        compact.run_step("verify", {**focused, "allow_partial": True})
