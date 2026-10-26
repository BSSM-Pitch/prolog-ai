"""장면 간 근거 연결·가설 경계·재개·수정·검색을 결정적 모의 LLM으로 검증한다.

이 테스트는 모델의 문학 해석 정확도를 측정하지 않는다. 실제 품질 평가는 evals의
별도 원고/주석 세트로 수행하며, 여기서는 모델 오류가 파이프라인을 오염시키지 않는지 본다.
"""

import copy
import json
from types import SimpleNamespace

import pytest

from prolog_ai import (
    MemoryStore,
    query_character_memory,
    run_aiq,
    run_character_memory,
    run_character_review,
    run_scds,
    run_scds_analysis,
    run_scds_rules,
)
from prolog_ai.core.llm import LLMFailedError, LLMTimeoutError
from prolog_ai.memory.source import chunks, encode, validate_memory

CHARACTERS = [
    {"character_id": "c1", "name": "서진", "aliases": ["진"]},
    {"character_id": "c2", "name": "동생"},
]
SCENES = [
    {
        "scene_id": "s7",
        "revision": "1",
        "order": 7,
        "story_time": "부상 전",
        "text": '동료가 도움을 제안했다. 서진은 "됐어."라고 말했다.',
    },
    {
        "scene_id": "s31",
        "revision": "1",
        "order": 31,
        "text": '동생이 도와주려 했다. 서진은 "괜찮아."라고 말했다.',
    },
    {
        "scene_id": "s68",
        "revision": "1",
        "order": 68,
        "text": '서진은 동생의 도움을 받아들였다. "부탁해."',
    },
]


def draft(quote, **changes):
    return {
        "character_id": "c1",
        "attribution": "certain",
        "kind": "speech",
        "presentation": "depicted",
        "summary": "도움에 대한 반응",
        "context": "도움을 제안받음",
        "interlocutor_ids": ["c2"],
        "quote": quote,
        "occurrence": 0,
        **changes,
    }


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")
    state = SimpleNamespace(calls=[], transform=None, fail=None)

    def fake(prompt, *, schema, **kwargs):
        if "<input_json>" in prompt:
            data = json.loads(prompt.split("<input_json>\n", 1)[1].rsplit("\n</input_json>", 1)[0])
        else:
            data = {"prompt": prompt}
        state.calls.append((schema.__name__, data))
        if state.fail:
            state.fail(schema.__name__, data)
        if schema.__name__ == "ExtractionOutput":
            quotes = [q for q in ["됐어.", "괜찮아.", "부탁해."] if q in data["text"]]
            result = {"observations": [draft(q) for q in quotes]}
        elif schema.__name__ == "SpeakerVerificationOutput":
            result = {
                "decisions": [
                    {
                        "observation_id": o["observation_id"],
                        "character_id": "c1",
                        "attribution": "certain",
                        "reason": "발화 지시문 확인",
                        "quote": o["quote"],
                        "occurrence": 0,
                    }
                    for o in data["observations"]
                ]
            }
        elif schema.__name__ == "SpeakerResolutionOutput":
            result = {
                "decisions": [
                    {
                        "observation_id": o["observation_id"],
                        "character_id": "c1",
                        "attribution": "certain",
                        "reason": "정확한 위치의 발화 지시문 확인",
                        "evidence_id": next(
                            e["evidence_id"] for e in o["evidence_options"] if e["role"] == "target"
                        ),
                    }
                    for o in data["observations"]
                ]
            }
        elif schema.__name__ == "DiscoveryOutput":
            result = {
                "proposals": [
                    {
                        "description": "관심을 받으면 도움을 거절하는 경향",
                        "condition": "도움을 제안받음",
                        "seed_observation_ids": [data["observations"][0]["observation_id"]],
                        "hypothesis": "취약함을 보이는 일을 부담스러워할 수 있다",
                        "alternatives": ["혼자 해결하려는 선호일 수 있다"],
                    }
                ]
            }
        elif schema.__name__ == "AssessmentOutput":
            support = [
                o["observation_id"]
                for o in data["observations"]
                if o["evidence"]["quote"] != "부탁해."
            ]
            counter = [
                o["observation_id"]
                for o in data["observations"]
                if o["evidence"]["quote"] == "부탁해."
            ]
            result = {
                "assessments": [
                    {
                        "proposal_index": p["proposal_index"],
                        "supporting_observation_ids": support,
                        "counterexample_observation_ids": counter,
                    }
                    for p in data["proposals"]
                ]
            }
        elif schema.__name__ == "CharacterReviewOutput":
            result = {
                "findings": [
                    {
                        "character_id": "c1",
                        "kind": "development",
                        "explanation": "관계 변화 가능성",
                        "advice": "도움을 받아들이는 계기를 살펴보세요.",
                        "event_quote": data["event"]["content"],
                        "observation_ids": [data["memory"]["observations"][0]["observation_id"]],
                    }
                ]
            }
        elif schema.__name__ == "AIQOutput":
            result = {"content": "반례가 있어 단정할 수 없습니다."}
        else:
            result = {"conflicts": []}
        return state.transform(schema.__name__, data, result) if state.transform else result

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", fake)
    return state


