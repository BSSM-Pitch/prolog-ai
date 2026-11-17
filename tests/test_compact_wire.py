from copy import deepcopy

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory import compact_wire as wire
from prolog_ai.memory.source import encode, validate_memory


def setup(text="윤하는 손을 떨었다. “미안해.”", roster=None):
    scenes = [{"scene_id": "s", "revision": "r", "order": 1, "text": text}]
    roster = roster or [{"character_id": "a", "name": "서윤하", "aliases": []}]
    batch = {**compact.batch_payload(compact.plan(scenes)[0], roster), "allow_partial": True}
    return scenes, roster, batch


def unpack(batch, rows, people=None, skip=None):
    return compact.validate_extraction(
        batch,
        wire.extraction_response(
            batch,
            {
                "people": people or [],
                "rows": rows,
                "skip": skip or [],
            },
        ),
    )


def test_sentence_rows_preserve_small_details_without_reprinting_source():
    scenes, roster, batch = setup()
    raw = {"people": [], "rows": [[0, 0, 1, 0, 4, 1], [1, 0, 0, 0, 0, 1]], "skip": []}
    extracted = compact.validate_extraction(batch, wire.extraction_response(batch, raw))
    assert not compact.missing_units(batch, extracted)
    p = compact.verification_payload(batch, extracted)
    review = compact.validate_verification(
        p, wire.verification_response(p, {"rows": [[1, 0, 0, 1]], "links": []})
    )
    memory = compact.build_memory("p", scenes, roster, [batch], [extracted], [review], model="test")
    assert len(memory.observations) == 2
    assert [o.evidence.quote for o in memory.observations] == ["윤하는 손을 떨었다.", " “미안해.”"]
    assert "미안해" not in encode(raw)
    assert len(encode(raw)) < len(encode(extracted)) / 3
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)


@pytest.mark.parametrize("known_count,alias", [(0, 0), (0, 99), (1, 1), (1, 99)])
def test_invalid_alias_preserves_literal_subject_and_paid_observations(known_count, alias):
    _, _, batch = setup("민서가 걸었다. 민서는 고개를 들었다.")
    batch["known_people"] = [{"name": "지훈", "aliases": []}][:known_count]
    person = {"name": "민서", "kind": "ambiguous", "alias": alias, "u": 0}
    raw = {
        "people": [person],
        "rows": [[u, known_count, 1, 0, 0, 1] for u in batch["target_ids"]],
        "skip": [],
    }
    extracted = compact.validate_extraction(batch, wire.extraction_response(batch, raw))
    assert extracted["people"][0]["alias_of"] is None
    assert extracted["people"][0]["kind"] == "ambiguous"
    assert all(r["c"] == "민서" and r["a"] == "certain" for r in extracted["observations"])
    assert not compact.missing_units(batch, extracted)
    assert extracted["validation_audit"]["wire"]["invalid_aliases"] == [person]


def test_claimed_coverage_cannot_hide_an_unrecorded_tail_and_repair_preserves_prefix():
    _, _, batch = setup("윤하는 걸었다. 윤하는 숨을 삼켰다. “미안해.”")
    first = unpack(batch, [[0, 0, 1, 0, 0, 1]])
    first["covered_units"] = batch["target_ids"]  # Reproduce the old false all-read list.
    assert compact.missing_units(batch, first) == [1, 2]
    repair_batch = compact.repair_payload(batch, [1, 2])
    repair = unpack(repair_batch, [[1, 0, 1, 0, 4, 1], [2, 0, 0, 0, 0, 1]])
    merged = compact.merge_extractions(batch, first, repair)
    assert merged["observations"][0] == first["observations"][0]
    assert not compact.missing_units(batch, merged)
    incomplete = unpack(repair_batch, [[1, 0, 1, 0, 4, 1]])
    with pytest.raises(ValueError, match="coverage incomplete"):
        compact.merge_extractions(batch, first, incomplete)


