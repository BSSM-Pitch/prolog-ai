"""Materialization must preserve paid decisions without changing provider inputs."""

from copy import deepcopy

import pytest

from prolog_ai.core.runner import InputValidationError
from prolog_ai.memory import compact
from prolog_ai.memory.module import observation_record
from prolog_ai.memory.retrieval import prepare_context
from prolog_ai.memory.source import validate_memory


def sample(kind="action", duplicate=False):
    scenes = [
        {
            "scene_id": "s",
            "revision": "r",
            "order": 1,
            "text": "서윤과 도겸, 하린이 있었다. 손을 떨었다.",
        }
    ]
    roster = [{"character_id": n, "name": n} for n in ["서윤", "도겸", "하린"]]
    batch = {
        **compact.batch_payload(compact.plan(scenes)[0], roster),
        "review_actions": True,
        "allow_partial": True,
    }
    record = {
        "c": "서윤",
        "e": [1],
        "x": [0],
        "k": kind,
        "p": "depicted",
        "b": "involuntary_reaction",
        "a": "certain",
        "to": ["도겸"],
    }
    rows = [record, {**record, "to": ["하린"]}] if duplicate else [record]
    extracted = {"people": [], "observations": rows, "covered_units": [0, 1], "skipped_units": [0]}
    review = {
        "decisions": [
            {"i": i, "c": "도겸", "a": "certain", "e": [0, 1], "reason": "독립 판정"}
            for i in range(len(rows))
        ]
    }
    return scenes, roster, batch, extracted, review


def build(args):
    scenes, roster, batch, extracted, review = args
    return compact.build_memory(
        "p", scenes, roster, [batch], [extracted], [review], model="offline"
    )


@pytest.mark.parametrize("kind", ["speech", "action", "inner_thought", "narration"])
def test_all_kinds_retain_disputed_candidates_and_source_after_roundtrip(kind):
    args = sample(kind)
    memory = build(args)
    memory = validate_memory(memory.model_dump())
    o = memory.observations[0]
    assert o.character_id is None and o.attribution == "uncertain"
    assert [(c.stage, c.name, c.character_id) for c in o.attribution_checks] == [
        ("extract", "서윤", "서윤"),
        ("verify", "도겸", "도겸"),
    ]
    assert o.attribution_checks[1].evidence[0].quote == args[0][0]["text"]
    assert compact.synthesis_payload(memory)["observations"] == []


def test_duplicate_records_merge_partners_and_alternative_checks_without_new_records():
    args = sample(duplicate=True)
    args[-1]["decisions"][1]["c"] = "하린"
    memory = build(args)
    assert len(memory.observations) == 1
    o = memory.observations[0]
    assert set(o.interlocutor_ids) == {"도겸", "하린"}
    assert {c.name for c in o.attribution_checks} == {"서윤", "도겸", "하린"}
    assert len(o.attribution_checks) == 3


def test_adjudicated_record_retains_all_decisions_without_growing_synthesis_input():
    args = sample()
    args[-1]["adjudications"] = [{**args[-1]["decisions"][0], "reason": "재검토 근거"}]
    memory = build(args)
    o = memory.observations[0]
    assert o.character_id == "도겸" and o.attribution == "certain"
    assert [c.stage for c in o.attribution_checks] == ["extract", "verify", "adjudicate"]
    payload = compact.synthesis_payload(memory)
    o.attribution_checks = []
    assert compact.synthesis_payload(memory) == payload


@pytest.mark.parametrize("damage", ["character", "quote", "revision", "scene"])
def test_retained_decisions_validate_names_and_source(damage):
    data = build(sample()).model_dump()
    check = data["observations"][0]["attribution_checks"][0]
    if damage == "character":
        check["character_id"] = "missing"
    else:
        check["evidence"][0][
            {"quote": "quote", "revision": "revision", "scene": "scene_id"}[damage]
        ] = "invalid"
    with pytest.raises(InputValidationError):
        validate_memory(data)


def test_old_memories_remain_readable():
    data = deepcopy(build(sample()).model_dump())
    data["observations"][0].pop("attribution_checks")
    assert validate_memory(data).observations[0].attribution_checks == []


def test_storage_provenance_never_expands_question_or_legacy_analysis_input():
    memory = build(sample())
    memory.complete = True
    before = prepare_context(memory.model_dump(), "손을 떨었다")
    scenes = {s.scene_id: s for s in memory.scenes}
    record = observation_record(memory.observations[0], scenes)
    assert "attribution_checks" not in record
    for observation in memory.observations:
        observation.attribution_checks = []
    assert prepare_context(memory.model_dump(), "손을 떨었다") == before
    assert observation_record(memory.observations[0], scenes) == record
