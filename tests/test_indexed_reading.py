import copy
import json

import pytest

from prolog_ai.memory.indexed_reading import index_sources, run_indexed_reading
from prolog_ai.memory.reading_schema import ReadingSource

CHARACTERS = [{"character_id": "c", "name": "서진"}]
SCENES = [
    {
        "scene_id": "window",
        "source_scene_id": "chapter",
        "source_start": 80,
        "revision": "v2",
        "order": 1,
        "text": "같은 말.\n\n그는 문을 보았다.\n\n같은 말.",
    }
]


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")
    state = {"calls": [], "mutate": None}

    def fake(prompt, *, schema, **kwargs):
        data = json.loads(prompt.split("<input_json>\n", 1)[1].rsplit("\n</input_json>", 1)[0])
        state["calls"].append((schema.__name__, data))
        value = {
            "answers": [
                {
                    "requirement_index": i,
                    "status": "answered",
                    "text": f"{i + 1}번째 요구에 관한 답이다.",
                    "evidence_ids": [data["scenes"][-1]["passages"][-1][0]],
                }
                for i in range(len(data["requirements"]))
            ],
            "certainty": "supported",
            "moments": [],
        }
        if schema.__name__ == "IndexedReadingRevision":
            value.update(verdict="retained", review_notes=[])
        if state["mutate"]:
            state["mutate"](schema.__name__, value)
        return value

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", fake)
    return state


def read(**kwargs):
    return run_indexed_reading(
        "두 변화를 설명하라. 800자 이내",
        SCENES,
        CHARACTERS,
        requirements=["처음", "나중"],
        **kwargs,
    )


def test_repeated_text_id_restores_the_selected_occurrence_and_revision(model):
    result = read()
    assert "data" in result, result
    data = result["data"]
    ref = data["answer_evidence"][0]
    assert ref["start"] == 80 + SCENES[0]["text"].rindex("같은 말.")
    assert ref["end"] - ref["start"] == len(ref["quote"])
    assert ref["scene_id"] == "chapter" and ref["revision"] == "v2"
    assert data["content"] == "1번째 요구에 관한 답이다.\n\n2번째 요구에 관한 답이다."
    assert all(c["answer_excerpt"] in data["content"] for c in data["coverage_checks"])
    assert result["meta"]["semantic_accuracy"] == "requires_human_review"


@pytest.mark.parametrize(
    "bad",
    [
        "missing",
        "duplicate",
        "unknown_id",
        "blank",
        "dangling_middle",
        "bracket",
        "too_long",
        "answered_without_evidence",
    ],
)
def test_bad_final_cannot_be_published(model, bad):
    def mutate(name, value):
        if name != "IndexedReadingRevision":
            return
        answer = value["answers"][0]
        if bad == "missing":
            value["answers"].pop()
        elif bad == "duplicate":
            value["answers"][1]["requirement_index"] = 0
        elif bad == "unknown_id":
            answer["evidence_ids"] = ["p999999"]
        elif bad == "blank":
            answer["text"] = "   "
        elif bad == "dangling_middle":
            answer["text"] = "그 이유는 다음과 같다:"
        elif bad == "bracket":
            answer["text"] = "그는 “답했다."
        elif bad == "too_long":
            answer["text"] = "가" * 801
        else:
            answer["evidence_ids"] = []

    model["mutate"] = mutate
    result = read()
    assert "data" not in result
    assert result["error"]["details"]["stage"] == "reading_review"
    assert result["error"]["details"]["checkpoint"]["repair_feedback"]["failed_revision"]


def test_resume_reuses_draft_and_passes_actual_failed_final_for_repair(model):
    def mutate(name, value):
        if name == "IndexedReadingRevision":
            value["answers"][0]["evidence_ids"] = ["not-provided"]

    model["mutate"] = mutate
    failed = read()
    checkpoint = failed["error"]["details"]["checkpoint"]
    model["mutate"] = None
    model["calls"].clear()
    result = read(previous_analysis=checkpoint)
    assert "data" in result
    assert [name for name, _ in model["calls"]] == ["IndexedReadingRevision"]
    sent = model["calls"][0][1]
    assert "not-provided" in sent["repair_feedback"]["error"]
    assert sent["repair_feedback"]["failed_revision"]["answers"][0]["evidence_ids"] == [
        "not-provided"
    ]


def test_changed_source_cannot_reuse_ids_or_old_checkpoint(model):
    def mutate(name, value):
        if name == "IndexedReadingRevision":
            value["answers"].pop()

    model["mutate"] = mutate
    checkpoint = read()["error"]["details"]["checkpoint"]
    changed = copy.deepcopy(SCENES)
    changed[0]["text"] = "원문이 달라졌다."
    result = run_indexed_reading(
        "두 변화를 설명하라. 800자 이내",
        changed,
        CHARACTERS,
        requirements=["처음", "나중"],
        previous_analysis=checkpoint,
    )
    assert result["error"]["code"] == "INVALID_INPUT"


def test_all_nonwhitespace_source_characters_survive_passage_indexing():
    text = "  첫 문단.\n\n둘째\n문단.\n\n" + "아주긴문단😀" * 300 + "\n\n끝.  "
    source = ReadingSource(scene_id="s", revision="1", order=1, text=text)
    indexed, catalog = index_sources([source])
    joined = "".join(p[1] for p in indexed[0]["passages"])
    assert "".join(joined.split()) == "".join(text.split())
    assert all(
        len(c["quote"]) <= 1000
        and text[c["local_start"] : c["local_start"] + len(c["quote"])] == c["quote"]
        for c in catalog.values()
    )


def test_many_windows_with_long_metadata_fit_without_duplicating_source(model):
    scenes = [
        {
            "scene_id": "excerpt_" + str(i).zfill(24),
            "source_scene_id": "ch" + str(i),
            "source_start": 100,
            "source_order": i,
            "revision": "x" * 64,
            "chapter_id": "chapter_" + "x" * 100,
            "story_time": "x" * 100,
            "order": i,
            "text": ("등불 아래에서 손을 보았다.\n\n" * 28)[:500],
        }
        for i in range(60)
    ]
    result = run_indexed_reading(
        "무엇을 했는가? 800자 이내", scenes, CHARACTERS, requirements=["행동"]
    )
    assert "data" in result, result
    payload = model["calls"][0][1]
    assert all("text" not in scene for scene in payload["scenes"])
    assert sum(s["source_length"] for s in payload["scenes"]) == sum(len(s["text"]) for s in scenes)
    assert len(json.dumps(payload, ensure_ascii=False)) < 52000


def test_unknown_answer_is_visible_and_not_promoted_to_fact(model):
    def mutate(name, value):
        value["certainty"] = "insufficient_evidence"
        for answer in value["answers"]:
            answer.update(status="unknown", text="제공된 발췌에서 확인할 수 없다.", evidence_ids=[])

    model["mutate"] = mutate
    data = read()["data"]
    assert data["answer_evidence"] == []
    assert all(c["status"] == "unknown" for c in data["coverage_checks"])
