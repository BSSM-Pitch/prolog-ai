from copy import deepcopy

import pytest

from prolog_ai.memory import compact, repairs
from prolog_ai.memory import compact_wire as wire


def sample():
    roster = [
        {"character_id": name, "name": name, "aliases": []}
        for name in ["서윤하", "서하린", "하소리", "김정은", "어머니"]
    ]
    scenes = [
        {
            "scene_id": "one",
            "revision": "r",
            "order": 1,
            "text": "서윤하의 어머니는 서하린이다. 어머니는 휘파람을 불었다. 하소리의 어머니는 김정은이다. 어머니는 손을 흔들었다. 어머니는 웃었다.",
        }
    ]
    batch = {
        **compact.batch_payload(compact.plan(scenes)[0], roster),
        "allow_partial": True,
        "review_actions": True,
    }
    names = [p["name"] for p in batch["known_people"]]

    def link(unit, owner, canonical, proof):
        return {
            "units": [unit],
            "reference": names.index("어머니"),
            "relative_to": names.index(owner),
            "canonical": names.index(canonical),
            "evidence": proof,
        }

    raw = {
        "people": [],
        "skip": [0, 2],
        "rows": [[u, names.index("어머니"), 1, 0, 0, 1] for u in [1, 3, 4]],
        "identities": [link(1, "서윤하", "서하린", [0, 1]), link(3, "하소리", "김정은", [2, 3])],
    }
    return scenes, roster, batch, raw


def extract(batch, raw):
    return compact.validate_extraction(batch, wire.extraction_response(batch, raw))


def test_registered_mothers_resolve_per_record_without_global_alias_or_roster_edit():
    scenes, roster, batch, raw = sample()
    before = deepcopy(roster)
    e = extract(batch, raw)
    assert [r["c"] for r in e["observations"]] == ["서하린", "김정은", "어머니"]
    assert not e["people"]
    p = compact.verification_payload(batch, e)
    request = wire.verification_request(p)
    assert "identities" not in request
    assert all(set(o) <= {"i", "units", "quote", "context"} for o in request["observations"])
    assert 0 in request["observations"][0]["context"]
    review = {
        "decisions": [
            {
                "i": i,
                "c": name,
                "a": "certain",
                "e": e["observations"][i]["e"],
                "reason": "Independent source check",
            }
            for i, name in enumerate(["어머니", "어머니", "어머니"])
        ],
        "bindings": [],
    }
    memory = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert [o.character_id for o in memory.observations] == ["서하린", "김정은", "어머니"]
    assert roster == before
    assert all(not c.aliases for c in memory.characters)
    check = memory.observations[0].attribution_checks[0]
    assert "서윤하의 어머니 → 서하린" in check.reason
    assert any("서윤하의 어머니는 서하린" in e.quote for e in check.evidence)


def test_identity_disagreement_is_uncertain_without_an_additional_adjudication():
    scenes, roster, batch, raw = sample()
    e = extract(batch, raw)
    review = {
        "decisions": [
            {
                "i": i,
                "c": ["김정은", "서하린", "어머니"][i],
                "a": "certain",
                "e": r["e"],
                "reason": "Unresolved identity",
            }
            for i, r in enumerate(e["observations"])
        ],
        "bindings": [],
    }
    assert compact.ownership_disputes(e, review) == []
    memory = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert [o.attribution for o in memory.observations] == ["uncertain", "uncertain", "certain"]


def test_cropped_identity_citation_can_include_immediately_adjacent_subject():
    _, _, batch, raw = sample()
    raw["identities"][0]["evidence"] = [1]
    e = extract(batch, raw)
    assert e["observations"][0]["c"] == "서하린"
    assert e["observations"][0]["identity"]["evidence"] == [0, 1]
    audit = e["validation_audit"]["wire"]["scoped_identities"][0]
    assert audit["evidence"] == [1]
    assert audit["resolved_evidence"] == [0, 1]


@pytest.mark.parametrize(
    "damage", ["missing_source", "missing_owner", "wrong_owner_id", "conflict"]
)
def test_bad_identity_preserves_raw_subject_and_defers_only_link(damage):
    _, _, batch, raw = sample()
    link = raw["identities"][0]
    raw["rows"][0][1] = link["canonical"]
    original_name = batch["known_people"][link["canonical"]]["name"]
    if damage == "missing_source":
        link["evidence"] = [999]
    elif damage == "missing_owner":
        link["evidence"] = [4]
    elif damage == "wrong_owner_id":
        link["relative_to"] = 999
    else:
        raw["identities"].append({**raw["identities"][1], "units": [1]})
    e = extract(batch, raw)
    assert e["observations"][0]["c"] == original_name
    assert e["observations"][0]["a"] == "certain"
    assert e["observations"][0]["identity"] is None
    assert e["observations"][0]["identity_unresolved"]
    assert e["observations"][0]["e"] == [1]
    assert compact.missing_units(batch, e) == []


