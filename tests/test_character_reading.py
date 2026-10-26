import copy
import json

import pytest

from prolog_ai import run_aiq, run_character_reading
from prolog_ai.core.llm import LLMTimeoutError
from prolog_ai.memory.schema import Character, Evidence, Memory, Observation, Scene
from prolog_ai.memory.source import snapshot_id

CHARACTERS = [{"character_id": "c", "name": "서진"}]
SCENES = [
    {
        "scene_id": "s",
        "revision": "1",
        "order": 1,
        "text": "서진은 문이 잠긴 것을 알았다. 저도 모르게 손을 뻗었다. 손을 거두었다.",
    }
]


def ref(quote="저도 모르게 손을 뻗었다.", **changes):
    return {"scene_id": "s", "quote": quote, "occurrence": 0, **changes}


def draft():
    return {
        "content": "알고 있는 것과 반응이 어긋나지만 원인을 단정할 수 없다.",
        "certainty": "tentative",
        "answer_evidence": [ref()],
        "moments": [
            {
                "character_id": "c",
                "observations": [
                    {
                        "role": "involuntary_reaction",
                        "statement": "손을 뻗는다.",
                        "evidence": [ref()],
                    }
                ],
                "interpretation": "습관적인 행동일 수 있다.",
                "alternatives": ["잠금을 확인하려는 행동일 수 있다."],
                "counterevidence": [],
            }
        ],
    }


@pytest.fixture
def calls(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")
    state = {"calls": [], "mutate": None, "fail_review": False}

    def fake(prompt, *, schema, **options):
        data = json.loads(prompt.split("<input_json>\n", 1)[1].rsplit("\n</input_json>", 1)[0])
        name = schema.__name__
        state["calls"].append((name, data, options))
        if name == "ReadingRevision" and state["fail_review"]:
            raise LLMTimeoutError("timed out")
        value = draft()
        if name == "ReadingRevision":
            value.update(
                content="한 번의 반응만으로 숨은 동기를 확정할 수 없다.",
                verdict="revised",
                review_notes=[],
            )
        if state["mutate"]:
            state["mutate"](name, value)
        if name == "ReadingRevision":
            value.setdefault(
                "coverage_checks",
                [
                    {
                        "requirement_index": i,
                        "status": "answered",
                        "answer_excerpt": value["content"],
                    }
                    for i in range(len(data["requirements"]))
                ],
            )
        return value

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", fake)
    return state


def test_single_scene_has_grounded_moments_and_separate_source_review(calls):
    result = run_character_reading("왜 손을 뻗었나?", SCENES, CHARACTERS)
    assert "data" in result, result
    data = result["data"]
    assert data["reviewed"] and data["verdict"] == "revised"
    assert data["content"] != data["draft"]["content"]
    assert data["moments"][0]["interpretation_status"] == "tentative"
    assert len(calls["calls"]) == 2
    assert calls["calls"][1][1]["scenes"][0]["text"] == SCENES[0]["text"]
    assert calls["calls"][1][1]["draft"]["content"] == draft()["content"]
    evidence = data["moments"][0]["observations"][0]["evidence"][0]
    assert SCENES[0]["text"][evidence["start"] : evidence["end"]] == evidence["quote"]
    assert result["meta"]["semantic_accuracy"] == "requires_human_review"


@pytest.mark.parametrize("stage", ["ReadingDraft", "ReadingRevision"])
@pytest.mark.parametrize("bad", ["quote", "scene", "character"])
def test_draft_errors_are_repaired_but_final_errors_cannot_be_published(calls, stage, bad):
    def mutate(name, value):
        if name != stage:
            return
        if bad == "character":
            value["moments"][0]["character_id"] = "unknown"
        else:
            value["answer_evidence"][0].update(
                {"quote": "없는 문장"} if bad == "quote" else {"scene_id": "missing"}
            )

    calls["mutate"] = mutate
    result = run_character_reading("질문", SCENES, CHARACTERS)
    if stage == "ReadingRevision":
        assert result["error"]["details"]["internal_code"] == "INVALID_REFERENCE"
        assert "data" not in result
    else:
        assert result["data"]["reviewed"]
        assert not result["data"]["draft_reference_validation"]["valid"]
        assert not calls["calls"][1][1]["draft_reference_validation"]["valid"]
        assert result["data"]["answer_evidence"][0]["quote"] == ref()["quote"]
        assert result["data"]["moments"][0]["character_id"] == "c"


def test_review_that_repeats_bad_quote_is_rejected_and_checkpoint_can_resume(calls):
    def mutate(name, value):
        value["answer_evidence"][0]["quote"] = "없는 인용"

    calls["mutate"] = mutate
    result = run_character_reading("질문", SCENES, CHARACTERS)
    assert result["error"]["details"]["stage"] == "reading_review"
    checkpoint = result["error"]["details"]["checkpoint"]
    calls["mutate"] = None
    calls["calls"].clear()
    result = run_character_reading("질문", SCENES, CHARACTERS, previous_analysis=checkpoint)
    assert result["data"]["reviewed"]
    assert not result["data"]["draft_reference_validation"]["valid"]
    assert [c[0] for c in calls["calls"]] == ["ReadingRevision"]


def test_failed_review_preserves_draft_and_resumes_only_review(calls):
    calls["fail_review"] = True
    failed = run_character_reading("질문", SCENES, CHARACTERS)
    checkpoint = failed["error"]["details"]["checkpoint"]
    assert failed["error"]["details"]["stage"] == "reading_review"
    assert "data" not in failed
    calls["fail_review"] = False
    calls["calls"].clear()
    resumed = run_character_reading("질문", SCENES, CHARACTERS, previous_analysis=checkpoint)
    assert resumed["data"]["reviewed"]
    assert [c[0] for c in calls["calls"]] == ["ReadingRevision"]
    assert resumed["meta"]["draft_reused"]


@pytest.mark.parametrize("change", ["source", "question", "model", "effort"])
def test_checkpoint_is_invalidated_by_source_question_and_model(calls, monkeypatch, change):
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "nvidia")
    monkeypatch.setenv("PROLOG_AI_MODEL", "z-ai/glm-5.3-flash")
    failed = run_character_reading("질문", SCENES, CHARACTERS, max_llm_calls=1)
    checkpoint = failed["error"]["details"]["checkpoint"]
    scenes, question = copy.deepcopy(SCENES), "질문"
    if change == "source":
        scenes[0]["text"] += " 달라졌다."
    elif change == "question":
        question = "다른 질문"
    elif change == "model":
        monkeypatch.setenv("PROLOG_AI_MODEL", "other")
    else:
        monkeypatch.setenv("PROLOG_AI_REASONING_EFFORT", "high")
    result = run_character_reading(question, scenes, CHARACTERS, previous_analysis=checkpoint)
    assert result["error"]["code"] == "INVALID_INPUT"
    assert len(calls["calls"]) == 1