def test_required_detail_hints_cover_repair_targets_without_silently_skipping_others():
    _, _, batch = setup("윤하는 손을 떨었다. 밤이었다. “미안해.”")
    request = wire.extraction_request(batch)
    assert request["must_record_ids"] == [0, 2]
    assert request["new_person_start"] == len(batch["known_people"])
    assert request["target_ids"] == [0, 1, 2]
    repair = compact.repair_payload(batch, [2])
    hint = wire.extraction_request(repair)
    assert hint["must_record_ids"] == [2]  # Context still contains the trembling hand.
    assert len(hint["units"]) == 3
    skipped = unpack(batch, [], skip=[0, 1, 2])
    assert compact.missing_units(batch, skipped) == [0, 2]
    omitted = unpack(batch, [[0, 0, 1, 0, 4, 1], [2, 0, 0, 0, 0, 1]])
    assert compact.missing_units(batch, omitted) == [1]


def test_explicit_dialogue_and_habit_cannot_be_marked_as_background():
    _, _, batch = setup("윤하는 먼저 휘파람을 부는 버릇이 있었다. “안녕.”")
    output = unpack(batch, [], skip=batch["target_ids"])
    assert compact.missing_units(batch, output) == batch["target_ids"]


def test_overlapping_skip_never_erases_an_actual_record():
    _, _, batch = setup()
    output = unpack(batch, [[0, 0, 1, 0, 4, 1], [1, 0, 0, 0, 0, 1]], skip=[0, 0])
    assert len(output["observations"]) == 2
    assert output["skipped_units"] == []
    assert not compact.missing_units(batch, output)
    assert output["validation_audit"]["wire"]["overlapping_skips"] == [0]
    assert output["validation_audit"]["wire"]["duplicate_skips"] == 1


def test_repair_context_is_retained_for_audit_without_duplicate_extraction():
    _, _, batch = setup()
    repair = compact.repair_payload(batch, [1])
    output = unpack(repair, [[0, 0, 1, 0, 4, 1], [1, 0, 0, 0, 0, 1]])
    assert [r["e"] for r in output["observations"]] == [[1]]
    assert output["validation_audit"]["wire"]["context_only_rows"] == [[0, 0, 1, 0, 4, 1]]
    assert not compact.missing_units(repair, output)


@pytest.mark.parametrize("confirmed,expected", [("서윤하", "a"), (None, None)])
def test_alias_needs_independent_agreement_and_does_not_change_author_roster(confirmed, expected):
    scenes, roster, batch = setup()
    extracted = unpack(
        batch,
        [[0, 1, 1, 0, 4, 1], [1, 1, 0, 0, 0, 1]],
        people=[{"name": "윤하", "alias": 0, "u": 0}],
    )
    p = compact.verification_payload(batch, extracted)
    # The verifier sees names, but not the extractor's alias target or speakers.
    request = wire.verification_request(p)
    assert "alias_of" not in encode(request)
    review = {
        "decisions": [{"i": 1, "c": "서윤하", "a": "certain", "e": [0, 1], "reason": "발화 지문"}],
        "bindings": [{"name": "윤하", "canonical": confirmed, "e": 0}],
    }
    before = deepcopy(roster)
    memory = compact.build_memory("p", scenes, roster, [batch], [extracted], [review], model="test")
    assert memory.observations[0].character_id == expected
    assert memory.observations[1].character_id == expected
    assert roster == before and not memory.characters[0].aliases


def test_same_short_name_with_competing_full_names_stays_unresolved():
    roster = [{"character_id": "a", "name": "서윤하"}, {"character_id": "b", "name": "김윤하"}]
    scenes, roster, batch = setup(roster=roster)
    known = [c["name"] for c in batch["known_people"]]
    extracted = unpack(
        batch,
        [[0, 2, 1, 0, 4, 1]],
        people=[{"name": "윤하", "alias": known.index("서윤하"), "u": 0}],
        skip=[1],
    )
    review = {"decisions": [], "bindings": [{"name": "윤하", "canonical": "서윤하", "e": 0}]}
    memory = compact.build_memory("p", scenes, roster, [batch], [extracted], [review], model="test")
    assert memory.observations[0].character_id is None


def test_bad_indices_and_foreign_link_evidence_are_rejected():
    _, _, batch = setup()
    invalid = unpack(batch, [[0, 99, 1, 0, 0, 1]])
    assert invalid["observations"] == []
    assert compact.missing_units(batch, invalid) == batch["target_ids"]
    assert invalid["validation_audit"]["wire"]["invalid_code_rows"] == [[0, 99, 1, 0, 0, 1]]
    extracted = unpack(
        batch, [[0, 1, 1, 0, 0, 1]], people=[{"name": "윤하", "alias": 0, "u": 0}], skip=[1]
    )
    p = compact.verification_payload(batch, extracted)
    with pytest.raises(ValueError, match="identity binding"):
        compact.check(
            "verify",
            p,
            {"decisions": [], "bindings": [{"name": "윤하", "canonical": "서윤하", "e": 1}]},
        )


