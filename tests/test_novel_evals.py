import pytest

from evals.novel_bench.run_bench import NovelAnswers, build_prompt, chapters, verify_evidence

TEXT = "제1장 시작\n\n민은 웃었다.\n\n제2장 끝\n\n민은 울었다.\n"
QUESTIONS = [{"question_id": "change", "question": "어떻게 달라졌는가?"}]


def answer(chapter=1, quote="민은 웃었다."):
    return {
        "question_id": "change",
        "answer": "변화",
        "certainty": "interpretation",
        "alternatives": [],
        "evidence": [{"chapter": chapter, "quote": quote}],
    }


def test_citation_requires_exact_quote_in_the_claimed_chapter():
    output = NovelAnswers.model_validate({"answers": [answer(), answer(2)]})
    verification = verify_evidence(TEXT, QUESTIONS, output)
    assert verification["valid_citations"] == 1
    assert verification["total_citations"] == 2
    assert not verification["all_questions_answered_once"]
    assert not verification["mechanical_checks_passed"]
    first = verification["references"][0]
    assert TEXT[first["file_start"] : first["file_end"]] == "민은 웃었다."
    assert first["line"] == 3


def test_missing_answer_does_not_count_as_complete():
    output = NovelAnswers(answers=[])
    assert not verify_evidence(TEXT, QUESTIONS, output)["all_questions_answered_once"]


def test_valid_citation_passes_only_mechanical_not_semantic_review():
    output = NovelAnswers.model_validate({"answers": [answer()]})
    result = verify_evidence(TEXT, QUESTIONS, output)
    assert result["mechanical_checks_passed"]
    assert result["semantic_accuracy"] == "requires_human_review"


def test_whitespace_does_not_count_as_evidence():
    output = NovelAnswers.model_validate({"answers": [answer(quote=" ")]})
    assert not verify_evidence(TEXT, QUESTIONS, output)["mechanical_checks_passed"]


def test_explicit_unknown_may_omit_evidence_without_inventing_a_quote():
    item = {**answer(), "answer": "본문에 나오지 않는다.", "certainty": "unknown", "evidence": []}
    output = NovelAnswers.model_validate({"answers": [item]})
    result = verify_evidence(TEXT, QUESTIONS, output)
    assert result["mechanical_checks_passed"]
    assert result["total_citations"] == 0
    assert result["semantic_accuracy"] == "requires_human_review"


def test_supported_answer_requires_evidence():
    item = {**answer(), "certainty": "supported", "evidence": []}
    output = NovelAnswers.model_validate({"answers": [item]})
    assert not verify_evidence(TEXT, QUESTIONS, output)["mechanical_checks_passed"]


def test_duplicate_chapter_ids_are_rejected():
    with pytest.raises(ValueError, match="중복"):
        chapters(TEXT + "제1장 잘못된 번호\n")


def test_grading_notes_are_not_sent_to_the_model():
    questions = [{**QUESTIONS[0], "expected_answer": "DO_NOT_LEAK_THIS_GOLD"}]
    prompt = build_prompt(TEXT, questions)
    assert TEXT in prompt and QUESTIONS[0]["question"] in prompt
    assert "DO_NOT_LEAK_THIS_GOLD" not in prompt
