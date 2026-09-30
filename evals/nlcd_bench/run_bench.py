"""NLCD 추출 측정 스크립트 (실제 API 호출).

cases.json의 케이스마다 run_nlcd를 --repeat번(기본 5번) 호출해 모든 답변을 출력하고,
케이스별 정확도를 출력한다. 한 회차는 케이스의 checks를 모두 통과해야 정답이다.

실행 (프로젝트 루트에서, .env를 셸에 불러온 뒤):
    python evals/nlcd_bench/run_bench.py --workers 5
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench_common import (
    check_real_env,
    contains_any,
    header,
    parse_args,
    print_accuracy,
    run_parallel,
)

from prolog_ai import run_nlcd

DATA_DIR = Path(__file__).parent
DEFAULT_DATA = "cases.json"
FIELDS = ("personality_tags", "core_values", "influence_relations", "emotion_keywords")
FIELD_NAMES = {
    "personality_tags": "성격",
    "core_values": "가치",
    "influence_relations": "영향",
    "emotion_keywords": "감정",
}


def failed_checks(data: dict, checks: list[dict]) -> list[str]:
    failures = []
    for check in checks:
        field = check["field"]
        values = [item["value"] for item in data.get(field, [])]
        name = FIELD_NAMES[field]
        if check.get("empty") and values:
            failures.append(f"{name}이(가) 비어 있어야 함")
        if "any_of" in check and not any(contains_any(v, check["any_of"]) for v in values):
            failures.append(f"{name}에 {check['any_of']} 중 하나가 있어야 함")
        if "none_of" in check and any(contains_any(v, check["none_of"]) for v in values):
            failures.append(f"{name}에 {check['none_of']}가 있으면 안 됨")
    return failures


def summarize(data: dict) -> str:
    parts = []
    for field in FIELDS:
        items = data.get(field, [])
        values = [
            f"{i['value']}({i['type']})" if field == "influence_relations" and i.get("type") else i["value"]
            for i in items
        ]
        parts.append(f"{FIELD_NAMES[field]} [{', '.join(values)}]")
    return " / ".join(parts)


def main() -> int:
    args = parse_args(__doc__)
    if not check_real_env():
        return 1

    cases = json.loads((DATA_DIR / (args.data or DEFAULT_DATA)).read_text(encoding="utf-8"))["cases"]
    jobs = [case for case in cases for _ in range(args.repeat)]
    print(f"AI 호출 {len(jobs)}번을 시작합니다 (케이스 {len(cases)}개 × {args.repeat}번).")
    results = run_parallel(lambda case: run_nlcd(case["source_text"]), jobs, args.workers)

    header("답변 전체")
    items = []
    for number, case in enumerate(cases, 1):
        print(f"\n{number}번 케이스 [{case['id']} / {case['category']}]")
        print(f"  문장: {case['source_text']}")
        outcomes = []
        for attempt in range(args.repeat):
            result = results[(number - 1) * args.repeat + attempt]
            if "error" in result:
                outcomes.append(None)
                print(f"  {attempt + 1}회차 X 에러 {result['error']['code']}: {result['error']['message']}")
                continue
            failures = failed_checks(result["data"], case["checks"])
            outcomes.append(not failures)
            removed = result["meta"].get("removed_evidence_count", 0)
            removed_note = f" (근거 불일치로 {removed}개 제거)" if removed else ""
            print(f"  {attempt + 1}회차 {'O' if not failures else 'X'} {summarize(result['data'])}{removed_note}")
            for failure in failures:
                print(f"      - {failure}")
        items.append({"label": case["id"], "category": case["category"], "results": outcomes})

    print_accuracy(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
