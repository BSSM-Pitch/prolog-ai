"""Source fidelity, abstention, cross-character evidence and bounded batch planning."""

from copy import deepcopy

import pytest

from prolog_ai.memory import compact
from prolog_ai.memory.source import validate_memory


def scene(text, sid="s", order=1):
    return {"scene_id": sid, "revision": "r", "order": order, "text": text}


def extraction(batch):
    return {
        "people": [
            {
                "name": "서윤",
                "kind": "named_person",
                "alias_of": None,
                "e": batch["target_ids"][0],
                "reason": "발화 지문",
            }
        ],
        "observations": [
            {
                "c": "서윤",
                "e": [batch["target_ids"][0]],
                "x": [],
                "k": "speech",
                "p": "depicted",
                "b": "other",
                "a": "certain",
                "to": [],
            }
        ],
        "covered_units": batch["target_ids"],
    }


def test_planner_covers_unicode_blank_lines_and_long_lines_without_loss():
    text = "🌙 서윤은 말했다. “괜찮아.”\n \t\n" + "가" * 14000 + "\n끝."
    batches = compact.plan([scene(text)])
    targets = []
    for batch in batches:
        for unit in batch["units"]:
            ev = compact.evidence(batch, [unit["id"]])
            assert text[ev["start"] : ev["end"]] == ev["quote"]
            if unit["id"] in batch["target_ids"]:
                targets.append((ev["start"], ev["end"]))
        for a, b in zip(batch["units"], batch["units"][1:]):
            if b["end"] - a["start"] <= 1200:
                ev = compact.evidence(batch, [a["id"], b["id"]])
                assert text[ev["start"] : ev["end"]] == ev["quote"]
    assert len(targets) == len(set(targets))
    assert all(ch.isspace() or any(a <= i < b for a, b in targets) for i, ch in enumerate(text))


def test_eighteen_chapters_plan_twenty_steps_and_stable_later_batch_ids():
    scenes = [scene(("서윤이 걸었다.\n" * 600), str(i), i) for i in range(18)]
    first = compact.plan(scenes)
    assert len(first) == 9
    assert 2 * len(first) + 2 == compact.MAX_STEPS
    scenes[0]["text"] = "수정된 원고\n" + scenes[0]["text"]
    scenes[0]["revision"] = "changed"
    changed = compact.plan(scenes)
    assert first[-1] == changed[-1]


def test_rejects_missing_coverage_hallucinated_person_and_foreign_source():
    batch = compact.plan([scene("서윤은 말했다. “괜찮아.”")])[0]
    valid = extraction(batch)
    compact.check("extract", batch, valid)
    for mutate in (
        lambda x: x.update(covered_units=[]),
        lambda x: x["people"][0].update(name="없는인물"),
        lambda x: x["observations"][0].update(e=[999]),
        lambda x: x["observations"][0].update(c=None),
    ):
        broken = deepcopy(valid)
        mutate(broken)
        with pytest.raises(ValueError):
            compact.check("extract", batch, broken)


def test_disputed_speaker_stays_uncertain_and_exact_evidence_survives():
    scenes = [scene("서윤은 말했다. “괜찮아.”\n도겸은 돌아섰다.")]
    batch = compact.plan(scenes)[0]
    data = extraction(batch)
    data["people"].append(
        {"name": "도겸", "kind": "named_person", "alias_of": None, "e": 2, "reason": "행동 지문"}
    )
    review = {"decisions": [{"i": 0, "c": "도겸", "a": "certain", "e": [0], "reason": "다른 판정"}]}
    memory = compact.build_memory(
        "p",
        scenes,
        [{"character_id": "a", "name": "서윤"}, {"character_id": "b", "name": "도겸"}],
        [batch],
        [data],
        [review],
        model="offline",
    )
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    assert memory.observations[0].character_id is None
    assert memory.observations[0].attribution == "uncertain"
    assert memory.speaker_verifications[0].proposed_character_id == "b"
    ev = memory.observations[0].evidence
    assert scenes[0]["text"][ev.start : ev.end] == ev.quote


def test_pattern_evidence_cannot_cross_characters_or_overlap():
    payload = {
        "characters": [{"i": 0}, {"i": 1}],
        "observations": [{"i": 0, "c": 0}, {"i": 1, "c": 1}],
        "proposals": [
            {
                "c": 0,
                "description": "말버릇",
                "condition": "불안할 때",
                "seeds": [0],
                "hypothesis": None,
                "alternatives": [],
            }
        ],
    }
    for assessment in [
        {"i": 0, "support": [1], "counter": []},
        {"i": 0, "support": [0], "counter": [0]},
    ]:
        with pytest.raises(ValueError):
            compact.check("assess", payload, {"assessments": [assessment]})


def test_paid_step_requires_budget_even_without_an_api_key():
    with pytest.raises(ValueError, match="durable request budget"):
        compact.run_step("extract", {})