def test_combined_repair_remaps_identity_proof_to_original_source():
    _, _, batch, _ = sample()
    # Force a different numbering by excluding the first source unit.
    local = [{**batch, "units": batch["units"][1:], "target_ids": [3]}]
    packed, mapping = repairs.pack("extract", local)
    names = [p["name"] for p in packed["known_people"]]
    raw = {
        "people": [],
        "skip": [],
        "rows": [[2, names.index("어머니"), 1, 0, 0, 1]],
        "identities": [
            {
                "units": [2],
                "reference": names.index("어머니"),
                "relative_to": names.index("하소리"),
                "canonical": names.index("김정은"),
                "evidence": [1, 2],
            }
        ],
    }
    out = repairs.unpack("extract", local, extract(packed, raw), mapping)[0]
    assert out["observations"][0]["c"] == "김정은"
    assert out["observations"][0]["e"] == [3]
    assert out["observations"][0]["identity"]["evidence"] == [2, 3]


@pytest.mark.parametrize("certain", [0, 1])
def test_self_link_cannot_erase_subject_or_upgrade_original_uncertainty(certain):
    scenes, roster, batch, raw = sample()
    before = deepcopy(raw)
    mother = batch["known_people"].index(
        next(p for p in batch["known_people"] if p["name"] == "어머니")
    )
    raw["identities"][0]["canonical"] = mother
    raw["rows"][0][-1] = certain
    supplied = deepcopy(raw)
    e = extract(batch, raw)
    row = e["observations"][0]
    assert row["c"] == "어머니"
    assert row["a"] == ("certain" if certain else "uncertain")
    assert row["identity"] is None and row["identity_unresolved"]
    assert raw == supplied and roster == sample()[1]
    review = {
        "decisions": [
            {"i": i, "c": "어머니", "a": "certain", "e": r["e"], "reason": "독립 판정"}
            for i, r in enumerate(e["observations"])
        ]
    }
    memory = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert memory.observations[0].character_id == ("어머니" if certain else None)
    assert memory.observations[0].attribution == ("certain" if certain else "uncertain")
    assert "연결만 보류" in memory.observations[0].attribution_checks[0].reason
    review["decisions"][0]["c"] = "김정은"
    disagreed = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert disagreed.observations[0].attribution == "uncertain"
    assert before["identities"][0]["canonical"] != mother


@pytest.mark.parametrize("damage", ["owner", "evidence"])
def test_normalized_invalid_identity_keeps_source_record_and_subject(damage):
    _, _, batch, raw = sample()
    e = extract(batch, raw)
    r = e["observations"][0]
    original = deepcopy(r)
    if damage == "owner":
        r["identity"]["relative_to"] = "없는 인물"
    else:
        r["identity"]["evidence"] = [999]
    result = compact.validate_extraction(batch, e)
    repaired = result["observations"][0]
    assert (repaired["c"], repaired["a"], repaired["e"]) == (
        original["c"],
        original["a"],
        original["e"],
    )
    assert repaired["identity"] is None and repaired["identity_unresolved"]
    assert result["validation_audit"]["withheld_identities"]
    assert len(result["observations"]) == len(e["observations"])


def test_repair_mapping_failure_preserves_subject_without_inventing_identity_proof():
    _, _, batch, _ = sample()
    local = [{**batch, "units": batch["units"][1:], "target_ids": [3]}]
    _combined, mappings = repairs.pack("extract", local)
    result = {
        "people": [],
        "observations": [
            {
                "c": "김정은",
                "e": [2],
                "x": [],
                "k": "action",
                "p": "depicted",
                "b": "other",
                "a": "certain",
                "to": [],
                "identity": {"reference": "어머니", "relative_to": "하소리", "evidence": [999]},
            }
        ],
        "covered_units": [2],
        "skipped_units": [],
    }
    original = deepcopy(result)
    row = repairs.unpack("extract", local, result, mappings)[0]["observations"][0]
    assert result == original
    assert row["c"] == "김정은" and row["a"] == "certain"
    assert row["identity"] is None and row["identity_unresolved"]
    assert row["e"] == [3]