def build(**kwargs):
    return run_character_memory("novel", copy.deepcopy(SCENES), copy.deepcopy(CHARACTERS), **kwargs)


def test_observations_patterns_and_tentative_hypotheses_have_exact_provenance(llm):
    result = build()
    assert "data" in result, result
    memory = result["data"]
    assert memory["complete"]
    assert len(memory["observations"]) == 3
    (p,) = memory["patterns"]
    assert p["supporting_scene_count"] == 2
    assert p["counterexample_scene_count"] == 1 and p["status"] == "contested"
    assert p["evaluated_observation_count"] == 3
    assert memory["hypotheses"][0]["status"] == "tentative"
    sources = {s["scene_id"]: s for s in memory["scenes"]}
    for o in memory["observations"]:
        e = o["evidence"]
        assert sources[e["scene_id"]]["text"][e["start"] : e["end"]] == e["quote"]
    assert result["meta"]["llm_calls"] == 8


def test_a_single_minor_detail_is_kept_without_claiming_a_pattern(llm):
    memory = run_character_memory("novel", SCENES[:1], CHARACTERS)["data"]
    assert len(memory["observations"]) == 1
    assert memory["patterns"] == memory["hypotheses"] == []


def test_independent_speaker_verification_corrects_before_pattern_build(llm):
    def transform(name, data, result):
        if name == "ExtractionOutput":
            for o in result["observations"]:
                o["character_id"] = "c2"  # 정확한 인용을 엉뚱한 듣는 사람에게 귀속
        if name == "SpeakerVerificationOutput":
            assert all("character_id" not in o for o in data["observations"])
            assert "서진" in data["source_text"]
        return result

    llm.transform = transform
    result = build()
    assert result["meta"]["corrected_speakers"] == 3
    assert [o["character_id"] for o in result["data"]["observations"]] == ["c1", "c1", None]
    assert result["data"]["observations"][-1]["attribution"] == "uncertain"
    assert {p["character_id"] for p in result["data"]["patterns"]} == {"c1"}
    assert {v["original_character_id"] for v in result["data"]["speaker_verifications"]} == {"c2"}
    validate_memory(result["data"], require_complete=True)


def test_disagreement_recheck_does_not_overwrite_correct_extraction(llm):
    def transform(name, data, result):
        if name == "SpeakerResolutionOutput":
            assert all(
                "first_decision" not in o and "extraction" not in o for o in data["observations"]
            )
        if name == "SpeakerVerificationOutput":
            if "target_context" not in data["observations"][0]:
                for d in result["decisions"]:
                    d["character_id"] = "c2"  # 검증 모델 자체가 화자를 뒤집는 오류
            else:
                assert "서진" in data["source_text"]
                assert data["observations"][0]["evidence_options"]
        return result

    llm.transform = transform
    result = build()
    assert result["meta"]["adjudicated_speakers"] == 3
    assert result["meta"]["corrected_speakers"] == 1
    assert [o["character_id"] for o in result["data"]["observations"]] == ["c1", "c1", None]
    assert result["data"]["observations"][-1]["attribution"] == "uncertain"


