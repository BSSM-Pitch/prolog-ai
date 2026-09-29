"""다섯 모듈의 공개 함수가 USE_FAKE_LLM=1에서 스키마에 맞는 응답을 돌려주는지 확인한다."""

import pytest

from prolog_ai import (
    run_aiq,
    run_nlcd,
    run_rex,
    run_scds,
    run_scds_analysis,
    run_scds_rules,
    run_ssm,
)
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

    def fake_call(prompt, *, schema, **_):
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


def test_run_aiq_project_scope_returns_schema_shaped_response():
    result = run_aiq(
        question="주인공의 동기가 일관되나요?", manuscript_text="원고 본문", scope="project"
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
    assert result["data"]["status"] == "skipped"


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
    assert result["data"]["status"] == "skipped"


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
                {"candidate_index": 0, "severity": "high", "advice": "a"},
                {"candidate_index": 1, "severity": "low", "advice": "b"},
                {"candidate_index": -1, "severity": "low", "advice": "c"},
            ]
        }
    ]
    result = run_scds(VIOLENT_EVENT, WORLD_RULES)
    assert [c["advice"] for c in result["data"]["conflicts"]] == ["a"]
    assert result["meta"]["removed_conflict_count"] == 2


def test_run_scds_fills_conflict_fields_from_candidate(llm_calls):
    llm_calls["responses"] = [{"conflicts": [{"candidate_index": 0, "severity": "high", "advice": "a"}]}]
    result = run_scds(VIOLENT_EVENT, WORLD_RULES)
    candidate = result["data"]["rule_result"]["candidates"][0]
    assert result["data"]["conflicts"] == [
        {
            "character_id": candidate["character_id"],
            "conflict_target": candidate["conflict_target"],
            "severity": "high",
            "advice": "a",
        }
    ]
    assert result["meta"]["removed_conflict_count"] == 0
    assert f"[0] 캐릭터: {candidate['character_id']}" in llm_calls["prompts"][0]


def test_run_scds_all_outcomes_share_status_and_rule_result():
    skipped = run_scds(VIOLENT_EVENT, [])
    no_candidate = run_scds({**VIOLENT_EVENT, "content": "평화"}, WORLD_RULES)
    completed = run_scds(VIOLENT_EVENT, WORLD_RULES)
    for result, status in [(skipped, "skipped"), (no_candidate, "skipped"), (completed, "completed")]:
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


def test_run_aiq_project_scope_has_no_selection_block(llm_calls):
    llm_calls["responses"] = [{"content": "답"}]
    run_aiq("질문", "원고 본문", scope="project")
    assert "선택 구간(" not in llm_calls["prompts"][0]


# --- AIQ: 후속 질문(이전 메시지를 프롬프트에 넣음) ---


def test_run_aiq_previous_messages_are_in_prompt_in_order(llm_calls):
    llm_calls["responses"] = [{"content": "답"}]
    messages = [
        {"message_id": "msg_1", "role": "user", "content": "첫 질문", "status": "completed"},
        {"message_id": "msg_2", "role": "assistant", "content": "첫 답변", "status": "completed"},
    ]
    result = run_aiq("3장에서는 어떤 방향이 좋을까요?", "원고 본문", messages=messages)
    assert "data" in result
    prompt = llm_calls["prompts"][0]
    assert "이전 대화:\n[user] 첫 질문\n[assistant] 첫 답변" in prompt
    assert prompt.index("이전 대화:") < prompt.index("질문: 3장에서는")
    assert "msg_1" not in prompt


@pytest.mark.parametrize("messages", [None, []])
def test_run_aiq_first_question_has_no_history_block(llm_calls, messages):
    llm_calls["responses"] = [{"content": "답"}]
    run_aiq("질문", "원고 본문", messages=messages)
    assert "이전 대화:" not in llm_calls["prompts"][0]


# --- SCDS: 룰 검출(run_scds_rules)과 AI 분석(run_scds_analysis) 분리 ---

SPLIT_EVENT = {"character_ids": ["char_001"], "content": "강도를 잔혹하게 살해함"}
SPLIT_RULES = [{"rule_id": "RULE-02", "description": "폭력 회피", "violation_keywords": ["잔혹하게 살해"]}]


