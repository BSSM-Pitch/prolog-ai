"""다섯 모듈의 공개 함수가 USE_FAKE_LLM=1에서 스키마에 맞는 응답을 돌려주는지 확인한다."""

import pytest

from prolog_ai import run_aiq, run_nlcd, run_rex, run_scds, run_ssm


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")


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
    assert result == {"data": {"conflicts": []}, "meta": {}}


# --- SSM ---


def test_run_ssm_empty_input_returns_manuscript_too_short():
    result = run_ssm("")
    assert result["error"]["code"] == "MANUSCRIPT_TOO_SHORT"


def test_run_ssm_single_chunk_returns_schema_shaped_response():
    result = run_ssm("1화. 옛날 옛적에...")
    assert result == {"data": {"acts": [], "nodes": [], "edges": []}, "meta": {}}


def test_run_ssm_splits_multiple_chapters_and_merges_results():
    manuscript = "1장 시작\n내용1\n2장 전개\n내용2"
    result = run_ssm(manuscript)
    # 두 챕터로 나뉘어 run_module이 두 번 호출되어도 병합된 형태는 동일한 스키마를 따른다.
    assert result == {"data": {"acts": [], "nodes": [], "edges": []}, "meta": {}}