def test_recheck_rejects_a_repeated_quote_from_another_location():
    from prolog_ai.memory.schema import SpeakerResolutionOutput, SpeakerVerificationOutput
    from prolog_ai.memory.speakers import resolve_decisions, validate_decisions

    text = "알아." + "가" * 2000 + "알아."
    data = {
        "source_text": text,
        "source_start": 0,
        "observations": [
            {"observation_id": "o", "target_context": {"start": 1900, "end": len(text)}}
        ],
    }
    output = SpeakerVerificationOutput.model_validate(
        {
            "decisions": [
                {
                    "observation_id": "o",
                    "character_id": "c1",
                    "attribution": "certain",
                    "reason": "두 번째 발화",
                    "quote": "알아.",
                    "occurrence": 0,
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="다른 위치"):
        validate_decisions(output, data, {"c1"})
    output.decisions[0].occurrence = 1
    validate_decisions(output, data, {"c1"})
    data["observations"][0]["evidence_options"] = [
        {"evidence_id": "o:target", "start": 2003, "quote": "알아."}
    ]
    resolution = SpeakerResolutionOutput.model_validate(
        {
            "decisions": [
                {
                    "observation_id": "o",
                    "character_id": "c1",
                    "attribution": "certain",
                    "reason": "두 번째 발화",
                    "evidence_id": "o:target",
                }
            ]
        }
    )
    assert resolve_decisions(resolution, data, {"c1"}).decisions[0].occurrence == 1
    resolution.decisions[0].evidence_id = "other:target"
    with pytest.raises(ValueError, match="선택지"):
        resolve_decisions(resolution, data, {"c1"})


def test_invalid_first_speaker_citation_requires_local_repair_before_storage(llm):
    def transform(name, data, result):
        if name == "SpeakerVerificationOutput" and "target_context" not in data["observations"][0]:
            result["decisions"][0]["quote"] = "원문에 없는 발화 지시문"
        return result

    llm.transform = transform
    result = build()
    assert result["meta"]["adjudicated_speakers"] == 3
    assert all(
        v["evidence"]["quote"] != "원문에 없는 발화 지시문"
        for v in result["data"]["speaker_verifications"]
    )
    validate_memory(result["data"], require_complete=True)


@pytest.mark.parametrize("defect", ["missing", "unknown", "fabricated", "null_certain"])
def test_speaker_verification_cannot_cache_invalid_decisions(llm, defect):
    def transform(name, data, result):
        if name == "SpeakerVerificationOutput":
            if defect == "missing":
                result["decisions"] = []
            elif defect == "unknown":
                result["decisions"][0]["character_id"] = "ghost"
            elif defect == "null_certain":
                result["decisions"][0]["character_id"] = None
            else:
                result["decisions"][0]["quote"] = "꾸며낸 발화 지시문"
        if name == "SpeakerResolutionOutput" and defect == "fabricated":
            result["decisions"][0]["evidence_id"] = "missing"
        return result

    llm.transform = transform
    result = build()
    assert result["error"]["details"]["internal_code"] == "INVALID_REFERENCE"
    checkpoint = result["error"]["details"]["checkpoint"]
    llm.transform = None
    llm.calls.clear()
    assert "data" in build(previous_memory=checkpoint)
    assert llm.calls[0][0] in ("SpeakerVerificationOutput", "SpeakerResolutionOutput")


def test_fabricated_quotes_unknown_characters_and_uncertain_speakers(llm):
    def transform(name, data, result):
        if name == "ExtractionOutput":
            quote = result["observations"][0]["quote"]
            result["observations"] = [
                draft("원고에 없는 말"),
                draft(quote, character_id="ghost"),
                draft(quote, character_id=None, attribution="uncertain"),
            ]
        if name == "SpeakerVerificationOutput":
            for decision in result["decisions"]:
                decision.update(character_id=None, attribution="uncertain")
        return result

    llm.transform = transform
    result = build()
    assert result["meta"]["removed_observations"] == 6
    assert len(result["data"]["observations"]) == 3
    assert result["data"]["patterns"] == []


def test_same_quote_occurrence_and_overlapping_chunks_are_deduplicated(llm):
    text = "됐어. " + "가" * 970 + " 됐어. " + "나" * 1000

    def transform(name, data, result):
        if name == "ExtractionOutput":
            result["observations"] = [
                draft("됐어.", occurrence=i) for i in range(data["text"].count("됐어."))
            ]
        return result

    llm.transform = transform
    result = run_character_memory(
        "novel", [{**SCENES[0], "text": text}], CHARACTERS, chunk_chars=1000
    )
    assert "data" in result, result
    observations = result["data"]["observations"]
    assert len(observations) == 2
    assert sorted(o["evidence"]["start"] for o in observations) == [0, text.rfind("됐어.")]
    assert max(len(d["text"]) for name, d in llm.calls if name == "ExtractionOutput") <= 1000


def test_chunk_coverage_has_no_gaps_with_long_paragraphs_and_newlines():
    text = ("가" * 730 + "\n" + "나" * 900 + "\n") * 10
    covered = set()
    for start, part in chunks(text, 1000):
        assert text[start : start + len(part)] == part and len(part) <= 1000
        covered.update(range(start, start + len(part)))
    assert covered == set(range(len(text)))


def test_every_observation_batch_is_checked_for_counterexamples(llm):
    scenes = [{**SCENES[i % 3], "scene_id": f"s{i}", "order": i} for i in range(30)]
    result = run_character_memory("novel", scenes, CHARACTERS, batch_chars=4000)
    assert "data" in result, result
    (p,) = result["data"]["patterns"]
    assert p["supporting_scene_count"] == 20 and p["counterexample_scene_count"] == 10
    checks = [d for name, d in llm.calls if name == "AssessmentOutput"]
    assert len(checks) > 1
    assert len({o["observation_id"] for d in checks for o in d["observations"]}) == 30
    # 큰 패턴도 제한 문맥에서 검색할 수 있고 반례 표본과 생략량을 함께 제공한다.
    context = query_character_memory(result["data"], "서진", max_context_chars=12000)["data"]
    (retrieved,) = context["patterns"]
    assert retrieved["evidence_selection"]["sampled"]
    assert retrieved["counterexample_observation_ids"]
    assert retrieved["evidence_selection"]["omitted_counterexample_observation_count"] > 0
    assert context["coverage"]["sampled_pattern_count"] == 1
    assert len(encode(context)) <= 12000


@pytest.mark.parametrize(
    "defect", ["unknown", "other_character", "overlap", "missing", "duplicate"]
)
def test_assessment_reference_errors_fail_and_can_be_retried(llm, defect):
    def transform(name, data, result):
        if name == "AssessmentOutput":
            a = result["assessments"][0]
            if defect in {"unknown", "other_character"}:
                a["supporting_observation_ids"].append("not-in-this-batch")
            elif defect == "overlap":
                a["counterexample_observation_ids"].append(a["supporting_observation_ids"][0])
            elif defect == "missing":
                result["assessments"] = []
            else:
                result["assessments"].append(a)
        return result

    llm.transform = transform
    failure = build()
    assert failure["error"]["details"]["internal_code"] == "INVALID_REFERENCE"
    checkpoint = failure["error"]["details"]["checkpoint"]
    validate_memory(checkpoint)
    llm.transform = None
    assert "data" in build(previous_memory=checkpoint)


def test_budget_checkpoint_resumes_without_repeating_completed_requests(llm):
    previous = None
    for _ in range(9):
        result = build(previous_memory=previous, max_llm_calls=1)
        if "data" in result:
            break
        assert result["error"]["details"]["internal_code"] == "CALL_BUDGET_EXCEEDED"
        previous = result["error"]["details"]["checkpoint"]
        validate_memory(previous)
        assert not previous["complete"]
    assert "data" in result
    assert len(llm.calls) == 8
    again = build(previous_memory=result["data"])
    assert again["meta"]["llm_calls"] == 0 and again["meta"]["cache_hits"] == 8
    assert again["data"] == result["data"]


@pytest.mark.parametrize(
    "error,code",
    [
        (LLMFailedError("failed"), "AI_ANALYSIS_FAILED"),
        (LLMTimeoutError("timeout"), "AI_ANALYSIS_TIMEOUT"),
    ],
)
def test_provider_failure_returns_reusable_checkpoint(llm, error, code):
    def fail(name, data):
        if name == "ExtractionOutput" and data["scene"]["scene_id"] == "s31":
            raise error

    llm.fail = fail
    result = build()
    assert result["error"]["code"] == code
    checkpoint = result["error"]["details"]["checkpoint"]
    assert checkpoint["processed_scene_ids"] == ["s7"]
    llm.fail = None
    resumed = build(previous_memory=checkpoint)
    assert "data" in resumed and resumed["meta"]["cache_hits"] == 1


def test_source_edit_and_deletion_remove_old_evidence_and_hypotheses(llm):
    previous = build()["data"]
    scenes = copy.deepcopy(SCENES[:2])
    scenes[1].update(text="서진은 아무 말도 하지 않았다.", revision="2")
    result = run_character_memory("novel", scenes, CHARACTERS, previous)
    assert "data" in result, result
    memory = result["data"]
    assert len(memory["observations"]) == 1
    assert memory["patterns"] == memory["hypotheses"] == []
    assert memory["snapshot_id"] != previous["snapshot_id"]
    assert result["meta"]["cache_hits"] == 2
    empty = run_character_memory("novel", [], CHARACTERS, memory)["data"]
    assert empty["scenes"] == empty["observations"] == []
    assert empty["call_cache"] == {} and empty["complete"]


def test_text_edit_even_without_revision_bump_invalidates_requests(llm):
    previous = build()["data"]
    scenes = copy.deepcopy(SCENES)
    scenes[0]["text"] = '서진은 "부탁해."라고 말했다.'
    result = run_character_memory("novel", scenes, CHARACTERS, previous)
    assert result["meta"]["llm_calls"] > 0
    assert all(o["evidence"]["quote"] != "됐어." for o in result["data"]["observations"])
    assert result["data"]["patterns"] == []


def test_project_and_model_cache_isolation(llm, monkeypatch):
    previous = build()["data"]
    assert (
        run_character_memory("other", SCENES, CHARACTERS, previous)["error"]["code"]
        == "INVALID_INPUT"
    )
    monkeypatch.setenv("PROLOG_AI_MODEL", "different-model")
    assert build(previous_memory=previous)["meta"]["cache_hits"] == 0


def test_provider_change_invalidates_cache_even_with_same_model(llm, monkeypatch):
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "openrouter")
    monkeypatch.setenv("PROLOG_AI_MODEL", "same-model")
    previous = build()["data"]
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "nvidia")
    result = build(previous_memory=previous)
    assert result["meta"]["cache_hits"] == 0
    assert result["data"]["analysis_key"] != previous["analysis_key"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m["scenes"][0].update(text="수정된 원문"),
        lambda m: m["observations"][0]["evidence"].update(start=999),
        lambda m: m["patterns"][0]["supporting_observation_ids"].append("unknown"),
        lambda m: m["hypotheses"][0].update(status="confirmed"),
        lambda m: m["call_cache"].update(invalid={"data": b"not-json"}),
        lambda m: m.update(complete=False),
    ],
)
def test_retrieval_rejects_stale_or_corrupt_or_incomplete_memory(llm, mutate):
    memory = build()["data"]
    mutate(memory)
    assert query_character_memory(memory, "서진")["error"]["code"] == "INVALID_INPUT"


