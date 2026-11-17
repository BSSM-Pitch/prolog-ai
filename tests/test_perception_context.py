"""Context-derived perceivers are useful links, not fabricated model verdicts."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.core.runner import InputValidationError
from prolog_ai.memory import compact, compact_wire, verification_wire
from prolog_ai.memory.perception_context import infer_perception_contexts
from prolog_ai.memory.source import validate_memory


def fixture(name="한민서", sense="sound", damage=None):
    phrases = {
        "sound": (
            f"{name}는 전에 들었던 음성을 떠올렸다.",
            "발소리는 없었다.",
            "저 음성은 이름부터 불렀다.",
        ),
        "sight": (
            f"{name}는 전에 보았던 빛을 떠올렸다.",
            "불빛은 없었다.",
            "저 빛은 색깔이 달랐다.",
        ),
        "smell": (
            f"{name}는 전에 맡았던 향기를 떠올렸다.",
            "향기는 없었다.",
            "저 향기는 전과 달랐다.",
        ),
    }
    before, target, after = phrases[sense]
    if damage == "no_sense":
        target = "문은 없었다."
    if damage == "quoted":
        target = f'"{target}"'
    gap = "\n\n" if damage == "next_paragraph" else " "
    text = before + '\n\n"이리 와."\n\n' + target + " 조한결은 늘 먼저 발을 굴렀다." + gap + after
    scene = {"scene_id": "s", "revision": "r", "order": 1, "text": text}
    batch = {
        **compact.plan([scene])[0],
        "known_people": [],
        "allow_partial": True,
        "review_actions": True,
    }
    assert len(batch["units"]) == 5
    kinds = ["inner_thought", "speech", "narration", "narration", "inner_thought"]
    names = [name, None, None, "조한결", name]
    if damage == "viewpoint_switch":
        names[4] = "조한결"
    if damage == "named_target":
        names[2] = name
    if damage == "no_thought":
        kinds[0] = "action"
    rows = [
        {
            "c": n,
            "e": [i],
            "x": [],
            "k": k,
            "p": "thought" if k == "inner_thought" else "narrator_claim",
            "b": "awareness" if k == "inner_thought" else "other",
            "a": "certain" if n else "uncertain",
            "to": [],
        }
        for i, (k, n) in enumerate(zip(kinds, names, strict=True))
    ]
    ex = compact.validate_extraction(
        batch,
        {
            "people": [
                {"name": name, "alias_of": None, "kind": "named_person", "e": 0, "reason": "원문"},
                {
                    "name": "조한결",
                    "alias_of": None,
                    "kind": "named_person",
                    "e": 3,
                    "reason": "원문",
                },
            ],
            "observations": rows,
            "covered_units": list(range(5)),
        },
    )
    batch = compact.share_discovered_people([batch], [ex])[0]
    review = {
        "decisions": [
            {"i": i, "c": n, "a": "certain" if n else "uncertain", "e": [i], "reason": "독립 검증"}
            for i, n in enumerate(names)
        ]
    }
    if damage == "unverified_anchor":
        review["decisions"][0].update(c=None, a="uncertain")
    roster = [{"character_id": n, "name": n} for n in [name, "조한결"]]
    with patch.object(compact, "call_llm", side_effect=AssertionError("No model calls")):
        memory = compact.build_memory(
            "p", [scene], roster, [batch], [ex], [review], model="offline"
        )
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    return memory, batch, ex


@pytest.mark.parametrize(
    "name,sense", [("한민서", "sound"), ("장태오", "sight"), ("김지민", "smell")]
)
def test_first_upload_links_corroborated_perceiver_but_keeps_null_verdicts(name, sense):
    memory, _, _ = fixture(name, sense)
    target = memory.observations[2]
    assert target.perception_context.character_id == name
    assert target.perception_context.basis == "context_inference"
    assert target.character_id is None and target.attribution == "uncertain"
    assert target.subject_name is None and target.subject_attribution == "uncertain"
    assert all(c.name is None and c.attribution == "uncertain" for c in target.attribution_checks)
    assert target.perception_context.anchor_observation_ids == [
        memory.observations[i].observation_id for i in (0, 4)
    ]
    before = deepcopy(memory)
    assert infer_perception_contexts(memory) == infer_perception_contexts(memory)
    assert memory == before
    payload = compact.synthesis_payload(memory)
    assert len(payload["observations"]) == 3  # No synthetic confirmed record added.
    wire = compact_wire.synthesis_request(payload)
    related = wire["related_perceptions"]
    assert related[0]["subject_confirmed"] is False
    assert wire["texts"][related[0]["quote"]] == target.evidence.quote


@pytest.mark.parametrize(
    "damage",
    [
        "viewpoint_switch",
        "unverified_anchor",
        "named_target",
        "no_thought",
        "no_sense",
        "quoted",
        "next_paragraph",
    ],
)
def test_does_not_assign_every_description_to_the_nearest_character(damage):
    memory, _, _ = fixture(damage=damage)
    assert memory.observations[2].perception_context is None


def test_competing_uncertain_thought_blocks_context_propagation():
    memory, _, _ = fixture()
    middle = memory.observations[3]
    middle.kind, middle.behavior_role = "inner_thought", "awareness"
    middle.attribution = "uncertain"
    assert memory.observations[2].observation_id not in infer_perception_contexts(memory)


def test_context_cannot_cross_scene_or_be_tampered_with():
    memory, _, _ = fixture()
    for field, value in [
        ("character_id", "조한결"),
        ("anchor_observation_ids", ["missing", "missing"]),
    ]:
        damaged = memory.model_dump()
        damaged["observations"][2]["perception_context"][field] = value
        with pytest.raises(InputValidationError):
            validate_memory(damaged, require_complete=True)
    damaged = memory.model_dump()
    damaged["observations"][2]["perception_context"]["evidence"][0]["quote"] = "가짜 근거"
    with pytest.raises(InputValidationError):
        validate_memory(damaged, require_complete=True)
    memory.observations[4].evidence.scene_id = "other"
    assert not infer_perception_contexts(memory)


def test_existing_requests_include_paragraphs_without_subject_leakage():
    _, batch, ex = fixture()
    extract = compact_wire.extraction_request(batch)
    verify = verification_wire.request(compact.verification_payload(batch, ex))
    assert [u["paragraph"] for u in extract["units"]] == [0, 1, 2, 2, 2]
    assert [u["paragraph"] for u in verify["source"]] == [0, 1, 2, 2, 2]
    assert all("c" not in target for u in verify["source"] for target in u.get("targets", []))