def test_missing_source_is_unknown_not_invented(calls):
    def mutate(name, value):
        value.update(
            content="원문에서 확인할 수 없다.",
            certainty="insufficient_evidence",
            answer_evidence=[],
            moments=[],
        )
        if name == "ReadingRevision":
            value["verdict"] = "insufficient_evidence"

    calls["mutate"] = mutate
    result = run_character_reading("생년월일?", SCENES, CHARACTERS)
    assert result["data"]["certainty"] == "insufficient_evidence"
    assert result["data"]["moments"] == []


def make_memory():
    scenes = [
        Scene.model_validate(SCENES[0]),
        Scene(scene_id="later", revision="1", order=2, text="미래 사건: 문을 부쉈다."),
    ]
    chars = [Character.model_validate(CHARACTERS[0])]
    q = "저도 모르게 손을 뻗었다."
    start = scenes[0].text.index(q)
    obs = Observation(
        observation_id="o",
        character_id="c",
        attribution="certain",
        kind="action",
        presentation="depicted",
        behavior_role="involuntary_reaction",
        summary="손을 뻗음",
        context="닫힌 문",
        interlocutor_ids=[],
        evidence=Evidence(scene_id="s", revision="1", start=start, end=start + len(q), quote=q),
    )
    return Memory(
        project_id="p",
        snapshot_id=snapshot_id("p", chars, scenes),
        analysis_key="k",
        model="test",
        mode="fake",
        characters=chars,
        scenes=scenes,
        observations=[obs],
        processed_scene_ids=["s", "later"],
        complete=True,
    ).model_dump()


def test_memory_aiq_uses_whole_visible_scene_for_two_pass_reading(calls):
    result = run_aiq("서진은 왜 손을 뻗었나?", "", memory=make_memory(), as_of_order=1)
    assert result["data"]["reviewed"]
    assert len(calls["calls"]) == 2
    assert calls["calls"][0][1]["scenes"][0]["text"] == SCENES[0]["text"]
    assert "미래 사건" not in json.dumps(calls["calls"], ensure_ascii=False)
    assert result["data"]["coverage"]["retrieval"]["as_of_order"] == 1