def test_global_compaction_preserves_all_prose_ids_and_pattern_candidates():
    observations = [
        {
            "i": i,
            "c": 0,
            "order": 1,
            "k": "action",
            "p": "depicted",
            "b": "other",
            "quote": "손이 떨렸다.",
            "context": "대답하기 직전",
        }
        for i in (4, 7)
    ]
    source = {
        "characters": [{"i": 0, "name": "서윤하"}],
        "observations": observations,
        "proposals": [{"seeds": [4, 7]}],
    }
    packed = wire.synthesis_request(source)
    assert len(packed["texts"]) == 2
    assert [row[0] for row in packed["rows"]] == [4, 7]
    for row, original in zip(packed["rows"], observations, strict=True):
        assert packed["texts"][row[6]] == original["quote"]
        assert " ".join(packed["texts"][i] for i in row[7]) == original["context"]
    assert packed["proposals"] == source["proposals"]


def test_remembered_habit_owner_requires_two_independent_confirmations():
    roster = [{"character_id": "a", "name": "서윤하"}, {"character_id": "b", "name": "서하린"}]
    scenes, roster, batch = setup(
        "서윤하는 서하린을 떠올렸다. 서하린은 먼저 휘파람을 부는 버릇이 있었다.", roster
    )
    batch["review_actions"] = True
    e = unpack(batch, [[0, 0, 2, 3, 2, 1], [1, 0, 3, 2, 0, 1]])
    review = {
        "decisions": [
            {"i": 0, "c": "서윤하", "a": "certain", "e": [0], "reason": "회상 주체"},
            {"i": 1, "c": "서하린", "a": "certain", "e": [1], "reason": "습관 주체"},
        ],
        "bindings": [],
    }
    assert compact.ownership_disputes(e, review) == [1]
    memory = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert memory.observations[1].character_id is None
    review["adjudications"] = [deepcopy(review["decisions"][1])]
    memory = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert memory.observations[0].character_id == "a"
    assert memory.observations[1].character_id == "b"
    assert not memory.speaker_verifications  # Action checks are not speech checks.
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    review["adjudications"][0]["c"] = "서윤하"
    uncertain = compact.build_memory("p", scenes, roster, [batch], [e], [review], model="test")
    assert uncertain.observations[1].character_id is None


def test_context_skip_is_audited_but_never_counts_as_target_coverage():
    _, _, batch = setup()
    batch["target_ids"] = [0]
    extracted = unpack(batch, [[0, 0, 1, 0, 4, 1]], skip=[1])
    assert extracted["covered_units"] == [0]
    assert extracted["skipped_units"] == []
    assert extracted["validation_audit"]["wire"]["context_only_skips"] == [1]
    missing = unpack(batch, [], skip=[1])
    assert compact.missing_units(batch, missing) == [0]
    with pytest.raises(ValueError, match="outside supplied source"):
        unpack(batch, [], skip=[999])


def test_invalid_review_range_keeps_record_but_never_confirms_owner():
    _, _, batch = setup()
    extracted = unpack(batch, [[0, 0, 0, 0, 0, 1]], skip=[1])
    payload = compact.verification_payload(batch, extracted)
    raw = {"rows": [[0, 0, 0, 15]], "links": []}
    reviewed = compact.validate_verification(payload, wire.verification_response(payload, raw))
    assert reviewed["decisions"][0]["c"] is None
    assert reviewed["decisions"][0]["a"] == "uncertain"
    assert reviewed["decisions"][0]["e"] == [0]
    assert reviewed["validation_audit"]["invalid_proof_rows"] == raw["rows"]


