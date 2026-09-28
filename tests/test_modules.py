"""다섯 모듈의 공개 함수가 USE_FAKE_LLM=1에서 스키마에 맞는 응답을 돌려주는지 확인한다."""

import pytest

from prolog_ai import run_aiq, run_nlcd, run_rex, run_scds, run_ssm
from prolog_ai.core.llm import LLMFailedError, _build_fake_instance
from prolog_ai.modules.ssm.chunking import split_into_chapters

VIOLENT_EVENT = {"character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함"}
WORLD_RULES = [
    {"rule_id": "RULE-02", "description": "폭력 회피", "violation_keywords": ["잔혹하게 살해"]}
]
PETER = {
    "character_id": "char_001",
    "name": "피터 파커",
    "personality_tags": ["책임감 강함"],
    "core_values": ["폭력 회피"],
    "influence_relations": [{"target": "벤 삼촌", "type": "영향", "status": "고인"}],
    "emotion_keywords": ["불안"],
    "status": "confirmed",
}


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")


@pytest.fixture
def llm_calls(monkeypatch):
    """runner.call_llm을 바꿔 끼운다. responses에 넣은 값을 호출 순서대로 돌려준다."""
    state = {"prompts": [], "responses": []}

    def fake_call(prompt, *, schema):
        state["prompts"].append(prompt)
        response = state["responses"][len(state["prompts"]) - 1]
        if isinstance(response, Exception):
            raise response
        return response(schema) if callable(response) else response

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", fake_call)
    return state


# --- NLCD ---


def test_run_nlcd_returns_schema_shaped_response():
    result = run_nlcd("피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다.")
    assert result == {
        "data": {
            "personality_tags": [],
            "core_values": [],
            "influence_relations": [],
            "emotion_keywords": [],
        },
        "meta": {"removed_evidence_count": 0},
    }


def test_run_nlcd_empty_input_is_invalid():
    result = run_nlcd("")
    assert result["error"]["code"] == "INVALID_INPUT"


# --- REX ---


def test_run_rex_returns_schema_shaped_response():
    result = run_rex("모든 주문은 정령과의 계약을 통해서만 발현된다.")
    assert result == {
        "data": {"extracted_rules": []},
        "meta": {"removed_evidence_count": 0},
    }


def test_run_rex_empty_input_is_invalid():
    result = run_rex("   ")
    assert result["error"]["code"] == "INVALID_INPUT"


# --- AIQ ---


def test_run_aiq_whole_scope_returns_schema_shaped_response():
    result = run_aiq(
        question="주인공의 동기가 일관되나요?", manuscript_text="원고 본문", scope="whole"
    )
    assert result == {"data": {"content": ""}, "meta": {}}


def test_run_aiq_empty_question_is_invalid():
    result = run_aiq(question="", manuscript_text="원고 본문")
    assert result["error"]["code"] == "INVALID_INPUT"


def test_run_aiq_selection_scope_missing_range_is_invalid():
    result = run_aiq(question="이 문단 어때?", manuscript_text="원고 본문", scope="selection")
    assert result["error"]["code"] == "INVALID_SELECTION_RANGE"


def test_run_aiq_selection_scope_backwards_range_is_invalid():
    result = run_aiq(
        question="이 문단 어때?",
        manuscript_text="원고 본문",
        scope="selection",
        selection_range={"start": 100, "end": 10},
    )
    assert result["error"]["code"] == "INVALID_SELECTION_RANGE"


def test_run_aiq_selection_scope_valid_range_succeeds():
    result = run_aiq(
        question="이 문단 어때?",
        manuscript_text="원고 본문입니다. 충분히 긴 원고",
        scope="selection",
        selection_range={"start": 0, "end": 10},
    )
    assert result == {"data": {"content": ""}, "meta": {}}


# --- SCDS ---


def test_run_scds_no_reference_data_is_skipped():
    event = {"character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함"}
    result = run_scds(event, world_rules=[])
    assert result["data"]["status"] == "skipped"
    assert result["data"]["rule_result"]["skipped_reason"] == "NO_REFERENCE_DATA"


def test_run_scds_no_matching_keyword_is_no_candidate():
    event = {"character_ids": ["char_001"], "content": "평화롭게 대화를 나눴다"}
    world_rules = [{"rule_id": "RULE-02", "description": "폭력 회피", "violation_keywords": ["잔혹하게 살해"]}]
    result = run_scds(event, world_rules)
    assert result["data"]["status"] == "no_candidate"


