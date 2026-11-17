from unittest.mock import patch

import pytest

from prolog_ai.core.request_policy import RequestPolicy, current_policy, request_policy
from prolog_ai.memory import compact


def payload():
    return {
        "characters": [{"i": 0, "name": "가"}, {"i": 1, "name": "나"}],
        "observations": [
            {
                "i": i,
                "c": i % 2,
                "order": i + 1,
                "k": "action",
                "p": "depicted",
                "b": "choice",
                "quote": f"전후반 근거 {i}",
                "context": "다른 인물과의 문맥",
            }
            for i in range(4)
        ],
    }


def test_scoped_proposals_and_assessment_keep_identical_full_corpus_cache(monkeypatch):
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    source = payload()
    prefixes, prompts = [], []

    def answer(prompt, **kwargs):
        prefixes.append(current_policy.get().prompt_cache_prefix)
        prompts.append(prompt)
        assert kwargs["schema"] is compact.PatternTurn
        return {"proposals": [], "assessments": []}

    with (
        patch.object(compact, "call_llm", side_effect=answer),
        request_policy(RequestPolicy(before_attempt=lambda: None)),
    ):
        for subjects in ([0], [1]):
            compact.run_step("propose", {**source, "requested_subjects": subjects})
        compact.run_step("assess", {**source, "proposals": []})
    assert prefixes[0] == prefixes[1] == prefixes[2]
    assert "requested_subjects" not in prefixes[0]
    for row in source["observations"]:
        assert row["quote"] in prefixes[0]
    assert prompts[0] != prompts[1]


@pytest.mark.parametrize("subjects", [[], [0, 0], [9], [True], "0"])
def test_bad_scope_rejected_without_paid_call(subjects, monkeypatch):
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    with patch.object(compact, "call_llm") as model:
        with (
            request_policy(RequestPolicy(before_attempt=lambda: None)),
            pytest.raises(ValueError, match="Invalid requested"),
        ):
            compact.run_step("propose", {**payload(), "requested_subjects": subjects})
        model.assert_not_called()


def test_model_cannot_emit_another_groups_subject():
    proposal = {"c": 1, "description": "반복", "condition": "위기", "seeds": [1, 3]}
    with pytest.raises(ValueError, match="outside requested"):
        compact.validate_pattern_response(
            "propose", {**payload(), "requested_subjects": [0]}, {"proposals": [proposal]}
        )