def test_proof_length_expands_exactly_and_invalid_length_requires_repair():
    _, _, batch = setup("윤하는 걸었다. 윤하는 숨을 골랐다. “미안해.”")
    extracted = unpack(batch, [[2, 0, 0, 0, 0, 1]], skip=[0, 1])
    payload = {**compact.verification_payload(batch, extracted), "allow_partial": True}
    assert wire.verification_request(payload)["chapter_ranges"] == [[0, 2]]
    raw = {"rows": [[0, 0, 1, 2]], "links": []}
    review = compact.validate_verification(
        payload, wire.verification_response(payload, raw, proof_lengths=True)
    )
    assert review["decisions"][0]["e"] == [1, 2]
    assert compact.missing_verifications(payload, review) == []
    for length in (0, 9):
        raw = {"rows": [[0, 0, 1, length]], "links": []}
        review = compact.validate_verification(
            payload, wire.verification_response(payload, raw, proof_lengths=True)
        )
        assert review["decisions"][0]["c"] is None
        assert compact.missing_verifications(payload, review) == [0]


def test_alias_self_link_is_unconfirmed_instead_of_registering_itself():
    _, _, batch = setup()
    extracted = unpack(
        batch, [[0, 1, 0, 0, 0, 1]], people=[{"name": "윤하", "alias": 0, "u": 0}], skip=[1]
    )
    payload = compact.verification_payload(batch, extracted)
    alias = payload["people"].index("윤하")
    raw = {"rows": [[0, alias, 0, 0]], "links": [[alias, alias, 0]]}
    reviewed = compact.validate_verification(payload, wire.verification_response(payload, raw))
    assert reviewed["bindings"][0]["canonical"] is None
    assert reviewed["validation_audit"]["unresolved_bindings"][0]["canonical"] == "윤하"


def test_alias_wrong_literal_proof_is_unconfirmed_with_original_link_audited():
    _, _, batch = setup()
    extracted = unpack(
        batch, [[0, 1, 0, 0, 0, 1]], people=[{"name": "윤하", "alias": 0, "u": 0}], skip=[1]
    )
    payload = compact.verification_payload(batch, extracted)
    alias = payload["people"].index("윤하")
    canonical = payload["people"].index("서윤하")
    raw = {"rows": [[0, canonical, 0, 0]], "links": [[alias, canonical, 1]]}
    reviewed = compact.validate_verification(payload, wire.verification_response(payload, raw))
    assert reviewed["bindings"][0] == {"name": "윤하", "canonical": None, "e": 0}
    assert reviewed["validation_audit"]["unresolved_bindings"][0]["e"] == 1


def test_partial_verification_repairs_missing_and_bad_proof_without_repeating_good_rows():
    _, _, batch = setup("윤하는 손을 떨었다. 윤하는 숨을 골랐다. 윤하는 돌아섰다.")
    batch["review_actions"] = True
    extracted = unpack(batch, [[i, 0, 1, 0, 0, 1] for i in range(3)])
    payload = {**compact.verification_payload(batch, extracted), "allow_partial": True}
    review = compact.validate_verification(
        payload,
        wire.verification_response(
            payload, {"rows": [[0, 0, 0, 0], [1, 0, 999, 999]], "links": []}
        ),
    )
    assert compact.missing_verifications(payload, review) == [1, 2]
    with pytest.raises(ValueError, match="Missing or duplicate"):
        compact.check("verify", {**payload, "allow_partial": False}, review)
    repair_payload = compact.verification_repair_payload(payload, [1, 2])
    assert [o["i"] for o in repair_payload["observations"]] == [1, 2]
    assert repair_payload["units"] == payload["units"]
    repaired = compact.validate_verification(
        repair_payload,
        wire.verification_response(
            repair_payload, {"rows": [[1, 0, 1, 1], [2, 0, 2, 2]], "links": []}
        ),
    )
    merged = compact.merge_verifications(payload, review, repaired)
    assert merged["decisions"][0] == review["decisions"][0]
    assert [d["i"] for d in merged["decisions"]] == [0, 1, 2]
    assert all(d["a"] == "certain" for d in merged["decisions"])
    with pytest.raises(ValueError, match="exactly"):
        compact.merge_verifications(payload, review, {"decisions": []})