def test_distinct_details_in_one_unit_are_not_collapsed():
    scenes = [scene("서윤은 손을 떨었다. 서윤은 고개를 숙였다.")]
    batch = compact.plan(scenes, granular=False)[0]
    data = extraction(batch)
    base = {**data["observations"][0], "k": "action"}
    data["observations"] = [{**base, "q": "손을 떨었다."}, {**base, "q": "고개를 숙였다."}]
    memory = compact.build_memory(
        "p",
        scenes,
        [{"character_id": "a", "name": "서윤"}],
        [batch],
        [data],
        [{"decisions": []}],
        model="offline",
    )
    assert len(memory.observations) == 2
    assert {o.evidence.quote for o in memory.observations} == {"손을 떨었다.", "고개를 숙였다."}
    bad = deepcopy(data)
    bad["observations"][0]["q"] = "원문에 없는 행동"
    with pytest.raises(ValueError, match="absent"):
        compact.check("extract", batch, bad)


def test_known_full_name_can_ground_short_form_without_registering_an_alias():
    scene_data = scene("윤하는 말했다. “괜찮아.”")
    batch = compact.batch_payload(
        compact.plan([scene_data])[0], [{"name": "서윤하", "character_id": "a", "aliases": []}]
    )
    data = extraction(batch)
    data["people"][0]["name"] = "윤하"
    data["observations"][0]["c"] = "서윤하"
    compact.check("extract", batch, data)
    review = {
        "decisions": [
            {"i": 0, "c": "서윤하", "a": "certain", "e": [0], "reason": "문맥상 기존 인물의 발화"}
        ]
    }
    memory = compact.build_memory(
        "p",
        [scene_data],
        [{"name": "서윤하", "character_id": "a"}],
        [batch],
        [data],
        [review],
        model="offline",
    )
    assert memory.observations[0].character_id == "a"
    assert not memory.characters[0].aliases
    # A nearby suffix is only a candidate: without a grounded model decision it stays unresolved.
    data["observations"][0]["c"] = "윤하"
    review["decisions"][0]["c"] = "윤하"
    unknown = compact.build_memory(
        "p",
        [scene_data],
        [{"name": "서윤하", "character_id": "a"}],
        [batch],
        [data],
        [review],
        model="offline",
    )
    assert unknown.observations[0].character_id is None
    assert unknown.observations[0].attribution == "uncertain"


def test_source_filter_keeps_rejected_record_for_audit_without_inventing_evidence():
    b = compact.plan([scene("서윤은 손을 떨었다.")])[0]
    raw = extraction(b)
    raw["observations"] = [
        {**raw["observations"][0], "k": "action", "b": "invalid-role", "q": "손을 떨었다."},
        {**raw["observations"][0], "k": "action", "q": "원문에 없는 행동"},
    ]
    result = compact.validate_extraction(b, raw)
    assert len(result["observations"]) == 1
    assert result["observations"][0]["b"] == "other"
    audit = result["validation_audit"]
    assert audit["unknown_behavior_roles"] == 1
    assert audit["withheld_observations"][0]["record"]["q"] == "원문에 없는 행동"
    assert compact.check("extract", b, result) == result


def test_verification_joins_actual_source_and_keeps_original_references():
    b = compact.plan([scene("서윤이 말했다.\n“괜찮아.”\n서윤은 고개를 끄덕였다.\n")])[0]
    raw = extraction(b)
    p = compact.verification_payload(b, raw)
    result = compact.validate_verification(
        p,
        {"decisions": [{"i": 0, "c": "서윤", "a": "certain", "e": [0, 2], "reason": "앞뒤 지문"}]},
    )
    assert result["decisions"][0]["e"] == [0, 1, 2]
    assert result["validation_audit"]["joined_source_references"][0]["original_e"] == [0, 2]
    assert (
        compact.evidence(p, [0, 1, 2])["quote"]
        == "서윤이 말했다.\n“괜찮아.”\n서윤은 고개를 끄덕였다."
    )
    bad = deepcopy(p)
    bad["units"][2]["scene"] = "another-scene"
    rejected = compact.validate_verification(
        bad,
        {
            "decisions": [
                {"i": 0, "c": "서윤", "a": "certain", "e": [0, 2], "reason": "잘못된 장면"}
            ]
        },
    )
    assert rejected["decisions"][0]["c"] is None
    assert rejected["decisions"][0]["a"] == "uncertain"
    assert "one scene" in rejected["validation_audit"]["invalid_source_proofs"][0]["reason"]


def test_unnamed_speaker_cannot_be_promoted_to_certain_identity():
    b = compact.plan([scene("아이가 말했다. “싫어요.”")])[0]
    p = compact.verification_payload(b, extraction(b))
    original = {"i": 0, "c": None, "a": "certain", "e": [0], "reason": "이름 없는 아이"}
    result = compact.validate_verification(p, {"decisions": [original]})
    assert result["decisions"][0]["a"] == "uncertain"
    assert result["decisions"][0]["c"] is None
    assert result["validation_audit"]["unresolved_speakers"] == [original]
    assert original["a"] == "certain"