def test_retrieval_includes_counterevidence_with_patterns_and_respects_budget(llm):
    memory = build()["data"]
    full = query_character_memory(memory, "서진의 말버릇")["data"]
    (p,) = full["patterns"]
    ids = {o["observation_id"] for o in full["observations"]}
    assert set(p["supporting_observation_ids"] + p["counterexample_observation_ids"]) <= ids
    small = query_character_memory(memory, "서진", max_context_chars=2000)["data"]
    assert len(encode(small)) <= 2000
    assert small["patterns"] == [] and small["coverage"]["truncated"]
    assert small["coverage"]["exhaustive"] is False


def test_as_of_query_does_not_leak_future_observations_or_derived_hypotheses(llm):
    memory = build()["data"]
    early = query_character_memory(memory, "서진", as_of_order=31)["data"]
    assert len(early["observations"]) == 2
    assert "부탁해" not in encode(early)
    assert early["patterns"] == early["hypotheses"] == []
    assert query_character_memory(memory, "서진", as_of_order=0)["data"]["observations"] == []


def test_explicit_character_filter_and_unknown_ids(llm):
    memory = build()["data"]
    assert query_character_memory(memory, "서진", ["c2"])["data"]["observations"] == []
    assert query_character_memory(memory, "서진", ["ghost"])["error"]["code"] == "INVALID_INPUT"