def test_oversized_inputs_are_rejected_without_model_call(calls):
    result = run_character_reading("질문", [{**SCENES[0], "text": "가" * 32001}], CHARACTERS)
    assert result["error"]["code"] == "INVALID_INPUT"
    assert calls["calls"] == []


def test_memory_aiq_preserves_error_contract_and_resumes_review(calls):
    calls["fail_review"] = True
    result = run_aiq("질문", "", memory=make_memory())
    assert result["error"]["code"] == "AI_RESPONSE_TIMEOUT"
    checkpoint = result["error"]["details"]["checkpoint"]
    calls["fail_review"] = False
    calls["calls"].clear()
    result = run_aiq("질문", "", memory=make_memory(), previous_analysis=checkpoint)
    assert result["data"]["reviewed"]
    assert [c[0] for c in calls["calls"]] == ["ReadingRevision"]


def test_memory_search_without_evidence_does_not_call_or_claim_review(calls):
    memory = make_memory()
    memory["observations"] = []
    result = run_aiq("질문", "", memory=memory)
    assert result["data"]["certainty"] == "insufficient_evidence"
    assert not result["data"]["reviewed"]
    assert calls["calls"] == []


def test_current_input_and_memory_cannot_create_duplicate_scene_ids(calls):
    from prolog_ai.memory.reading import read_from_memory
    from prolog_ai.memory.source import digest

    memory = make_memory()
    current = "현재 구간"
    sid = "current_" + digest(current)[:16]
    # 직접 어댑터 검증: 같은 ID가 이미 있으면 현재 구간에 별도 ID를 생성해야 한다.
    memory["scenes"][1]["scene_id"] = sid
    captured = {}
    import prolog_ai.memory.reading as reading_module

    original = reading_module.run_character_reading

    def read(question, scenes, characters, **kwargs):
        captured["scenes"] = scenes
        return {"data": {"coverage": {}}, "meta": {"llm_calls": 0}}

    reading_module.run_character_reading = read
    try:
        read_from_memory(
            {
                "memory": memory,
                "memory_context": {"observations": [], "coverage": {}, "snapshot_id": "s"},
                "manuscript_text": current,
                "scope": "project",
                "question": "질문",
                "messages": [],
            }
        )
    finally:
        reading_module.run_character_reading = original
    assert captured["scenes"][0]["scene_id"] != sid


def test_fake_reading_is_explicitly_marked_and_never_calls_network(monkeypatch):
    import openai

    monkeypatch.setenv("USE_FAKE_LLM", "1")

    def no_network(**kwargs):
        raise AssertionError("fake mode must not call API")

    monkeypatch.setattr(openai, "OpenAI", no_network)
    result = run_character_reading("질문", SCENES, CHARACTERS)
    assert result["meta"]["mode"] == "fake"
    assert "[FAKE]" in result["data"]["content"]
    assert result["data"]["certainty"] == "insufficient_evidence"
    assert result["data"]["moments"] == []


@pytest.mark.parametrize("defect", ["truncated", "missing_requirement", "not_in_content"])
def test_incomplete_answer_is_rejected_and_resume_receives_failed_final(calls, defect):
    def mutate(name, value):
        if name != "ReadingRevision":
            return
        if defect == "truncated":
            value["content"] = "이 행동의 변화는 다음과 같다:"
        elif defect == "missing_requirement":
            value["coverage_checks"] = [
                {"requirement_index": 1, "status": "answered", "answer_excerpt": value["content"]}
            ]
        else:
            value["coverage_checks"] = [
                {
                    "requirement_index": 0,
                    "status": "answered",
                    "answer_excerpt": "구조화 필드에만 있는 답",
                }
            ]

    calls["mutate"] = mutate
    failed = run_character_reading("반응과 선택은?", SCENES, CHARACTERS)
    details = failed["error"]["details"]
    assert details["internal_code"] == "INCOMPLETE_ANSWER"
    calls["mutate"] = None
    calls["calls"].clear()
    result = run_character_reading(
        "반응과 선택은?", SCENES, CHARACTERS, previous_analysis=details["checkpoint"]
    )
    assert "data" in result
    assert calls["calls"][0][1]["repair_feedback"]["failed_revision"]
    assert len(calls["calls"]) == 1


