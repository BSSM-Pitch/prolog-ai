"""First-upload entity resolution using only this run's independent decisions."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.memory import compact, compact_wire
from prolog_ai.memory.source import validate_memory


def unpack(scene, people, rows, identities=()):
    batch = {
        **compact.plan([scene])[0],
        "known_people": [],
        "allow_partial": True,
        "review_actions": True,
    }
    raw = {"people": people, "rows": rows, "skip": [], "identities": list(identities)}
    return batch, compact.validate_extraction(batch, compact_wire.extraction_response(batch, raw))


def named_fixture(full="한민서", short="민서"):
    scenes = [
        {
            "scene_id": "a",
            "revision": "r",
            "order": 1,
            "text": f"{full}가 걸었다. {short}는 웃었다.",
        },
        {"scene_id": "b", "revision": "r", "order": 2, "text": f"{short}는 손을 떨었다."},
    ]
    batches, extracts = [], []
    for index, scene in enumerate(scenes):
        people = (
            [{"name": short, "alias": -1, "u": 0}]
            if index
            else [{"name": full, "alias": -1, "u": 0}, {"name": short, "alias": -1, "u": 1}]
        )
        rows = [[0, 0, 1, 0, 0, 1]] if index else [[0, 0, 1, 0, 0, 1], [1, 1, 1, 0, 0, 1]]
        b, e = unpack(scene, people, rows)
        batches.append(b)
        extracts.append(e)
    assert all(b["known_people"] == [] for b in batches)
    batches = compact.share_discovered_people(batches, extracts)
    reviews = [
        {
            "decisions": [
                {"i": i, "c": row["c"], "a": "certain", "e": row["e"], "reason": "원문 검증"}
                for i, row in enumerate(e["observations"])
            ],
            "bindings": [
                {
                    "name": short,
                    "canonical": full if index == 0 else short,
                    "e": 1 if index == 0 else 0,
                }
            ],
        }
        for index, e in enumerate(extracts)
    ]
    return scenes, [{"character_id": "person", "name": full}], batches, extracts, reviews


def build(data):
    scenes, roster, batches, extracts, reviews = data
    with patch.object(compact, "call_llm", side_effect=AssertionError("No AI calls")):
        memory = compact.build_memory(
            "p", scenes, roster, batches, extracts, reviews, model="offline"
        )
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    return memory


@pytest.mark.parametrize("full,short", [("한민서", "민서"), ("장태오", "태오"), ("이서진", "서진")])
def test_cold_upload_shares_grounded_name_link_despite_self_link_elsewhere(full, short):
    data = named_fixture(full, short)
    before = deepcopy(data)
    memory = build(data)
    assert data == before
    assert all(
        o.character_id == "person" and o.attribution == "certain" for o in memory.observations
    )
    target = memory.observations[-1]
    assert target.subject_name == short and target.subject_attribution == "certain"
    assert target.identity_status == "linked"
    assert target.identity_links[0].canonical == full
    assert {e.scene_id for e in target.identity_links[0].evidence} == {"a"}
    assert not memory.characters[0].aliases  # Do not mutate author-owned facts.


@pytest.mark.parametrize(
    "damage",
    [
        "no_binding",
        "self_only",
        "competing_full_name",
        "distinct_registered_short",
        "conflicting_vote",
    ],
)
def test_no_suffix_guessing_and_recognized_subject_survives_unlinked_identity(damage):
    data = named_fixture()
    _, roster, batches, _, reviews = data
    if damage == "no_binding":
        reviews[0]["bindings"][0]["canonical"] = None
    elif damage == "self_only":
        reviews[0]["bindings"][0]["canonical"] = "민서"
    elif damage == "competing_full_name":
        roster.append({"character_id": "other", "name": "김민서"})
    elif damage == "distinct_registered_short":
        roster.append({"character_id": "other", "name": "민서"})
    else:
        for b in batches:
            b["known_people"].append({"name": "김민서", "aliases": []})
        reviews[1]["bindings"][0]["canonical"] = "김민서"
    target = build(data).observations[-1]
    assert target.character_id != "person"
    assert target.subject_name == "민서" and target.subject_attribution == "certain"
    if damage != "distinct_registered_short":
        assert target.character_id is None and target.identity_status == "unlinked"
        assert "주체 판정 일치" in target.attribution_checks[1].reason


def test_link_pool_is_snapshot_local_and_order_independent():
    data = named_fixture()
    scenes, roster, batches, extracts, reviews = data
    reverse = build((scenes, roster, batches[::-1], extracts[::-1], reviews[::-1]))
    assert all(o.character_id == "person" for o in reverse.observations)
    isolated = build((scenes[1:], roster, batches[1:], extracts[1:], reviews[1:]))
    assert isolated.observations[0].character_id is None


def relation_fixture(gap=" ", middle="", long_proof=False):
    first = {
        "scene_id": "remember",
        "revision": "r",
        "order": 1,
        "text": "한민서는 어머니를 떠올렸다."
        + gap
        + middle
        + "늘 먼저 휘파람을 부르던 버릇이었다.",
    }
    b, e = unpack(
        first,
        [{"name": "한민서", "alias": -1, "u": 0}, {"name": "어머니", "alias": -1, "u": 0}],
        [[0, 0, 2, 3, 0, 1], [1, 1, 3, 2, 0, 1]],
        [{"units": [0], "reference": 1, "relative_to": 0, "canonical": 1, "evidence": [0]}],
    )
    second = {
        "scene_id": "identity",
        "revision": "r",
        "order": 2,
        "text": "한민서의 엄마는 김다은이었다. "
        + ("기록이 남아 있었다. " * 6 if long_proof else "")
        + "엄마는 웃었다.",
    }
    last = 7 if long_proof else 1
    b2, e2 = unpack(
        second,
        [{"name": n, "alias": -1, "u": 0} for n in ["한민서", "엄마", "김다은"]],
        [[u, 1, 1, 0, 0, 1] for u in range(last + 1)],
        [
            {
                "units": list(range(last + 1)),
                "reference": 1,
                "relative_to": 0,
                "canonical": 2,
                "evidence": list(range(last + 1)),
            }
        ],
    )
    batches = compact.share_discovered_people([b, b2], [e, e2])
    reviews = [
        {
            "decisions": [
                {"i": i, "c": name, "a": "certain", "e": row["e"], "reason": "원문 검증"}
                for i, (row, name) in enumerate(zip(ext["observations"], names, strict=True))
            ],
            "bindings": [],
        }
        for ext, names in [(e, ["한민서", "어머니"]), (e2, ["엄마"] * (last + 1))]
    ]
    roster = [{"character_id": n, "name": n} for n in ["한민서", "김다은"]]
    return [first, second], roster, batches, [e, e2], reviews


@pytest.mark.parametrize("long_proof", [False, True])
def test_cold_role_scope_survives_owner_mention_and_joins_mom_synonym(long_proof):
    memory = build(relation_fixture(long_proof=long_proof))
    target = memory.observations[1]
    assert target.subject_name == "어머니"
    assert target.character_id == "김다은" and target.attribution == "certain"
    link = target.identity_links[0]
    assert link.relative_to == "한민서" and link.reference == "어머니"
    assert {e.scene_id for e in link.evidence} == {"remember", "identity"}
    if long_proof:
        assert len(link.evidence) == 9  # Previously discarded by the 8-unit cap.


@pytest.mark.parametrize(
    "damage", ["paragraph", "no_scope", "wrong_owner", "unreviewed_anchor", "uncertain_target"]
)
def test_role_scope_is_not_a_global_mother_alias(damage):
    data = relation_fixture(gap="\n\n" if damage == "paragraph" else " ")
    if damage == "no_scope":
        data[3][0]["observations"][1]["identity_scope"] = None
    if damage == "wrong_owner":
        data[3][0]["observations"][1]["identity_scope"]["relative_to"] = "김다은"
    if damage == "unreviewed_anchor":
        for d in data[4][1]["decisions"]:
            d.update(c=None, a="uncertain")
    if damage == "uncertain_target":
        data[4][0]["decisions"][1].update(c=None, a="uncertain")
    target = build(data).observations[1]
    assert target.character_id is None
    assert target.subject_name == "어머니"


@pytest.mark.parametrize(
    "middle", ["지훈은 고개를 들었다.", "아버지는 고개를 들었다.", "“그랬구나.”"]
)
def test_adjacent_role_scope_stops_at_short_name_role_or_dialogue_switch(middle):
    scene = {
        "scene_id": "s",
        "revision": "r",
        "order": 1,
        "text": f"한민서는 어머니를 떠올렸다. {middle} 늘 먼저 휘파람을 부르던 버릇이었다.",
    }
    batch = compact.plan([scene])[0]
    scopes = {(0, "어머니"): {"reference": "어머니", "relative_to": "한민서", "evidence": [0]}}
    assert (
        compact_wire.adjacent_identity_scope(
            batch, scopes, ["한민서", "박지훈", "어머니"], 2, "어머니"
        )
        is None
    )


def test_identity_link_source_quotes_are_validated_and_legacy_memory_still_loads():
    memory = build(named_fixture()).model_dump()
    damaged = deepcopy(memory)
    damaged["observations"][-1]["identity_links"][0]["evidence"][0]["quote"] = "만들어 낸 근거"
    from prolog_ai.core.runner import InputValidationError

    with pytest.raises(InputValidationError):
        validate_memory(damaged, require_complete=True)
    for row in memory["observations"]:
        for field in ("subject_name", "subject_attribution", "identity_status", "identity_links"):
            row.pop(field)
    validate_memory(memory, require_complete=True)