def test_memory_aiq_uses_evidence_without_resending_whole_manuscript(llm):
    memory = build()["data"]
    result = run_aiq(
        "서진의 말버릇은?", "", memory=memory, as_of_order=31, review_character_details=False
    )
    assert "data" in result
    built = llm.calls[-1][1]["prompt"]
    assert "<character_memory>" in built and "됐어." in built and "부탁해." not in built
    assert "tentative" in built and "반례" in built
    assert run_aiq("질문", "", memory=None)["error"]["code"] == "INVALID_INPUT"
    assert run_aiq("질문", "가" * 9000, memory=memory)["error"]["code"] == "INVALID_INPUT"


def test_scds_memory_review_runs_even_without_keyword_candidates(llm):
    memory = build()["data"]
    event = {"character_ids": ["c1"], "content": "서진은 동생에게 도움을 청했다."}
    result = run_scds(event, [], memory=memory)
    assert result["data"]["status"] == "completed"
    assert result["data"]["rule_result"]["candidates"] == []
    (finding,) = result["data"]["character_review"]["findings"]
    assert finding["kind"] == "development" and finding["evidence"]
    assert result["data"]["conflicts"] == []
    rules = run_scds_rules(event, [])
    separate = run_scds_analysis(event, rules["data"]["rule_result"], memory=memory)
    assert separate == result


