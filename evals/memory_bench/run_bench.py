"""python -m evals.memory_bench.run_bench [--real] [--distractor-scenes 100]

관찰 anchor/화자/행동 유형과 장면 간 지지·반례 연결을 채점한다. 심리 해석의 타당성은
이 자동 점수로 검증되지 않는다. --output 보고서의 원문/해석은 별도 사람 검토 대상이다.
--real은 API 비용이 발생한다. 기본 실행은 형식 확인만 하며 품질 점수를 내지 않는다.
"""

import argparse
import json
import os
from pathlib import Path

from prolog_ai import run_character_memory
from prolog_ai.core.llm import LLMFailedError, get_llm_config

CASES_PATH = Path(__file__).with_name("cases.json")


def score_case(case, result):
    if "error" in result:
        return {"passed": False, "error": result["error"]["code"]}
    memory = result["data"]
    observations = memory["observations"]
    found = []
    for expected in case["expected_observations"]:
        found.append(
            any(
                o["evidence"]["scene_id"] == expected["scene_id"]
                and o["character_id"] == expected["character_id"]
                and o["kind"] == expected["kind"]
                and o["attribution"] == "certain"
                and expected["anchor"] in o["evidence"]["quote"]
                for o in observations
            )
        )
    false_attributions = sum(
        any(
            o["evidence"]["scene_id"] == e["scene_id"]
            and e["anchor"] in o["evidence"]["quote"]
            and o["attribution"] == "certain"
            for o in observations
        )
        for e in case.get("forbidden_certain_attribution", [])
    )
    by_id = {o["observation_id"]: o for o in observations}
    patterns_found = []
    for e in case["expected_patterns"]:
        patterns_found.append(
            any(
                p["character_id"] == e["character_id"]
                and set(e["support_scenes"])
                <= {by_id[i]["evidence"]["scene_id"] for i in p["supporting_observation_ids"]}
                and set(e["counter_scenes"])
                <= {by_id[i]["evidence"]["scene_id"] for i in p["counterexample_observation_ids"]}
                for p in memory["patterns"]
            )
        )
    extra_patterns = bool(case.get("expect_no_patterns") and memory["patterns"])
    return {
        "passed": all(found)
        and all(patterns_found)
        and not false_attributions
        and not extra_patterns,
        "observation_recall": sum(found) / len(found) if found else None,
        "pattern_checks": patterns_found,
        "false_certain_attributions": false_attributions,
        "unexpected_patterns": extra_patterns,
        "interpretation_quality": "requires_human_review",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--distractor-scenes", type=int, default=0)
    parser.add_argument("--max-calls", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.distractor_scenes < 0:
        parser.error("--distractor-scenes는 0 이상이어야 합니다")
    if args.real:
        try:
            get_llm_config().require_api_key()
        except LLMFailedError as exc:
            print(str(exc))
            return 1
        os.environ.pop("USE_FAKE_LLM", None)
    else:
        os.environ["USE_FAKE_LLM"] = "1"
        print("가짜 LLM 형식 확인: 추출/해석 품질은 측정하지 않습니다.")
    reports = []
    for case in json.loads(CASES_PATH.read_text()):
        # 입력 장면의 간격을 벌려 방해 장면이 실제 단서 사이에 놓이게 한다.
        sources = [
            {**s, "order": s["order"] * (args.distractor_scenes + 1)} for s in case["scenes"]
        ]
        sources += [
            {
                "scene_id": f"filler-{i}",
                "revision": "1",
                "order": sources[0]["order"] + i + 1,
                "text": "길가의 가로등이 켜졌다. 바람에 종이 한 장이 굴러갔다.",
            }
            for i in range(args.distractor_scenes)
        ]
        result = run_character_memory(
            case["name"], sources, case["characters"], max_llm_calls=args.max_calls
        )
        score = (
            score_case(case, result)
            if args.real
            else {
                "passed": "data" in result,
                "quality_measured": False,
            }
        )
        print(f"{case['name']}: {json.dumps(score, ensure_ascii=False)}")
        reports.append({"name": case["name"], "score": score, "result": result})
        # 오래 걸리는 실제 평가에서 뒤 케이스가 중단돼도 완료 결과를 남긴다.
        if args.output:
            args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0 if all(r["score"]["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
