"""No previous analysis or expected-novel labels enter the first-pass protocol."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.core.request_policy import RequestPolicy, request_policy
from prolog_ai.memory import compact, compact_wire
from prolog_ai.memory import verification_wire as wire


def fixture():
    scenes = [
        {
            "scene_id": "s",
            "revision": "r",
            "order": 1,
            "text": "민서가 말했다. “괜찮아.” 지훈은 고개를 저었다. 민서는 차이를 알아챘다.",
        }
    ]
    batch = {
        **compact.plan(scenes)[0],
        "known_people": [],
        "allow_partial": True,
        "review_actions": True,
    }
    raw = {
        "people": [{"name": "민서", "alias": -1, "u": 0}, {"name": "지훈", "alias": -1, "u": 2}],
        "rows": [[0, 0, 1, 0, 0, 1], [1, 0, 0, 0, 0, 1], [2, 1, 1, 0, 0, 1], [3, 0, 2, 3, 2, 1]],
        "skip": [],
    }
    extracted = compact.validate_extraction(batch, compact_wire.extraction_response(batch, raw))
    shared = compact.share_discovered_people([batch], [extracted])[0]
    return (
        scenes,
        shared,
        extracted,
        {**compact.verification_payload(shared, extracted), "allow_partial": True},
    )


def test_target_text_kind_and_perception_are_preserved_without_proposed_subjects():
    _, _, _, payload = fixture()
    request = wire.request(payload)
    assert request["people"] == ["민서", "지훈"]
    assert request["source"][1]["text"] == " “괜찮아.”"
    assert request["source"][1]["targets"][0]["r"] == "T1.1"
    assert request["source"][3]["targets"][0]["role"] == "awareness"
    assert request["source"][3]["targets"][0]["kind"] == "inner_thought"
    assert all(
        "c" not in t and "subject" not in t for u in request["source"] for t in u.get("targets", [])
    )
    assert request["source"][1]["u"] == "U1"


@pytest.mark.parametrize(
    "damage",
    [
        "wrong_target_key",
        "wrong_proof",
        "numeric_person",
        "duplicate",
        "unknown_source",
        "cross_chapter",
    ],
)
def test_misaddressed_review_never_confirms_another_person(damage):
    _, _, _, p = fixture()
    p["observations"] = p["observations"][1:2]
    row = {"r": "T1.1", "c": "민서", "e": "U0", "n": 2}
    raw = {"rows": [row], "links": []}
    if damage == "wrong_target_key":
        row["r"] = "T1.0"
    elif damage == "wrong_proof":
        row.update(e="U2", c="지훈", n=1)
    elif damage == "numeric_person":
        row["c"] = "0"
    elif damage == "duplicate":
        raw["rows"].append({**row, "c": "지훈"})
    elif damage == "unknown_source":
        row["e"] = "U999"
    else:
        p["units"][0]["scene"] = "other"
    result = compact.validate_verification(p, wire.response(p, raw))
    assert compact.missing_verifications(p, result) == [1]
    assert all(d["a"] == "uncertain" and d["c"] is None for d in result["decisions"])


def test_shuffled_targets_and_nonconsecutive_indices_are_not_recounted():
    _, _, _, p = fixture()
    p["observations"] = p["observations"][1:3]
    p["observations"][0]["i"] = 73
    p["observations"][1]["i"] = 9
    raw = {
        "rows": [
            {"r": "T2.9", "c": "지훈", "e": "U2", "n": 1},
            {"r": "T1.73", "c": "민서", "e": "U0", "n": 2},
        ],
        "links": [],
    }
    result = compact.validate_verification(p, wire.response(p, raw))
    assert [(d["i"], d["c"]) for d in result["decisions"]] == [(9, "지훈"), (73, "민서")]
    assert compact.missing_verifications(p, result) == []


def test_live_step_uses_new_contract_in_one_existing_request(monkeypatch):
    _, _, _, p = fixture()
    p["observations"] = p["observations"][1:2]
    monkeypatch.delenv("USE_FAKE_LLM", raising=False)

    def response(prompt, **kwargs):
        assert kwargs["schema"] is wire.CompactContextVerification
        assert "T1.1" in prompt and "U1" in prompt
        return {"rows": [{"r": "T1.1", "c": "민서", "e": "U0", "n": 2}], "links": []}

    with (
        patch.object(compact, "call_llm", side_effect=response) as model,
        request_policy(RequestPolicy(before_attempt=lambda: None)),
    ):
        result = compact.run_step("verify", p)
    assert model.call_count == 1
    assert result["decisions"][0]["c"] == "민서"
    assert result["validation_audit"]["target_keys_validated"]


def test_empty_roster_can_link_newly_discovered_parent_in_same_response():
    scene = {
        "scene_id": "s",
        "revision": "r",
        "order": 1,
        "text": "민서의 어머니는 정은이다. 어머니는 휘파람을 불었다.",
    }
    batch = {
        **compact.plan([scene])[0],
        "known_people": [],
        "allow_partial": True,
        "review_actions": True,
    }
    raw = {
        "people": [
            {"name": "민서", "alias": -1, "u": 0},
            {"name": "어머니", "alias": -1, "u": 0},
            {"name": "정은", "alias": -1, "u": 0},
        ],
        "rows": [[1, 1, 1, 0, 0, 1]],
        "skip": [0],
        "identities": [
            {"units": [1], "reference": 1, "relative_to": 0, "canonical": 2, "evidence": [0, 1]}
        ],
    }
    original = deepcopy(raw)
    e = compact.validate_extraction(batch, compact_wire.extraction_response(batch, raw))
    assert raw == original and e["observations"][0]["c"] == "정은"
    batch = compact.share_discovered_people([batch], [e])[0]
    p = compact.verification_payload(batch, e)
    review = compact.validate_verification(
        p,
        wire.response(p, {"rows": [{"r": "T1.0", "c": "어머니", "e": "U0", "n": 2}], "links": []}),
    )
    roster = [{"character_id": p["name"], "name": p["name"]} for p in e["people"]]
    memory = compact.build_memory("p", [scene], roster, [batch], [e], [review], model="offline")
    assert memory.observations[0].character_id == "정은"
    assert memory.observations[0].attribution == "certain"


def test_first_pass_shares_new_names_but_requires_independent_alias_confirmation():
    scenes = [
        {"scene_id": "a", "revision": "r", "order": 1, "text": "윤하가 말했다."},
        {"scene_id": "b", "revision": "r", "order": 2, "text": "서윤하는 창문을 닫았다."},
    ]
    batches = []
    extracts = []
    for scene, name in zip(scenes, ["윤하", "서윤하"], strict=True):
        b = {
            **compact.plan([scene])[0],
            "known_people": [],
            "allow_partial": True,
            "review_actions": True,
        }
        e = compact.validate_extraction(
            b,
            compact_wire.extraction_response(
                b,
                {
                    "people": [{"name": name, "alias": -1, "u": 0}],
                    "rows": [[0, 0, 1, 0, 0, 1]],
                    "skip": [],
                },
            ),
        )
        batches.append(b)
        extracts.append(e)
    original = deepcopy(extracts)
    batches = compact.share_discovered_people(batches, extracts)
    assert extracts == original
    assert all({p["name"] for p in b["known_people"]} == {"윤하", "서윤하"} for b in batches)
    assert batches[0]["binding_candidates"] == {"윤하": ["서윤하"]}
    reviews = []
    for b, e in zip(batches, extracts, strict=True):
        p = compact.verification_payload(b, e)
        reviews.append(
            compact.validate_verification(
                p,
                wire.response(
                    p,
                    {
                        "rows": [{"r": "T0.0", "c": "서윤하", "e": "U0", "n": 1}],
                        "links": [{"name": "윤하", "canonical": "서윤하", "evidence": "U0"}]
                        if p["alias_names"]
                        else [],
                    },
                ),
            )
        )
    roster = [{"character_id": "y", "name": "서윤하"}]
    memory = compact.build_memory("p", scenes, roster, batches, extracts, reviews, model="offline")
    assert [o.character_id for o in memory.observations] == ["y", "y"]
    reviews[0]["bindings"][0]["canonical"] = None
    rejected = compact.build_memory(
        "p", scenes, roster, batches, extracts, reviews, model="offline"
    )
    assert rejected.observations[0].attribution == "uncertain"
    assert not memory.characters[0].aliases


def test_bad_alias_response_does_not_erase_valid_subject_decision():
    _, _, _, p = fixture()
    p["observations"] = p["observations"][:1]
    p["alias_names"] = ["민서"]
    raw = {
        "rows": [{"r": "T0.0", "c": "민서", "e": "U0", "n": 1}],
        "links": [{"name": "민서", "canonical": "지훈", "evidence": "U999"}],
    }
    result = compact.validate_verification(p, wire.response(p, raw))
    assert result["decisions"][0]["c"] == "민서"
    assert result["decisions"][0]["a"] == "certain"
    assert result["bindings"][0]["canonical"] is None
    assert result["validation_audit"]["unresolved_alias_responses"][0]["responses"] == raw["links"]
