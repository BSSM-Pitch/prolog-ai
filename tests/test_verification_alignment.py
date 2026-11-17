"""Recover systematic source-index drift, not arbitrary model disagreements."""

from copy import deepcopy

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory.verification_alignment import realign


def fixture():
    scenes = [
        {"scene_id": "s", "revision": "r", "order": 1, "text": "\n".join(["같은 말이다."] * 8)}
    ]
    payload = {
        **compact.plan(scenes)[0],
        "people": ["가", "나"],
        "alias_names": [],
        "observations": [{"i": i, "e": [i], "kind": "speech"} for i in range(8)],
    }
    review = {
        "decisions": [
            {"i": i, "c": "가", "a": "certain", "e": [(i + 2) % 8], "reason": "원문 판정"}
            for i in range(8)
        ]
    }
    return payload, review


def test_realign_by_coordinates_without_extracted_names_and_without_more_requests():
    p, raw = fixture()
    original = deepcopy(raw)
    result = realign(p, raw)
    assert raw == original
    assert [d["c"] for d in result["decisions"]] == [None, None] + ["가"] * 6
    for i, d in enumerate(result["decisions"][2:], 2):
        assert d["e"] == [i]
    assert result["validation_audit"]["source_alignment"]["original_decisions"] == raw["decisions"]
    assert compact.missing_verifications(p, result) == []
    assert realign(p, result) == result
    compact.check("verify", p, result)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_short_context_citations_are_not_relocated(count):
    p, raw = fixture()
    raw["decisions"] = raw["decisions"][:count]
    assert realign(p, raw) == raw


def test_direct_conflicting_review_is_not_overwritten():
    p, raw = fixture()
    raw["decisions"][6].update(c="나", e=[6])
    result = realign(p, raw)
    assert result["decisions"][6]["c"] is None
    assert result["decisions"][6]["a"] == "uncertain"
    assert result["validation_audit"]["source_alignment"]["withheld"]


def test_duplicate_source_targets_do_not_gain_arbitrary_assignment():
    p, raw = fixture()
    p["observations"] += [{"i": 8 + i, "e": [i], "kind": "action"} for i in range(8)]
    assert realign(p, raw) == raw


def test_overlap_is_not_mistaken_for_a_disjoint_record():
    p, raw = fixture()
    for i, o in enumerate(p["observations"][:6]):
        o["e"] = [i, i + 1, i + 2]
    assert realign(p, raw) == raw


def test_reason_stays_within_schema_limit():
    p, raw = fixture()
    for d in raw["decisions"]:
        d["reason"] = "가" * 160
    compact.check("verify", p, realign(p, raw))


@pytest.mark.parametrize(
    "third_name,refs,expected",
    [
        ("가", [1, 2], "가"),
        ("나", [1, 2], "나"),
        ("다", [1, 2], None),
        ("가", [0], None),
    ],
)
def test_targeted_review_supports_either_candidate_only_with_direct_evidence(
    third_name, refs, expected
):
    scenes = [
        {
            "scene_id": "s",
            "revision": "r",
            "order": 1,
            "text": "가와 나와 다가 있었다. 손이 떨렸다. 가는 그래도 걸었다.",
        }
    ]
    people = [{"name": n, "character_id": n} for n in ["가", "나", "다"]]
    batch = {**compact.batch_payload(compact.plan(scenes)[0], people), "review_actions": True}
    extraction = {
        "people": [],
        "observations": [
            {
                "c": "가",
                "e": [1],
                "x": [0],
                "k": "inner_thought",
                "p": "thought",
                "b": "other",
                "a": "certain",
                "to": [],
            }
        ],
        "covered_units": [0, 1, 2],
        "skipped_units": [0, 2],
    }
    review = {
        "decisions": [{"i": 0, "c": "나", "a": "certain", "e": [1], "reason": "독립검증"}],
        "adjudications": [
            {"i": 0, "c": third_name, "a": "certain", "e": refs, "reason": "기존 재검토"}
        ],
    }
    memory = compact.build_memory(
        "p", scenes, people, [batch], [extraction], [review], model="offline"
    )
    assert memory.observations[0].character_id == expected
    assert memory.observations[0].attribution == ("certain" if expected else "uncertain")


def test_extra_context_naming_only_the_other_candidate_does_not_restore_extraction():
    from prolog_ai.memory.verification_alignment import adds_candidate_context

    p, _ = fixture()
    p["units"][2]["text"] = "나의 행동이었다."
    p["units"][2]["end"] = p["units"][2]["start"] + len(p["units"][2]["text"])
    assert not adds_candidate_context(p, "가", {"e": [1]}, {"e": [1, 2]})


def test_ambiguous_short_name_is_not_new_identifying_context():
    from prolog_ai.memory.verification_alignment import adds_candidate_context

    p, _ = fixture()
    p["known_people"] = [{"name": "서민서"}, {"name": "강민서"}]
    p["units"][2]["text"] = "민서는 계속 걸었다."
    p["units"][2]["end"] = p["units"][2]["start"] + len(p["units"][2]["text"])
    assert not adds_candidate_context(p, "서민서", {"e": [1]}, {"e": [1, 2]})


def test_targeted_review_can_replace_irrelevant_tail_with_identifying_context():
    from prolog_ai.memory.verification_alignment import adds_candidate_context

    scenes = [
        {
            "scene_id": "s",
            "revision": "r",
            "order": 1,
            "text": "민서는 사다리를 올랐다. 높은 곳은 무서웠다. 바람이 불었다.",
        }
    ]
    payload = compact.plan(scenes)[0]
    assert adds_candidate_context(payload, "민서", {"e": [1, 2]}, {"e": [0, 1]})
    assert not adds_candidate_context(payload, "민서", {"e": [1, 2]}, {"e": [0]})
    assert not adds_candidate_context(payload, "민서", {"e": [1, 2]}, {"e": [1, 2]})