def test_run_scds_rules_candidate_is_queued_without_calling_llm(llm_calls):
    result = run_scds_rules(SPLIT_EVENT, SPLIT_RULES)
    assert llm_calls["prompts"] == []
    assert result["data"]["status"] == "queued"
    assert result["data"]["rule_result"]["candidates"] == [
        {
            "rule_id": "RULE-02",
            "character_id": "char_001",
            "conflict_target": "폭력 회피",
            "matched_keyword": "잔혹하게 살해",
        }
    ]
    assert result["meta"] == {}


@pytest.mark.parametrize(
    "event, world_rules, status",
    [
        (SPLIT_EVENT, [], "skipped"),
        ({"character_ids": ["char_001"], "content": "평화롭게 대화함"}, SPLIT_RULES, "skipped"),
    ],
)
def test_run_scds_rules_without_candidate(llm_calls, event, world_rules, status):
    result = run_scds_rules(event, world_rules)
    assert llm_calls["prompts"] == []
    assert result["data"]["status"] == status


def test_run_scds_analysis_uses_given_rule_result(llm_calls):
    rule_result = run_scds_rules(SPLIT_EVENT, SPLIT_RULES)["data"]["rule_result"]
    llm_calls["responses"] = [{"conflicts": [{"candidate_index": 0, "severity": "high", "advice": "조언"}]}]
    conflict = {"character_id": "char_001", "conflict_target": "폭력 회피", "severity": "high", "advice": "조언"}
    characters = [{"character_id": "char_001", "name": "피터", "core_values": ["폭력 회피"]}]

    result = run_scds_analysis(SPLIT_EVENT, rule_result, characters)

    assert result["data"] == {"status": "completed", "rule_result": rule_result, "conflicts": [conflict]}
    assert result["meta"] == {"removed_conflict_count": 0}
    assert "잔혹하게 살해" in llm_calls["prompts"][0]
    assert "폭력 회피" in llm_calls["prompts"][0]


def test_run_scds_rules_then_analysis_matches_run_scds(llm_calls):
    response = {"conflicts": [{"candidate_index": 0, "severity": "high", "advice": "조언"}]}
    llm_calls["responses"] = [response, response]
    combined = run_scds(SPLIT_EVENT, SPLIT_RULES)
    rule_result = run_scds_rules(SPLIT_EVENT, SPLIT_RULES)["data"]["rule_result"]
    assert run_scds_analysis(SPLIT_EVENT, rule_result) == combined


@pytest.mark.parametrize(
    "rule_result, status",
    [
        ({"has_candidate": False, "skipped": True, "skipped_reason": "NO_REFERENCE_DATA", "candidates": []}, "skipped"),
        ({"has_candidate": False, "skipped": False, "skipped_reason": None, "candidates": []}, "skipped"),
    ],
)
def test_run_scds_analysis_without_candidate_does_not_call_llm(llm_calls, rule_result, status):
    result = run_scds_analysis(SPLIT_EVENT, rule_result)
    assert llm_calls["prompts"] == []
    assert result["data"] == {"status": status, "rule_result": rule_result}


def test_run_scds_analysis_keeps_rule_result_when_ai_fails(llm_calls):
    from prolog_ai.core.llm import LLMFailedError

    rule_result = run_scds_rules(SPLIT_EVENT, SPLIT_RULES)["data"]["rule_result"]
    llm_calls["responses"] = [LLMFailedError("실패")]
    result = run_scds_analysis(SPLIT_EVENT, rule_result)
    assert result["error"]["code"] == "AI_ANALYSIS_FAILED"
    assert result["error"]["details"]["rule_result"] == rule_result


# --- 백엔드 정합·오류 수정 (fix/backend-alignment) ---


def test_run_nlcd_drops_blank_and_duplicate_values(llm_calls):
    text = "피터는 책임감이 강하다. Brave 하다."
    item = lambda value, evidence="책임감이 강하다": {"value": value, "evidence": evidence}
    llm_calls["responses"] = [
        {
            "personality_tags": [
                item("책임감 강함"),
                item(" 책임감 강함 "),
                item("   "),
                item("Brave", "Brave 하다"),
                item("brave", "Brave 하다"),
            ],
            "core_values": [],
            "influence_relations": [],
            "emotion_keywords": [],
        }
    ]
    result = run_nlcd(text)
    assert [i["value"] for i in result["data"]["personality_tags"]] == ["책임감 강함", "Brave"]


def test_run_rex_requires_violation_keywords(llm_calls):
    llm_calls["responses"] = [
        {"extracted_rules": [{"description": "규칙", "evidence": "원고"}]}
    ]
    result = run_rex("원고")
    assert result["error"]["code"] == "AI_EXTRACTION_FAILED"
    assert result["error"]["details"]["internal_code"] == "SCHEMA_VALIDATION_FAILED"