def test_exhausted_verification_preserves_good_decisions_and_defers_invalid_or_missing():
    b = compact.plan([scene("서윤은 걸었다.\n서윤이 말했다.\n서윤은 웃었다.")])[0]
    raw = extraction(b)
    raw["observations"] = [{**raw["observations"][0], "e": [i]} for i in range(3)]
    payload = compact.verification_payload(b, raw)
    good = {"i": 0, "c": "서윤", "a": "certain", "e": [0], "reason": "명시된 인물"}
    bad = {**good, "i": 1, "e": [1]}
    review = {
        "decisions": [good, bad],
        "validation_audit": {"invalid_proof_rows": [[1, 1, 999, 1]]},
    }
    before = deepcopy(review)
    result = compact.defer_verifications(payload, review)
    assert review == before
    assert result["decisions"][0] == good
    assert all(d["a"] == "uncertain" and d["c"] is None for d in result["decisions"][1:])
    assert compact.missing_verifications(payload, result) == []
    audit = result["validation_audit"]["deferred_verifications"]
    assert audit["indices"] == [1, 2]
    assert audit["invalid_proof_rows"] == [[1, 1, 999, 1]]
    assert audit["original_decisions"] == [bad]
    assert compact.defer_verifications(payload, result) == result
    memory = compact.build_memory(
        "p",
        [scene("서윤은 걸었다.\n서윤이 말했다.\n서윤은 웃었다.")],
        [{"character_id": "a", "name": "서윤"}],
        [b],
        [raw],
        [result],
        model="offline",
    )
    assert [o.attribution for o in memory.observations] == ["certain", "uncertain", "uncertain"]


def test_global_stages_share_schema_and_complete_evidence_prefix(monkeypatch):
    import json

    from prolog_ai.core.request_policy import RequestPolicy, request_policy

    calls = []
    payload = {
        "characters": [{"i": 0, "name": "서윤"}],
        "observations": [
            {
                "i": i,
                "c": 0,
                "order": i,
                "k": "action",
                "p": "depicted",
                "b": "other",
                "quote": f"서윤의 손이 떨렸다. {i}",
                "context": "대답하기 직전",
            }
            for i in (4, 7)
        ],
    }
    proposal = {
        "c": 0,
        "description": "손 떨림",
        "condition": "대답 직전",
        "seeds": [4, 7],
        "hypothesis": None,
        "alternatives": [],
    }

    def fake(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return (
            {"proposals": [proposal], "assessments": []}
            if len(calls) == 1
            else {"proposals": [], "assessments": [{"i": 0, "support": [4, 7], "counter": []}]}
        )

    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    monkeypatch.setattr(compact, "call_llm", fake)
    with request_policy(RequestPolicy(before_attempt=lambda: None)):
        proposed = compact.run_step("propose", payload)
        assessed = compact.run_step("assess", {**payload, **proposed})
    assert proposed == {"proposals": [proposal]}
    assert assessed["assessments"][0]["support"] == [4, 7]
    first, second = [call[0].split("\n작업:\n", 1) for call in calls]
    assert first[0] == second[0]
    assert first[1] != second[1]
    assert calls[0][1]["schema"] is calls[1][1]["schema"] is compact.PatternTurn
    evidence = json.loads(first[0][len(compact.SYNTHESIS_PREFIX) :])
    assert [row[0] for row in evidence["rows"]] == [4, 7]
    assert "proposals" not in evidence
    assert "후보:" in second[1]


def test_pattern_reference_recovery_never_invents_evidence_or_erases_counterexamples():
    payload = {
        "characters": [{"i": 0}, {"i": 1}],
        "observations": [{"i": 2, "c": 0}, {"i": 3, "c": 1}, {"i": 4, "c": 0}],
    }
    proposal = {
        "c": 0,
        "description": "습관",
        "condition": "대답",
        "seeds": [2, 3, 999],
        "hypothesis": None,
        "alternatives": [],
    }
    clean = compact.validate_pattern_response(
        "propose", payload, {"proposals": [proposal, {**proposal, "seeds": [3]}]}
    )
    assert len(clean["proposals"]) == 1
    assert clean["proposals"][0]["seeds"] == [2]
    assert len(clean["validation_audit"]["invalid_pattern_references"]) == 2
    payload = {**payload, **clean}
    accepted = compact.validate_pattern_response(
        "assess", payload, {"assessments": [{"i": 0, "support": [2, 3, 4, 999], "counter": []}]}
    )
    assert accepted["assessments"][0]["support"] == [2, 4]
    for counter in ([3], [999], [2]):
        withheld = compact.validate_pattern_response(
            "assess", payload, {"assessments": [{"i": 0, "support": [2, 4], "counter": counter}]}
        )
        assert withheld["assessments"] == [{"i": 0, "support": [], "counter": []}]