def test_bad_classification_is_repaired_without_guessing_or_losing_valid_rows():
    _, _, batch = setup()
    bad = [0, 0, 2, 5, 5, 1]
    extracted = unpack(batch, [[0, 0, 1, 0, 0, 1], bad], skip=[0, 1])
    assert len(extracted["observations"]) == 1
    assert extracted["validation_audit"]["wire"]["invalid_code_rows"] == [bad]
    assert compact.missing_units(batch, extracted) == [0, 1]
    repair_payload = compact.repair_payload(batch, [0, 1], extracted)
    repaired = unpack(repair_payload, [[0, 0, 2, 3, 5, 1], [1, 0, 0, 0, 0, 1]])
    merged = compact.merge_extractions(batch, extracted, repaired)
    assert len(merged["observations"]) == 3
    assert merged["observations"][0] == extracted["observations"][0]
    assert compact.missing_units(batch, merged) == []
    still_bad = unpack(repair_payload, [bad, [1, 0, 0, 0, 0, 1]])
    with pytest.raises(ValueError, match="coverage incomplete"):
        compact.merge_extractions(batch, extracted, still_bad)
    with pytest.raises(ValueError, match="row source"):
        unpack(batch, [[999, 0, 2, 3, 0, 1]])


@pytest.mark.parametrize("bad", [[0, 99, 1, 0, 0, 1], [0, 0, 1, 0, 0, 1, 99]])
def test_unknown_subject_or_recipient_is_repaired_even_if_unit_was_marked_skipped(bad):
    _, _, batch = setup()
    extracted = unpack(batch, [bad, [1, 0, 0, 0, 0, 1]], skip=[0])
    assert [r["e"] for r in extracted["observations"]] == [[1]]
    assert compact.missing_units(batch, extracted) == [0]
    repair_payload = compact.repair_payload(batch, [0], extracted)
    fixed = unpack(repair_payload, [[0, 0, 1, 0, 0, 1]])
    merged = compact.merge_extractions(batch, extracted, fixed)
    assert compact.missing_units(batch, merged) == []
    assert all(r["c"] == "서윤하" for r in merged["observations"])


def test_extra_verifier_index_is_audited_without_losing_valid_paid_decisions():
    _, _, batch = setup()
    batch["review_actions"] = True
    extracted = unpack(batch, [[0, 0, 1, 0, 4, 1], [1, 0, 0, 0, 0, 1]])
    p = {**compact.verification_payload(batch, extracted), "allow_partial": True}
    raw = {"rows": [[0, 0, 0, 1], [1, 0, 1, 1], [999, 0, 0, 1]], "links": []}
    reviewed = compact.validate_verification(
        p, wire.verification_response(p, raw, proof_lengths=True)
    )
    assert [d["i"] for d in reviewed["decisions"]] == [0, 1]
    assert reviewed["validation_audit"]["unexpected_observation_rows"] == [[999, 0, 0, 1]]
    assert compact.missing_verifications(p, reviewed) == []
    raw["rows"].pop(1)
    partial = compact.validate_verification(
        p, wire.verification_response(p, raw, proof_lengths=True)
    )
    assert compact.missing_verifications(p, partial) == [1]


@pytest.mark.parametrize("designation", ["어머니", "선생님", "선장", "박 기사"])
def test_unknown_identity_does_not_turn_a_designation_into_a_new_person(designation):
    _, _, batch = setup(f"정유진의 {designation}는 오세란이었다.")
    batch["known_people"] = []
    raw = {
        "people": [
            {"name": "정유진", "kind": "named_person", "alias": -1, "u": 0},
            {"name": "오세란", "kind": "named_person", "alias": -1, "u": 0},
            {"name": designation, "kind": "ambiguous", "alias": -1, "u": 0},
        ],
        "rows": [],
        "skip": batch["target_ids"],
    }
    result = wire.extraction_response(batch, raw)
    assert [p["kind"] for p in result["people"]] == ["named_person", "named_person", "ambiguous"]
    # A missing classification is not proof that the name is a distinct person.
    del raw["people"][2]["kind"]
    assert wire.extraction_response(batch, raw)["people"][2]["kind"] == "ambiguous"
    # Explicit contextual identity overrides an inconsistent named-person label.
    raw["people"][2]["kind"] = "named_person"
    raw["identities"] = [
        {
            "units": batch["target_ids"],
            "reference": 2,
            "relative_to": 0,
            "canonical": 1,
            "evidence": [0],
        }
    ]
    assert wire.extraction_response(batch, raw)["people"][2]["kind"] == "ambiguous"
