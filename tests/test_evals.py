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
