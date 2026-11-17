"""Immutable source-keyed paid review reuse, with conflicting evidence preserved."""

from copy import deepcopy

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory.review_history import reuse_reviews
from prolog_ai.memory.source import snapshot_id, validate_memory


def fixture():
    scenes = [
        {
            "scene_id": "s",
            "revision": "r",
            "order": 1,
            "text": "민서가 말했다.\n“괜찮아.”\n지훈은 고개를 저었다.\n“괜찮아.”",
        }
    ]
    roster = [{"character_id": n, "name": n} for n in ["민서", "지훈"]]
    batch = {**compact.batch_payload(compact.plan(scenes)[0], roster), "review_actions": True}
    extraction = {
        "people": [],
        "observations": [
            {
                "c": "민서",
                "a": "certain",
                "e": [1],
                "x": [0],
                "k": "speech",
                "p": "depicted",
                "b": "other",
                "to": [],
            }
        ],
        "covered_units": [0, 1, 2, 3],
        "skipped_units": [0, 2, 3],
    }
    past = {
        "decisions": [{"i": 0, "c": "민서", "a": "certain", "e": [0, 1], "reason": "발화 지문"}]
    }
    current = {
        "decisions": [{"i": 0, "c": None, "a": "uncertain", "e": [1], "reason": "확정 불가"}]
    }

    def build(review):
        m = compact.build_memory(
            "p", scenes, roster, [batch], [extraction], [review], model="offline"
        )
        m.complete = True
        validate_memory(m.model_dump(), require_complete=True)
        return m

    return build(current), build(past).model_dump()


def test_paid_review_reuse_preserves_current_checks_and_original_history():
    memory, prior = fixture()
    before = deepcopy(prior)
    report = reuse_reviews(memory, prior, analysis_id="previous-job")
    assert prior == before
    assert len(report["reused"]) == 1
    row = memory.observations[0]
    assert row.character_id == "민서" and row.attribution == "certain"
    assert row.attribution_checks[1].attribution == "uncertain"
    assert row.attribution_checks[-1].evidence[0].quote == "민서가 말했다.\n“괜찮아.”"
    assert "previous-job" in row.attribution_checks[-1].reason
    assert memory.speaker_verifications[0].observation_id == row.observation_id
    validate_memory(memory.model_dump(), require_complete=True)
    assert not reuse_reviews(memory, prior, analysis_id="same-job")["reused"]


@pytest.mark.parametrize(
    "damage",
    [
        "revision",
        "context",
        "project",
        "mode",
        "candidate",
        "prior_uncertain",
        "no_independent_proof",
        "same_text_different_position",
        "kind",
        "ambiguous_past",
        "renamed_character",
    ],
)
def test_history_is_not_a_vote_or_a_text_match(damage):
    memory, prior = fixture()
    if damage == "revision":
        memory.scenes[0].revision = "changed"
    elif damage == "context":
        memory.scenes[0].text += " 주변 문맥이 바뀌었다."
    elif damage == "project":
        memory.project_id = "other"
    elif damage == "mode":
        memory.mode = "fake"
    elif damage == "candidate":
        memory.observations[0].attribution_checks[0].character_id = "지훈"
    elif damage == "prior_uncertain":
        prior["observations"][0]["attribution"] = "uncertain"
    elif damage == "no_independent_proof":
        prior["observations"][0]["attribution_checks"] = prior["observations"][0][
            "attribution_checks"
        ][:1]
    elif damage == "same_text_different_position":
        ev = memory.observations[0].evidence
        ev.start = memory.scenes[0].text.rfind(ev.quote)
        ev.end = ev.start + len(ev.quote)
    elif damage == "kind":
        memory.observations[0].kind = "narration"
        memory.speaker_verifications = []
    elif damage == "ambiguous_past":
        second = deepcopy(prior["observations"][0])
        second.update(observation_id="other", character_id="지훈")
        prior["observations"].append(second)
        check = deepcopy(prior["speaker_verifications"][0])
        check["observation_id"] = "other"
        prior["speaker_verifications"].append(check)
    else:
        memory.characters[0].name = "새 이름"
        memory.snapshot_id = snapshot_id(memory.project_id, memory.characters, memory.scenes)
    assert not reuse_reviews(memory, prior, analysis_id="old")["reused"]
    assert memory.observations[0].attribution == "uncertain"


@pytest.mark.parametrize("direct", [True, False])
def test_competing_current_proof_blocks_old_review(direct):
    memory, prior = fixture()
    c = memory.observations[0].attribution_checks[1]
    c.name = c.character_id = "지훈"
    c.attribution = "certain"
    if not direct:
        text = memory.scenes[0].text
        quote = "지훈은 고개를 저었다."
        lo = text.index(quote)
        c.evidence[0] = c.evidence[0].model_copy(
            update={"quote": quote, "start": lo, "end": lo + len(quote)}
        )
    report = reuse_reviews(memory, prior, analysis_id="old")
    assert report["blocked"][0]["reason"] == "conflicting_current_proof"
    assert memory.observations[0].attribution == "uncertain"
