"""REX 규칙 추출 측정 스크립트 (실제 API 호출).

manuscripts.json의 원고마다 run_rex를 --repeat번(기본 5번) 호출한다. 회차마다 뽑힌 규칙을
SCDS 룰 검출(run_scds_rules, LLM 호출 없음)에 넣어, 사건마다 후보가 생기는지로 채점한다.
- violates=true 사건: 후보가 생기면 정답 (위반 키워드가 위반을 잡았는지) → 주 지표
- violates=false 사건: 후보가 없으면 정답 (규칙을 지키는 장면을 잘못 잡지 않았는지) → 참고 지표
- expect_no_rules=true 원고: 규칙이 0개면 정답

주 지표는 위반 검출률이다. 룰 검출이 놓친 위반은 AI 분석까지 가지 못해 되돌릴 수 없다.
지키는 장면의 오검출은 SCDS AI 분석이 다시 거르므로(evals/scds_bench) 결과는 틀리지 않고
AI 호출이 한 번 늘 뿐이다. 그래서 오검출률은 "AI 추가 호출 비율"로 따로 보여 준다.

AI 호출은 원고 수 × --repeat번이다. 룰 검출은 AI를 부르지 않는다.

실행 (프로젝트 루트에서, .env를 셸에 불러온 뒤):
    python evals/rex_bench/run_bench.py --workers 5
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench_common import (
    check_real_env,
    header,
    parse_args,
    print_accuracy,
    run_parallel,
)

from prolog_ai import run_rex, run_scds_rules

DATA_DIR = Path(__file__).parent
DEFAULT_DATA = "manuscripts.json"
TEST_CHARACTER = "c_test"
CATEGORY_VIOLATION = "위반 검출 (주 지표)"
CATEGORY_KEEP = "지키는 장면 오검출 없음 (참고)"
CATEGORY_NO_RULES = "규칙 없음"


def to_world_rules(extracted_rules: list[dict]) -> list[dict]:
    return [
        {
            "rule_id": f"r_{index}",
            "title": rule.get("title") or "",
            "description": rule["description"],
            "violation_keywords": rule.get("violation_keywords") or [],
        }
        for index, rule in enumerate(extracted_rules)
    ]


def detect(event: dict, world_rules: list[dict]) -> dict | None:
    """사건에 걸린 첫 후보. 없으면 None."""
    result = run_scds_rules({"character_ids": [TEST_CHARACTER], "content": event["content"]}, world_rules)
    candidates = result.get("data", {}).get("rule_result", {}).get("candidates", [])
    return candidates[0] if candidates else None


def rate(items: list[dict], category: str, value: bool) -> tuple[int, int]:
    results = [r for item in items if item["category"] == category for r in item["results"]]
    return sum(r is value for r in results), len(results)


def print_key_metrics(items: list[dict]) -> None:
    header("핵심 지표")
    caught, total = rate(items, CATEGORY_VIOLATION, True)
    if total:
        print(f"위반 검출률 (주 지표): {caught / total:.0%} ({caught}/{total}) — 놓친 위반은 AI 분석까지 가지 못한다")
    kept, total = rate(items, CATEGORY_KEEP, True)
    if total:
        extra = total - kept
        print(f"AI 추가 호출 비율 (참고): {extra / total:.0%} ({extra}/{total}) — 지키는 장면이 후보가 돼 AI를 한 번 더 부름")


def main() -> int:
    args = parse_args(__doc__)
    if not check_real_env():
        return 1

    manuscripts = json.loads((DATA_DIR / (args.data or DEFAULT_DATA)).read_text(encoding="utf-8"))["manuscripts"]
    jobs = [m for m in manuscripts for _ in range(args.repeat)]
    print(f"AI 호출 {len(jobs)}번을 시작합니다 (원고 {len(manuscripts)}개 × {args.repeat}번).")
    results = run_parallel(lambda m: run_rex(m["text"]), jobs, args.workers)

    header("답변 전체")
    items_by_id: dict[str, dict] = {}
    for number, manuscript in enumerate(manuscripts, 1):
        print(f"\n{number}번 원고 [{manuscript['id']}]")
        if manuscript.get("expect_no_rules"):
            items_by_id[manuscript["id"]] = {"label": manuscript["id"], "category": CATEGORY_NO_RULES, "results": []}
        for event in manuscript["events"]:
            category = CATEGORY_VIOLATION if event["violates"] else CATEGORY_KEEP
            items_by_id[event["id"]] = {"label": event["id"], "category": category, "results": []}

        for attempt in range(args.repeat):
            result = results[(number - 1) * args.repeat + attempt]
            print(f"\n  {attempt + 1}회차")
            if "error" in result:
                print(f"    에러 {result['error']['code']}: {result['error']['message']}")
                if manuscript.get("expect_no_rules"):
                    items_by_id[manuscript["id"]]["results"].append(None)
                for event in manuscript["events"]:
                    items_by_id[event["id"]]["results"].append(None)
                continue

            rules = result["data"]["extracted_rules"]
            removed = result["meta"].get("removed_evidence_count", 0)
            print(f"    규칙 {len(rules)}개" + (f" (근거 불일치로 {removed}개 제거)" if removed else ""))
            for rule in rules:
                print(f"    - {rule.get('title')}: {rule['description']}")
                print(f"      키워드: {rule.get('violation_keywords')}")
            if manuscript.get("expect_no_rules"):
                ok = not rules
                items_by_id[manuscript["id"]]["results"].append(ok)
                print(f"    {'O' if ok else 'X'} 규칙이 0개여야 함")

            world_rules = to_world_rules(rules)
            for event in manuscript["events"]:
                candidate = detect(event, world_rules) if world_rules else None
                ok = (candidate is not None) == event["violates"]
                items_by_id[event["id"]]["results"].append(ok)
                expected = "후보 있어야 함" if event["violates"] else "후보 없어야 함"
                found = f"후보 있음 (키워드 '{candidate['matched_keyword']}')" if candidate else "후보 없음"
                print(f"    {'O' if ok else 'X'} [{event['id']}] {expected} → {found}: {event['content']}")

    items = list(items_by_id.values())
    print_accuracy(items, unit="항목")
    print_key_metrics(items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