def test_run_rex_cleans_keywords_and_overwrites_source_chapter(llm_calls):
    llm_calls["responses"] = [
        {
            "extracted_rules": [
                {
                    "title": "  계약 마법  ",
                    "description": "마법은 계약 없이 발현될 수 없다",
                    "violation_keywords": [" 계약 없이 ", "", "  ", "계약 없이"],
                    "evidence": "계약 없이는",
                    "source_chapter": 7,
                },
                {
                    "title": "t",
                    "description": "  ",
                    "violation_keywords": ["x"],
                    "evidence": "계약 없이는",
                },
            ]
        }
    ]
    result = run_rex("마법은 계약 없이는 쓸 수 없다.")
    assert result["data"]["extracted_rules"] == [
        {
            "title": "계약 마법",
            "description": "마법은 계약 없이 발현될 수 없다",
            "violation_keywords": ["계약 없이"],
            "evidence": "계약 없이는",
            "source_chapter": None,
        }
    ]


def test_run_aiq_accepts_backend_scopes_and_rejects_whole():
    for scope in ("project", "chapter"):
        assert "data" in run_aiq("질문", "원고 본문", scope=scope)
    assert run_aiq("질문", "원고 본문", scope="whole")["error"]["code"] == "INVALID_INPUT"


def test_run_aiq_blank_manuscript_is_invalid():
    assert run_aiq("질문", "   ")["error"]["code"] == "INVALID_INPUT"


def test_run_aiq_non_integer_offsets_are_invalid_input():
    result = run_aiq("질문", "원고 본문", scope="selection", selection_range={"start": "0", "end": 2})
    assert result["error"]["code"] == "INVALID_INPUT"


def test_run_ssm_keeps_only_known_character_ids(llm_calls):
    chunk = _chunk(["node_1"], [])
    chunk["nodes"][0]["character_ids"] = ["char_001", "피터 파커", "char_001"]
    llm_calls["responses"] = [chunk, chunk]
    characters = [{"character_id": "char_001", "name": "피터 파커"}]
    result = run_ssm("원고", characters=characters)
    assert result["data"]["nodes"][0]["character_ids"] == ["char_001"]
    assert "char_001: 피터 파커" in llm_calls["prompts"][0]

    result = run_ssm("원고")
    assert result["data"]["nodes"][0]["character_ids"] == []


def test_run_ssm_invalid_characters_is_invalid_input():
    assert run_ssm("원고", characters=[{"character_id": "c1"}])["error"]["code"] == "INVALID_INPUT"


def test_run_ssm_drops_self_and_duplicate_edges(llm_calls):
    llm_calls["responses"] = [
        _chunk(["node_1", "node_2"], [("node_1", "node_1"), ("node_1", "node_2"), ("node_1", "node_2")])
    ]
    result = run_ssm("단일 원고")
    assert len(result["data"]["edges"]) == 1
    assert result["meta"]["removed_edge_count"] == 2


def test_run_ssm_failure_reports_chunk_index(llm_calls):
    llm_calls["responses"] = [_build_fake_instance, LLMFailedError("boom")]
    result = run_ssm("1장 시작\n내용1\n2장 전개\n내용2")
    assert result["error"]["details"] == {"chunk_index": 1, "chunk_count": 2}


def test_run_rex_title_fits_db_and_falls_back_to_description(llm_calls):
    rule = {"violation_keywords": [], "evidence": "계약 없이는"}
    llm_calls["responses"] = [
        {
            "extracted_rules": [
                {**rule, "title": "가" * 300, "description": "설명"},
                {**rule, "title": "   ", "description": "마법은 계약 없이 발현될 수 없다"},
            ]
        }
    ]
    rules = run_rex("마법은 계약 없이는 쓸 수 없다.")["data"]["extracted_rules"]
    assert rules[0]["title"] == "가" * 200
    assert rules[1]["title"] == "마법은 계약 없이 발현될 수 없다"


def test_run_ssm_node_title_fits_db(llm_calls):
    chunk = _chunk(["node_1"], [])
    chunk["nodes"][0]["title"] = "나" * 250
    llm_calls["responses"] = [chunk]
    result = run_ssm("단일 원고")
    assert result["data"]["nodes"][0]["title"] == "나" * 200