def test_excerpt_citations_restore_original_scene_and_absolute_offsets(calls):
    scenes = [{**SCENES[0], "source_scene_id": "chapter", "source_start": 700, "source_order": 20}]
    result = run_character_reading("왜 손을 뻗었나?", scenes, CHARACTERS)
    e = result["data"]["answer_evidence"][0]
    assert e["scene_id"] == "chapter" and e["excerpt_id"] == "s"
    assert e["start"] == 700 + SCENES[0]["text"].index(e["quote"])
    assert result["data"]["coverage"]["source_windows"][0]["start"] == 700


def test_raw_windows_recover_unextracted_detail_in_oversized_scene_without_future():
    from prolog_ai.memory.windows import select_source_windows

    text = ("평범한 풍경 묘사.\n" * 5000) + "서진은 이제 숨지 않고 종이학을 접었다.\n"
    memory = {
        "characters": CHARACTERS,
        "observations": [],
        "scenes": [
            {"scene_id": "long", "revision": "1", "order": 1, "text": text},
            {
                "scene_id": "future",
                "revision": "1",
                "order": 2,
                "text": "미래에만 공개된 종이학의 비밀.",
            },
        ],
    }
    context = {"observations": [], "coverage": {"as_of_order": 1}}
    windows = select_source_windows(memory, context, "종이학을 접는 행동은?", max_chars=3000)
    assert any("숨지 않고 종이학" in s["text"] for s in windows)
    assert sum(len(s["text"]) for s in windows) <= 3000
    assert all(s["source_scene_id"] == "long" for s in windows)
    for s in windows:
        assert s["text"] == text[s["source_start"] : s["source_start"] + len(s["text"])]


def test_format_instructions_do_not_change_retrieval(calls):
    from prolog_ai.memory.retrieval import prepare_context

    question = "서진의 손 반응은?"
    suffix = "\n답변은 500자 이내로 쓰고 근거를 제시하라. 확인할 수 없는 부분은 명시하라."
    assert prepare_context(make_memory(), question) == prepare_context(
        make_memory(), question + suffix
    )


@pytest.mark.parametrize("failed_stage", ["IndexedReadingDraft", "IndexedReadingRevision"])
def test_long_memory_resume_reuses_plan_and_preserves_time_filter(monkeypatch, failed_stage):
    monkeypatch.setenv("USE_FAKE_LLM", "1")
    memory = make_memory()
    memory["scenes"][0]["text"] += "\n평범한 풍경이다." * 4000
    memory["snapshot_id"] = snapshot_id(
        memory["project_id"],
        [Character.model_validate(c) for c in memory["characters"]],
        [Scene.model_validate(s) for s in memory["scenes"]],
    )
    seen, fail = [], True

    def fake(prompt, *, schema, **kwargs):
        data = json.loads(prompt.split("<input_json>\n", 1)[1].rsplit("\n</input_json>", 1)[0])
        seen.append((schema.__name__, data))
        assert "미래 사건" not in json.dumps(data, ensure_ascii=False)
        if schema.__name__ == "ReadingPlan":
            return {
                "requirements": ["손을 뻗은 반응을 설명"],
                "search_queries": ["저도 모르게 손을 뻗었다"],
            }
        if schema.__name__ == failed_stage and fail:
            raise LLMTimeoutError("timeout")
        eid = next(
            eid for s in data["scenes"] for eid, text in s["passages"] if ref()["quote"] in text
        )
        value = {
            "answers": [
                {
                    "requirement_index": 0,
                    "status": "answered",
                    "text": "서진은 저도 모르게 손을 뻗었다.",
                    "evidence_ids": [eid],
                }
            ],
            "certainty": "supported",
            "moments": [],
        }
        if schema.__name__ == "IndexedReadingRevision":
            value.update(verdict="retained", review_notes=[])
        return value

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", fake)
    result = run_aiq("손의 반응은?", "", memory=memory, as_of_order=1)
    checkpoint = result["error"]["details"]["checkpoint"]
    fail = False
    seen.clear()
    result = run_aiq("손의 반응은?", "", memory=memory, as_of_order=1, previous_analysis=checkpoint)
    assert "data" in result, result
    assert "ReadingPlan" not in [name for name, _ in seen]
    assert result["data"]["answer_evidence"][0]["scene_id"] == "s"
    assert result["data"]["coverage"]["source_characters"] <= 32000
