import json

from prolog_ai.memory import compact
from prolog_ai.memory import verification_wire as wire
from prolog_ai.memory.names import name_key, reference_mention
from prolog_ai.memory.sections import sections
from prolog_ai.modules.ssm.prompt import build_prompt
from tests.test_first_pass_verification import fixture


def test_logical_sections_are_lossless_and_do_not_restart_at_planning_notes():
    text = (
        "서문\n"
        + "".join(f"{n}화 제목\n인물이 걸었다.\n" for n in range(1, 91))
        + "기획 메모\n1화 수정할 것\n"
    )
    parts = sections(text)
    assert len(parts) == 90
    assert "".join(text[p["start"] : p["end"]] for p in parts) == text
    assert "기획 메모" in text[parts[-1]["start"] :]
    scenes = [
        {"scene_id": str(i), "order": i + 1, "revision": "r", "text": text[p["start"] : p["end"]]}
        for i, p in enumerate(parts)
    ]
    batches = compact.plan(scenes)
    assert len(batches) == 1
    assert {u["scene"] for batch in batches for u in batch["units"]} == {str(i) for i in range(90)}


def test_spacing_equivalence_never_removes_latin_word_boundaries_or_infers_suffixes():
    assert name_key("동방 승냥") == name_key("동방승냥")
    assert name_key("Ann A") != name_key("Anna")
    assert name_key("김민수") != name_key("민수")
    assert not reference_mention("마왕", "그는 마왕에 빙의했다.")
    assert reference_mention("가수", "그는 가수인 척했다.")


def test_compact_review_is_lossless_and_rejects_the_same_invalid_source():
    _, _, _, payload = fixture()
    old = {"rows": [{"r": "T0.0", "c": "민서", "e": "U0", "n": 1}], "links": []}
    new = {"rows": [["T0.0", "민서", "U0", 1]], "links": []}
    assert wire.response(payload, old) == wire.response(payload, new)
    assert len(json.dumps(new)) < len(json.dumps(old))
    old["rows"][0]["e"] = "U999"
    new["rows"][0][2] = "U999"
    assert wire.response(payload, old) == wire.response(payload, new)
    wire.CompactContextVerification.model_validate(new)


def test_ssm_expands_events_for_internal_episodes_without_extra_model_calls():
    prompt = build_prompt(
        {
            "chapter": 1,
            "characters": [],
            "chapter_text": "".join(f"{i}화\n사건 {i}\n" for i in range(1, 91)),
        }
    )
    assert "1~23개" in prompt
    assert "회차 표기" in prompt
    assert "<chapter_number>1</chapter_number>" in prompt


def test_bad_row_preserves_good_rows_and_repairs_only_affected_targets():
    import pytest
    from pydantic import ValidationError

    _, _, _, p = fixture()
    p["observations"] = p["observations"][:2]
    for bad in (9, 10, 0, True, "2", None):
        raw = {"rows": [["T0.0", "민서", "U0", 1], ["T1.1", "민서", "U0", bad]], "links": []}
        result = compact.validate_verification(p, wire.response(p, raw))
        assert compact.missing_verifications(p, result) == [1]
        assert result["decisions"][0]["c"] == "민서"
        assert result["validation_audit"]["malformed_rows"]
    for bad in (9, 10, 0, True):
        with pytest.raises(ValidationError):
            wire.CompactContextVerification.model_validate(
                {"rows": [["T0.0", "민서", "U0", bad]], "links": []}
            )


def test_malformed_duplicate_cannot_confirm_the_valid_duplicate():
    _, _, _, p = fixture()
    p["observations"] = p["observations"][:1]
    raw = {"rows": [["T0.0", "민서", "U0", 1], ["T0.0", "민서", "U0", 99]], "links": []}
    result = compact.validate_verification(p, wire.response(p, raw))
    assert compact.missing_verifications(p, result) == [0]
