"""evals 케이스 파일과 run_evals.py 실행기를 검사한다. 기본값은 가짜 LLM이라 실제 API를 안 쓴다."""

import pytest

from evals.run_evals import FUNCTIONS, load_cases, run_case


@pytest.fixture(autouse=True)
def _fake_llm(monkeypatch):
    monkeypatch.setenv("USE_FAKE_LLM", "1")


def test_all_case_files_have_required_keys():
    cases = load_cases()
    assert cases, "케이스가 하나도 없습니다"
    for case in cases:
        assert case["module"] in FUNCTIONS
        assert isinstance(case["name"], str) and case["name"]
        assert isinstance(case["source"], str) and case["source"]
        assert isinstance(case["input"], dict)


def test_case_input_matches_function_signature():
    for case in load_cases():
        FUNCTIONS[case["module"]](**case["input"])  # TypeError면 시그니처 불일치


@pytest.mark.parametrize("module", sorted(FUNCTIONS))
def test_every_case_passes_format_check_under_fake_llm(module):
    for case in load_cases(module):
        ok, detail = run_case(case, real=False)
        assert ok, f"{case['name']}: {detail}"


def test_scds_case_status_is_decided_without_calling_llm(monkeypatch):
    def boom(prompt, *, schema, **_):
        raise AssertionError("SCDS 케이스는 LLM을 부르면 안 된다")

    monkeypatch.setattr("prolog_ai.core.runner.call_llm", boom)
    for case in load_cases("scds"):
        ok, detail = run_case(case, real=False)
        assert ok, f"{case['name']}: {detail}"


def test_main_returns_zero_for_default_fake_run(monkeypatch, capsys):
    from evals.run_evals import main

    monkeypatch.delenv("USE_FAKE_LLM", raising=False)
    assert main([]) == 0
    assert "통과" in capsys.readouterr().out


def test_main_rejects_real_without_api_key(monkeypatch):
    from evals.run_evals import main

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert main(["--real"]) == 1


def test_judge_skips_llm_for_exact_matches(monkeypatch):
    from evals import judge

    def boom(*a, **k):
        raise AssertionError("글자 일치면 LLM을 부르지 않는다")

    monkeypatch.setattr(judge, "call_llm", boom)
    missing, records = judge.judge_field(["책임감 강함"], ["책임감  강함", "기타"])
    assert missing == [] and records[0]["reason"] == "글자 일치"
    assert judge.judge_field(["x"], [])[0] == ["x"]


def test_judge_rejects_matched_value_not_in_actual(monkeypatch):
    from evals import judge

    monkeypatch.setattr(
        judge,
        "call_llm",
        lambda prompt, **_: {
            "verdicts": [
                {"expected": "정직", "matched": "정직함", "reason": "같음"},
                {"expected": "불안", "matched": "지어낸 값", "reason": "같음"},
            ]
        },
    )
    missing, _ = judge.judge_field(["정직", "불안"], ["정직함", "걱정"])
    assert missing == ["불안"]


def test_run_evals_works_as_a_script():
    """python evals/run_evals.py로 직접 실행해도 judge를 불러올 수 있어야 한다(패키지 import와 경로가 다르다)."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [sys.executable, "evals/run_evals.py"],
        cwd=root,
        env={"USE_FAKE_LLM": "1", "PATH": ""},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
