"""Recover repaired role records from independently cited adjacent source."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory.source import validate_memory
from tests.test_scoped_identities import extract, sample


def fixture(*, preceding=False, gap=" ", target_text=None, owner="서윤하"):
    scenes, roster, anchor, raw = sample()
    first = extract(anchor, raw)
    target_text = target_text or "그 순서는 어머니가 가르쳐 준 것이었다."
    context = f"{owner}의 어머니는 손을 잡고 순서를 가르쳐 주었다."
    target_unit, context_unit = (1, 0) if preceding else (0, 1)
    text = context + gap + target_text if preceding else target_text + gap + context
    scene = {"scene_id": "repair", "revision": "r", "order": 2, "text": text}
    batch = {
        **compact.batch_payload(compact.plan([scene])[0], roster),
        "allow_partial": True,
        "review_actions": True,
    }
    names = [p["name"] for p in batch["known_people"]]
    mother = names.index("어머니")
    second = extract(
        batch,
        {
            "people": [],
            "skip": [],
            "rows": [[u, mother, 3, 2, 0, 1] for u in range(2)],
            "identities": [
                {
                    "units": [context_unit],
                    "reference": mother,
                    "relative_to": names.index(owner),
                    "canonical": mother,
                    "evidence": [context_unit],
                }
            ],
        },
    )
    # A sparse repair supplied this record without the original relation scope.
    second["observations"][target_unit].update(identity_scope=None, identity_unresolved=True)
    reviews = []
    for e in [first, second]:
        reviews.append(
            {
                "decisions": [
                    {"i": i, "c": "어머니", "a": "certain", "e": r["e"], "reason": "원문 검증"}
                    for i, r in enumerate(e["observations"])
                ]
            }
        )
    reviews[1]["decisions"][target_unit]["e"] = [0, 1]
    return (scenes + [scene], roster, [anchor, batch], [first, second], reviews), target_unit


def build(data):
    scenes, roster, batches, extracts, reviews = data
    with patch.object(compact, "call_llm", side_effect=AssertionError("No new LLM calls")):
        memory = compact.build_memory("p", scenes, roster, batches, extracts, reviews, model="test")
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    return [o for o in memory.observations if o.evidence.scene_id == "repair"]


@pytest.mark.parametrize("preceding", [False, True])
@pytest.mark.parametrize("owner,expected", [("서윤하", "서하린"), ("하소리", "김정은")])
def test_bidirectional_context_resolves_only_its_own_mother(preceding, owner, expected):
    data, target = fixture(preceding=preceding, owner=owner)
    before = deepcopy(data)
    row = build(data)[target]
    assert data == before
    assert row.character_id == expected and row.attribution == "certain"
    assert row.subject_name == "어머니" and row.identity_status == "linked"
    link = row.identity_links[0]
    assert link.relative_to == owner
    assert {e.scene_id for e in link.evidence} == {"one", "repair"}
    assert any("그 순서는" in e.quote for e in link.evidence)
    assert any(f"{owner}의 어머니" in e.quote for e in link.evidence)
    assert all(not c.get("aliases") for c in data[1])


@pytest.mark.parametrize(
    "damage",
    [
        "no_scope",
        "no_review_context",
        "no_review_target",
        "uncertain_target",
        "uncertain_extraction",
        "wrong_subject",
        "adjudication_conflict",
        "no_identity_anchor",
        "unknown_owner",
        "different_scene",
        "different_revision",
        "noncontiguous_source",
    ],
)
def test_scope_recovery_requires_both_model_evidence_and_valid_source(damage):
    data, target = fixture()
    _, _, batches, extracts, reviews = data
    row = extracts[1]["observations"][target]
    decision = reviews[1]["decisions"][target]
    if damage == "no_scope":
        extracts[1]["observations"][1]["identity_scope"] = None
    elif damage == "no_review_context":
        decision["e"] = [0]
    elif damage == "no_review_target":
        decision["e"] = [1]
    elif damage == "uncertain_target":
        decision["a"] = "uncertain"
    elif damage == "uncertain_extraction":
        row["a"] = "uncertain"
    elif damage == "wrong_subject":
        decision["c"] = "서윤하"
    elif damage == "adjudication_conflict":
        reviews[1]["adjudications"] = [{**decision, "c": "서윤하"}]
    elif damage == "no_identity_anchor":
        for d in reviews[0]["decisions"]:
            d["a"] = "uncertain"
    elif damage == "unknown_owner":
        extracts[1]["observations"][1]["identity_scope"]["relative_to"] = "없는인물"
    else:
        # Test this source guard directly: invalid provenance is also rejected
        # by materialization, before a final Memory can be returned.
        from prolog_ai.memory.identity_resolution import recover_reviewed_scope

        unit = batches[1]["units"][1]
        if damage == "different_scene":
            unit["scene"] = "other"
        elif damage == "different_revision":
            unit["revision"] = "other"
        else:
            unit["start"] += 20
        known = {p["name"].casefold(): {p["character_id"]} for p in data[1]}
        assert recover_reviewed_scope(batches[1], extracts[1], row, decision, known, {}) is None
        return
    assert build(data)[target].character_id != "서하린"


@pytest.mark.parametrize(
    "gap,target_text",
    [
        ("\n\n", None),
        (" ", '"그 순서는 어머니가 가르쳐 준 것이었다."'),
        (" ", "어머니의 목소리를 흉내 낸 안개가 그 순서를 말했다."),
        (" ", "하소리의 어머니가 그 순서를 가르쳐 주었다."),
    ],
)
def test_no_inheritance_across_paragraph_speaker_impersonation_or_owner_switch(gap, target_text):
    data, target = fixture(gap=gap, target_text=target_text)
    assert build(data)[target].character_id != "서하린"


def test_repaired_record_resolves_without_registering_generic_mother():
    data, target = fixture()
    data[1][:] = [p for p in data[1] if p["name"] != "어머니"]
    assert build(data)[target].character_id == "서하린"
