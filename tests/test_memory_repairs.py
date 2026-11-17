import pytest

from prolog_ai.memory import compact, repairs
from prolog_ai.memory import compact_wire as wire


def batches():
    return [
        {
            **compact.batch_payload(
                compact.plan([{"scene_id": scene, "revision": "r", "order": order, "text": text}])[
                    0
                ],
                [{"name": name, "aliases": []}],
            ),
            "allow_partial": True,
            "review_actions": True,
        }
        for scene, order, text, name in [
            ("a", 1, "윤하는 걸었다. “미안해.”", "윤하"),
            ("b", 2, "소리는 떨었다. “괜찮아.”", "소리"),
        ]
    ]


def test_combined_extraction_repairs_remap_colliding_local_ids_and_keep_source():
    originals = batches()
    local = [compact.repair_payload(b, [1]) for b in originals]
    payload, maps = repairs.pack("extract", local)
    assert payload["target_ids"] == [1, 3]
    response = compact.validate_extraction(
        payload,
        wire.extraction_response(
            payload, {"people": [], "rows": [[1, 1, 0, 0, 0, 1], [3, 0, 0, 0, 0, 1]], "skip": []}
        ),
    )
    split = repairs.unpack("extract", local, response, maps)
    for value, name, quote, batch in zip(
        split, ["윤하", "소리"], [" “미안해.”", " “괜찮아.”"], local, strict=True
    ):
        assert len(value["observations"]) == 1
        record = value["observations"][0]
        assert record["c"] == name
        assert record["e"] == [1]
        assert record["x"] == [0]
        assert compact.record_evidence(batch, record)["quote"] == quote
        assert compact.missing_units(batch, value) == []


def test_combined_verification_preserves_record_ids_and_cannot_use_other_chapter():
    original = batches()
    local = [
        {
            **b,
            "people": [b["known_people"][0]["name"]],
            "alias_names": [],
            "observations": [{"i": 7, "e": [1], "q": "", "n": 0, "kind": "speech"}],
        }
        for b in original
    ]
    payload, mappings = repairs.pack("verify", local)
    assert [o["i"] for o in payload["observations"]] == [0, 1]
    value = compact.validate_verification(
        payload,
        wire.verification_response(
            payload, {"rows": [[0, 1, 0, 2], [1, 0, 2, 2]], "links": []}, proof_lengths=True
        ),
    )
    split = repairs.unpack("verify", local, value, mappings)
    assert [v["decisions"][0]["i"] for v in split] == [7, 7]
    assert [v["decisions"][0]["c"] for v in split] == ["윤하", "소리"]
    assert all(v["decisions"][0]["e"] == [0, 1] for v in split)
    bad = compact.validate_verification(
        payload,
        wire.verification_response(
            payload, {"rows": [[0, 1, 2, 2], [1, 0, 2, 2]], "links": []}, proof_lengths=True
        ),
    )
    split = repairs.unpack("verify", local, bad, mappings)
    assert compact.missing_verifications(local[0], split[0]) == [7]
    assert compact.missing_verifications(local[1], split[1]) == []


def test_partial_repair_does_not_hide_unrepaired_source_and_default_still_fails():
    batch = batches()[0]
    empty = compact.validate_extraction(
        batch, wire.extraction_response(batch, {"people": [], "rows": [], "skip": []})
    )
    partial = compact.validate_extraction(
        batch,
        wire.extraction_response(batch, {"people": [], "rows": [[1, 0, 0, 0, 0, 1]], "skip": []}),
    )
    result = compact.merge_extractions(batch, empty, partial, require_complete=False)
    assert compact.missing_units(batch, result) == [0]
    with pytest.raises(ValueError, match="coverage incomplete"):
        compact.merge_extractions(batch, empty, partial)
