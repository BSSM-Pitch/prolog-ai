"""Existing relationship decisions can cross batches, never unrelated owners."""

from copy import deepcopy

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory.source import validate_memory
from tests.test_scoped_identities import extract, sample


def fixture():
    scenes, roster, anchor, raw = sample()
    first = extract(anchor, raw)
    target = {
        "scene_id": "target",
        "revision": "r",
        "order": 2,
        "text": "서윤하는 어머니를 떠올렸다. 어머니는 휘파람을 불었다. 하소리는 어머니를 떠올렸다. 어머니는 손을 흔들었다. 어머니는 웃었다.",
    }
    batch = {
        **compact.batch_payload(compact.plan([target])[0], roster),
        "allow_partial": True,
        "review_actions": True,
    }
    names = [p["name"] for p in batch["known_people"]]
    mother = names.index("어머니")
    raw2 = {
        "people": [],
        "skip": [0, 2],
        "rows": [[n, mother, 1, 0, 0, 1] for n in (1, 3, 4)],
        "identities": [
            {
                "units": [n],
                "reference": mother,
                "canonical": mother,
                "relative_to": names.index(owner),
                "evidence": [proof],
            }
            for n, owner, proof in [(1, "서윤하", 0), (3, "하소리", 2)]
        ],
    }
    second = extract(batch, raw2)

    def review(e):
        return {
            "decisions": [
                {"i": i, "c": "어머니", "a": "certain", "e": r["e"], "reason": "원문 독립 검증"}
                for i, r in enumerate(e["observations"])
            ]
        }

    return (
        scenes + [target],
        roster,
        [anchor, batch],
        [first, second],
        [review(first), review(second)],
    )


def build(data):
    scenes, roster, batches, extracts, reviews = data
    memory = compact.build_memory("p", scenes, roster, batches, extracts, reviews, model="offline")
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    return memory


def test_scoped_identity_reuses_reviewed_anchor_and_retains_both_source_proofs():
    data = fixture()
    before = deepcopy(data)
    memory = build(data)
    assert data == before
    target = [o for o in memory.observations if o.evidence.scene_id == "target"]
    assert [o.character_id for o in target] == ["서하린", "김정은", "어머니"]
    check = target[0].attribution_checks[0]
    assert check.name == "어머니" and check.character_id == "서하린"
    assert "기존 검증 연결 재사용" in check.reason
    assert {e.scene_id for e in check.evidence} == {"one", "target"}
    assert any("서윤하의 어머니는 서하린" in e.quote for e in check.evidence)
    assert all(not c.aliases for c in memory.characters)


@pytest.mark.parametrize(
    "damage",
    [
        "anchor_uncertain",
        "target_uncertain",
        "target_disagrees",
        "extract_uncertain",
        "no_scope",
        "unknown_owner",
        "bad_evidence",
        "competing_anchor",
    ],
)
def test_ambiguous_or_unreviewed_identity_cannot_cross_batch(damage):
    data = fixture()
    scenes, _roster, batches, extracts, reviews = data
    if damage == "anchor_uncertain":
        reviews[0]["decisions"][0].update(c=None, a="uncertain")
    elif damage == "target_uncertain":
        reviews[1]["decisions"][0].update(c=None, a="uncertain")
    elif damage == "target_disagrees":
        reviews[1]["decisions"][0]["c"] = "하소리"
    elif damage == "extract_uncertain":
        extracts[1]["observations"][0]["a"] = "uncertain"
    elif damage == "no_scope":
        extracts[1]["observations"][0]["identity_scope"] = None
    elif damage in ("unknown_owner", "bad_evidence"):
        scope = extracts[1]["observations"][0]["identity_scope"]
        scope.update(
            {"relative_to": "없는인물"} if damage == "unknown_owner" else {"evidence": [999]}
        )
        extracts[1] = compact.validate_extraction(batches[1], extracts[1])
    else:
        # A second independently reviewed canonical identity for the SAME owner
        # blocks reuse instead of choosing the first candidate.
        other = deepcopy(batches[0])
        other["units"] = [{**u, "scene": "contradictory", "order": 3} for u in other["units"]]
        scene = {**scenes[0], "scene_id": "contradictory", "order": 3}
        scene["text"] = scene["text"].replace("서하린", "김정은")
        for u in other["units"]:
            u["text"] = u["text"].replace("서하린", "김정은")
        extra = deepcopy(extracts[0])
        extra["observations"][0]["c"] = "김정은"
        scenes.append(scene)
        batches.append(other)
        extracts.append(extra)
        reviews.append(deepcopy(reviews[0]))
    memory = build(data)
    row = next(o for o in memory.observations if o.evidence.scene_id == "target")
    assert row.character_id != "서하린"
    assert "기존 검증 연결 재사용" not in row.attribution_checks[0].reason


def test_duplicate_role_ids_are_self_link_by_name_not_a_new_canonical_identity():
    _, _, batch, raw = sample()
    names = [p["name"] for p in batch["known_people"]]
    raw["people"] = [{"name": "어머니", "alias": names.index("어머니"), "u": 1}]
    raw["identities"][0]["reference"] = len(names)
    raw["identities"][0]["canonical"] = names.index("어머니")
    raw["rows"][0][1] = len(names)
    result = extract(batch, raw)
    row = result["observations"][0]
    assert row["c"] == "어머니" and row["a"] == "certain"
    assert row["identity"] is None
    assert row["identity_scope"]["relative_to"] == "서윤하"
    assert row["identity_unresolved"]
