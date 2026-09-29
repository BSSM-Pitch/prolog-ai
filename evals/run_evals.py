"""평가 케이스를 로드해 각 모듈을 실행하고 결과를 채점하는 진입점.

기본값은 USE_FAKE_LLM=1이며, 이 모드에서는 형식(응답이 성공/실패 봉투 중 하나인지,
죽지 않는지)과 SCDS의 룰 검출 결과(expected_status, LLM 호출 전에 결정됨)만 채점한다.
가짜 LLM은 항상 빈 배열을 돌려주므로 expected_values(추출 품질)는 --real일 때만 채점한다.
--real의 expected_values는 기본적으로 의미 비교(evals/judge.py, LLM-as-a-judge)로 채점하고,
--exact를 주면 예전처럼 글자 비교만 한다. --show는 응답과 판단 이유를 출력한다.

케이스 내용은 API 명세에 있는 예시만 사용하고 지어내지 않는다. 원고 본문 예시가 없는
모듈(SSM, AIQ)은 expected_values 없이 형식만 확인한다.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from prolog_ai import run_aiq, run_nlcd, run_rex, run_scds, run_ssm

try:
    from evals.judge import judge_field
except ModuleNotFoundError:  # python evals/run_evals.py로 직접 실행할 때
    from judge import judge_field

CASES_DIR = Path(__file__).parent / "cases"
FUNCTIONS = {"aiq": run_aiq, "nlcd": run_nlcd, "rex": run_rex, "scds": run_scds, "ssm": run_ssm}
# 스키마마다 "값"을 나타내는 필드 이름이 다르다 (ExtractedItem.value, DraftInfluenceItem.target 등).
LABEL_KEYS = ("value", "target", "description", "conflict_target")


def load_cases(module: str | None = None) -> list[dict[str, Any]]:
    modules = [module] if module else sorted(FUNCTIONS)
    cases = []
    for mod in modules:
        mod_dir = CASES_DIR / mod
        if not mod_dir.exists():
            continue
        for path in sorted(mod_dir.glob("*.json")):
            case = json.loads(path.read_text())
            case["module"] = mod
            case["path"] = str(path)
            cases.append(case)
    return cases


def _extract_labels(items: Any) -> list[str]:
    labels = []
    for item in items or []:
        if isinstance(item, str):
            labels.append(item)
            continue
        for key in LABEL_KEYS:
            if key in item:
                labels.append(item[key])
                break
    return labels


def run_case(
    case: dict[str, Any], real: bool, exact: bool = False, show: bool = False
) -> tuple[bool, str]:
    result = FUNCTIONS[case["module"]](**case["input"])
    if show:
        print(json.dumps(result, ensure_ascii=False, indent=1))

    if set(result) not in ({"data", "meta"}, {"error"}):
        return False, f"응답 형식이 아님: 키={sorted(result)}"

    if "expected_status" in case:
        actual = result.get("data", {}).get("status")
        if actual != case["expected_status"]:
            return False, f"status 불일치: 기대 {case['expected_status']!r}, 실제 {actual!r}"

    if real and "expected_values" in case and "data" in result:
        missing = {}
        for field, expected in case["expected_values"].items():
            actual_labels = _extract_labels(result["data"].get(field))
            if exact:
                not_found = [v for v in expected if v not in actual_labels]
            else:
                not_found, records = judge_field(expected, actual_labels)
                if show:
                    for r in records:
                        print(f"  [{field}] {r['expected']!r} → {r['matched']!r} ({r['reason']})")
            if not_found:
                missing[field] = not_found
        if missing:
            return False, f"기대 값 누락: {missing}"

    return True, "ok"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=sorted(FUNCTIONS), help="이 모듈 케이스만 실행")
    parser.add_argument(
        "--real", action="store_true", help="실제 LLM API(OpenRouter)로 호출해 expected_values까지 채점"
    )
    parser.add_argument("--exact", action="store_true", help="--real 채점을 글자 비교로만 한다")
    parser.add_argument("--show", action="store_true", help="응답과 판단 이유를 출력한다")
    args = parser.parse_args(argv)

    if args.real:
        os.environ.pop("USE_FAKE_LLM", None)
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY가 없어 --real을 쓸 수 없습니다.", file=sys.stderr)
            return 1
    else:
        os.environ["USE_FAKE_LLM"] = "1"

    cases = load_cases(args.module)
    if not cases:
        print("케이스가 없습니다.")
        return 0

    failed = 0
    for case in cases:
        ok, detail = run_case(case, args.real, exact=args.exact, show=args.show)
        print(f"[{'PASS' if ok else 'FAIL'}] {case['module']}/{case['name']}: {detail}")
        if not ok:
            failed += 1

    print(f"\n{len(cases)}개 중 {len(cases) - failed}개 통과 (real={args.real})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