def test_run_scds_matching_keyword_calls_llm_and_returns_schema_shaped_response():
    event = {"character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함"}
    world_rules = [{"rule_id": "RULE-02", "description": "폭력 회피", "violation_keywords": ["잔혹하게 살해"]}]
    result = run_scds(event, world_rules)
    assert result["data"]["status"] == "completed"
    assert result["data"]["conflicts"] == []
    assert result["data"]["rule_result"]["has_candidate"] is True
    assert result["meta"] == {"removed_conflict_count": 0}


# --- SSM ---


def test_run_ssm_empty_input_returns_manuscript_too_short():
    result = run_ssm("")
    assert result["error"]["code"] == "MANUSCRIPT_TOO_SHORT"


def test_run_ssm_single_chunk_returns_schema_shaped_response():
    result = run_ssm("1화. 옛날 옛적에...")
    assert result == {
        "data": {"acts": [], "nodes": [], "edges": []},
        "meta": {"removed_edge_count": 0},
    }


def test_run_ssm_splits_multiple_chapters_and_merges_results():
    manuscript = "1장 시작\n내용1\n2장 전개\n내용2"
    result = run_ssm(manuscript)
    # 두 챕터로 나뉘어 run_module이 두 번 호출되어도 병합된 형태는 동일한 스키마를 따른다.
    assert result == {
        "data": {"acts": [], "nodes": [], "edges": []},
        "meta": {"removed_edge_count": 0},
    }


# --- SCDS: 캐릭터 설정 전달, 응답 형식, 지어낸 충돌 제거 ---


def test_run_scds_passes_mapped_character_settings_to_prompt(llm_calls):
    llm_calls["responses"] = [{"conflicts": []}]
    run_scds(VIOLENT_EVENT, WORLD_RULES, characters=[PETER])
    prompt = llm_calls["prompts"][0]
    assert "'values': ['폭력 회피']" in prompt
    assert "'traits': ['책임감 강함']" in prompt
    assert "'influences': ['벤 삼촌']" in prompt


def test_run_scds_only_passes_characters_in_event(llm_calls):
    other = {**PETER, "character_id": "char_999", "name": "다른 인물"}
    llm_calls["responses"] = [{"conflicts": []}]
    run_scds(VIOLENT_EVENT, WORLD_RULES, characters=[PETER, other])
    assert "다른 인물" not in llm_calls["prompts"][0]


def test_run_scds_character_settings_count_as_reference_data():
    result = run_scds(VIOLENT_EVENT, world_rules=[], characters=[PETER])
    # 캐릭터 설정이 있으면 "참조 데이터 없음"이 아니다. RULE-01 판정은 미구현이라 후보는 없다.
    assert result["data"]["status"] == "no_candidate"


def test_run_scds_characters_without_settings_still_skipped():
    empty = {"character_id": "char_001", "name": "빈 캐릭터"}
    result = run_scds(VIOLENT_EVENT, world_rules=[], characters=[empty])
    assert result["data"]["status"] == "skipped"


def test_run_scds_keeps_rule_result_when_ai_fails(llm_calls):
    llm_calls["responses"] = [LLMFailedError("down")]
    result = run_scds(VIOLENT_EVENT, WORLD_RULES)
    assert result["error"]["code"] == "AI_ANALYSIS_FAILED"
    candidates = result["error"]["details"]["rule_result"]["candidates"]
    assert candidates[0]["matched_keyword"] == "잔혹하게 살해"


def test_run_scds_drops_conflicts_not_backed_by_candidates(llm_calls):
    llm_calls["responses"] = [
        {
            "conflicts": [
                {"character_id": "char_001", "conflict_target": "폭력 회피", "severity": "high", "advice": "a"},
                {"character_id": "char_999", "conflict_target": "폭력 회피", "severity": "low", "advice": "b"},
                {"character_id": "char_001", "conflict_target": "지어낸 설정", "severity": "low", "advice": "c"},
            ]
        }
    ]
    result = run_scds(VIOLENT_EVENT, WORLD_RULES)
    assert [c["advice"] for c in result["data"]["conflicts"]] == ["a"]
    assert result["meta"]["removed_conflict_count"] == 2


