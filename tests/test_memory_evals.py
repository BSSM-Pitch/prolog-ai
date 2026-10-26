import json

from evals.memory_bench.run_bench import CASES_PATH, main, score_case


def test_error_is_not_quality_success():
    case = json.loads(CASES_PATH.read_text())[0]
    assert not score_case(case, {"error": {"code": "AI_ANALYSIS_FAILED"}})["passed"]


def test_empty_extraction_is_not_quality_success():
    case = json.loads(CASES_PATH.read_text())[0]
    score = score_case(case, {"data": {"observations": [], "patterns": []}})
    assert not score["passed"] and score["observation_recall"] == 0


def test_fake_benchmark_labels_quality_as_unmeasured(monkeypatch, capsys):
    monkeypatch.setenv("USE_FAKE_LLM", "1")
    assert main(["--distractor-scenes", "5"]) == 0
    assert "품질은 측정하지 않습니다" in capsys.readouterr().out


def test_real_benchmark_requires_key(monkeypatch):
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert main(["--real"]) == 1


def test_real_benchmark_checks_selected_providers_key(monkeypatch, capsys):
    monkeypatch.setenv("PROLOG_AI_PROVIDER", "nvidia")
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-for-nvidia")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert main(["--real"]) == 1
    assert "NVIDIA_API_KEY" in capsys.readouterr().out