def test_invalid_memory_options_are_rejected_before_any_scds_llm_call(llm):
    event = {"character_ids": ["c1"], "content": "폭력을 썼다."}
    rules = [{"rule_id": "r1", "description": "폭력 금지", "violation_keywords": ["폭력"]}]
    result = run_scds(event, rules, memory={"invalid": True})
    assert result["error"]["code"] == "INVALID_INPUT"
    result = run_scds(event, rules, as_of_order=1)
    assert result["error"]["code"] == "INVALID_INPUT"
    assert llm.calls == []


def test_same_length_source_change_produces_new_observation_identity(llm):
    previous = build()["data"]
    scenes = copy.deepcopy(SCENES)
    scenes[0]["text"] = scenes[0]["text"].replace("동료가", "동생이")
    updated = run_character_memory("novel", scenes, CHARACTERS, previous)["data"]
    assert (
        updated["observations"][0]["observation_id"]
        != previous["observations"][0]["observation_id"]
    )


def test_review_rejects_hallucinated_evidence_and_wrong_character(llm):
    memory = build()["data"]

    def transform(name, data, result):
        if name == "CharacterReviewOutput":
            f = result["findings"][0]
            result["findings"] = [
                {**f, "observation_ids": ["unknown"]},
                {**f, "character_id": "c2"},
                {**f, "event_quote": "없는 사건"},
                f,
            ]
        return result

    llm.transform = transform
    result = run_character_review({"character_ids": ["c1"], "content": "도와줘."}, memory)
    assert len(result["data"]["findings"]) == 1
    assert result["meta"]["removed_finding_count"] == 3


def test_store_round_trip_project_isolation_and_concurrent_writer_protection(llm, tmp_path):
    path = tmp_path / "memory.sqlite3"
    memory = build()["data"]
    with MemoryStore(path) as first, MemoryStore(path) as second:
        assert first.load("novel") is None
        assert first.save(memory, expected_revision=0) == 1
        assert second.load("novel") == {"revision": 1, "memory": memory}
        with pytest.raises(ValueError, match="다른 작업"):
            second.save(memory, expected_revision=0)
        assert first.save(memory, expected_revision=1) == 2
        other = run_character_memory("other", [], CHARACTERS)["data"]
        second.save(other, expected_revision=0)
        assert first.load("novel")["revision"] == 2
    with MemoryStore(path) as reopened:
        assert reopened.load("novel")["memory"] == memory


@pytest.mark.parametrize(
    "kwargs",
    [
        {"scenes": [{**SCENES[0], "order": True}]},
        {"scenes": [SCENES[0], SCENES[0]]},
        {"scenes": [{**SCENES[0], "text": "  "}]},
        {"characters": []},
        {"chunk_chars": 0},
        {"max_llm_calls": False},
    ],
)
def test_invalid_inputs_fail_before_llm(llm, kwargs):
    args = {"project_id": "novel", "scenes": SCENES, "characters": CHARACTERS, **kwargs}
    assert run_character_memory(**args)["error"]["code"] == "INVALID_INPUT"
    assert llm.calls == []


@pytest.mark.parametrize(
    "function", [run_character_memory, query_character_memory, run_character_review]
)
def test_new_public_functions_preserve_error_envelope(function):
    assert function()["error"]["code"] == "INVALID_INPUT"