def test_run_scds_all_outcomes_share_status_and_rule_result():
    skipped = run_scds(VIOLENT_EVENT, [])
    no_candidate = run_scds({**VIOLENT_EVENT, "content": "평화"}, WORLD_RULES)
    completed = run_scds(VIOLENT_EVENT, WORLD_RULES)
    for result, status in [(skipped, "skipped"), (no_candidate, "no_candidate"), (completed, "completed")]:
        assert result["data"]["status"] == status
        assert "rule_result" in result["data"]


@pytest.mark.parametrize(
    "characters",
    [
        "피터",
        [None],
        [{"name": "id 없음"}],
        [{**PETER, "core_values": "폭력 회피"}],
        [{**PETER, "influence_relations": [{"type": "영향"}]}],
    ],
)
def test_run_scds_malformed_characters_is_invalid_input(characters):
    result = run_scds(VIOLENT_EVENT, WORLD_RULES, characters=characters)
    assert result["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "rule", [{"description": "id 없음"}, {"rule_id": "R"}, {"rule_id": "R", "description": "  "}]
)
def test_run_scds_world_rule_requires_id_and_description(rule):
    result = run_scds(VIOLENT_EVENT, [rule])
    assert result["error"]["code"] == "INVALID_INPUT"


# --- SSM: 프롤로그 보존, node_id 재부여 ---


def test_split_keeps_text_before_first_heading():
    chunks = split_into_chapters("프롤로그: 중요한 복선\n1장 시작\n내용")
    assert chunks[0].startswith("프롤로그")
    assert len(chunks) == 2


def test_split_without_preface_has_no_empty_chunk():
    assert split_into_chapters("1장 시작\n내용\n2장 전개") == ["1장 시작\n내용\n", "2장 전개"]


def _chunk(node_ids, edges):
    return {
        "acts": [],
        "nodes": [
            {"node_id": nid, "type": "event", "chapter": 1, "title": "t", "summary": "s"}
            for nid in node_ids
        ],
        "edges": [{"from_node_id": a, "to_node_id": b, "relation": "causes"} for a, b in edges],
    }


def test_run_ssm_renumbers_node_ids_and_edges_across_chunks(llm_calls):
    llm_calls["responses"] = [
        _chunk(["node_1", "node_2"], [("node_1", "node_2")]),
        _chunk(["node_1", "node_2"], [("node_2", "node_1")]),
    ]
    result = run_ssm("1장 시작\n내용1\n2장 전개\n내용2")
    assert [n["node_id"] for n in result["data"]["nodes"]] == ["node_1", "node_2", "node_3", "node_4"]
    assert [(e["from_node_id"], e["to_node_id"]) for e in result["data"]["edges"]] == [
        ("node_1", "node_2"),
        ("node_4", "node_3"),
    ]


def test_run_ssm_drops_edges_to_unknown_nodes(llm_calls):
    llm_calls["responses"] = [_chunk(["node_1"], [("node_1", "node_9"), ("node_7", "node_1")])]
    result = run_ssm("단일 원고")
    assert result["data"]["edges"] == []
    assert result["meta"]["removed_edge_count"] == 2


def test_run_ssm_prologue_is_analyzed(llm_calls):
    llm_calls["responses"] = [_build_fake_instance, _build_fake_instance]
    run_ssm("프롤로그: 중요한 복선\n1장 시작\n내용")
    assert len(llm_calls["prompts"]) == 2
    assert "프롤로그" in llm_calls["prompts"][0]


# --- AIQ: 선택 구간을 프롬프트에 넣음 ---


def test_run_aiq_selection_text_is_in_prompt(llm_calls):
    manuscript = "앞부분입니다. [선택된 문단] 뒷부분입니다."
    start = manuscript.index("[")
    end = manuscript.index("]") + 1
    llm_calls["responses"] = [{"content": "답"}]
    run_aiq("어조가 어울리나요?", manuscript, scope="selection", selection_range={"start": start, "end": end})
    assert f"선택 구간({start}~{end}):\n[선택된 문단]" in llm_calls["prompts"][0]


def test_run_aiq_whole_scope_has_no_selection_block(llm_calls):
    llm_calls["responses"] = [{"content": "답"}]
    run_aiq("질문", "원고 본문", scope="whole")
    assert "선택 구간(" not in llm_calls["prompts"][0]
