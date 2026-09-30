"""SCDS AI 분석 판정 측정 스크립트 (실제 API 호출).

events.json의 사건마다 룰 검출(run_scds_rules)을 한 번 하고, 같은 rule_result로
AI 분석(run_scds_analysis)을 --repeat번(기본 5번) 받는다. 모든 답변을 출력한 뒤
사건마다 정확도를 출력한다.

정답 판정: AI가 충돌을 하나 이상 돌려주면 "충돌"로 보고 expected_conflict와 비교한다.
에러 응답(시간 초과 등)은 오답으로 센다.

실행 (프로젝트 루트에서, .env를 셸에 불러온 뒤):
    python evals/scds_bench/run_bench.py
    python evals/scds_bench/run_bench.py --repeat 3 --workers 5
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prolog_ai import run_scds_analysis, run_scds_rules

DATA_DIR = Path(__file__).parent
DEFAULT_DATA = "events.json"


def judge(result: dict) -> tuple[bool | None, str]:
    """(AI가 충돌로 판단했는지, 출력용 설명). 에러면 판단값은 None."""
    if "error" in result:
        return None, f"에러 {result['error']['code']}: {result['error']['message']}"
    conflicts = result["data"].get("conflicts", [])
    if not conflicts:
        return False, "충돌 없음"
    lines = [f"충돌 [{c['severity']}] {c['advice']}" for c in conflicts]
    return True, "\n      ".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5, help="사건마다 AI 답변을 받을 횟수 (기본 5)")
    parser.add_argument("--workers", type=int, default=1, help="동시에 보낼 요청 수 (기본 1, 순서대로)")
    parser.add_argument("--data", help="측정 데이터 파일 이름 (이 폴더). 검증용 세트는 events_2.json")
    args = parser.parse_args()

    if os.environ.get("USE_FAKE_LLM") == "1":
        print("USE_FAKE_LLM=1이면 가짜 응답만 나옵니다. 비우고 다시 실행하세요.")
        return 1
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY가 없습니다. .env를 셸에 불러오세요: set -a; source .env; set +a")
        return 1

    bench = json.loads((DATA_DIR / (args.data or DEFAULT_DATA)).read_text(encoding="utf-8"))
    world_rules, characters, events = bench["world_rules"], bench["characters"], bench["events"]

    # 룰 검출은 결정적이라 사건마다 한 번만 한다.
    jobs = []
    for event in events:
        event_input = {"character_ids": event["character_ids"], "content": event["content"]}
        rules = run_scds_rules(event_input, world_rules, characters)
        if "error" in rules or rules["data"]["status"] != "queued":
            print(f"[{event['id']}] 룰 검출에서 후보가 나오지 않아 건너뜁니다: {rules}")
            continue
        rule_result = rules["data"]["rule_result"]
        for attempt in range(args.repeat):
            jobs.append((event, event_input, rule_result, attempt))

    total_calls = len(jobs)
    print(f"AI 호출 {total_calls}번을 시작합니다 (사건 {len(events)}개 × {args.repeat}번).\n")

    def call(job):
        _, event_input, rule_result, _ = job
        return run_scds_analysis(event_input, rule_result, characters)

    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as pool:
        results = list(pool.map(call, jobs))

    # 사건별로 모아서 출력
    by_event: dict[str, list[tuple[bool | None, str]]] = {}
    for (event, *_), result in zip(jobs, results):
        by_event.setdefault(event["id"], []).append(judge(result))

    print("=" * 70)
    print("답변 전체")
    print("=" * 70)
    for number, event in enumerate(events, 1):
        answers = by_event.get(event["id"])
        if answers is None:
            continue
        expected = "충돌" if event["expected_conflict"] else "충돌 아님"
        print(f"\n{number}번 사건 [{event['id']} / {event['category']}] 정답: {expected}")
        print(f"  사건: {event['content']}")
        for attempt, (decided, text) in enumerate(answers, 1):
            mark = "O" if decided == event["expected_conflict"] else "X"
            print(f"  {attempt}회차 {mark} {text}")

    print("\n" + "=" * 70)
    print("사건별 정확도")
    print("=" * 70)
    correct_total = 0
    by_category: dict[str, list[int]] = {}
    for number, event in enumerate(events, 1):
        answers = by_event.get(event["id"])
        if answers is None:
            continue
        correct = sum(decided == event["expected_conflict"] for decided, _ in answers)
        errors = sum(decided is None for decided, _ in answers)
        correct_total += correct
        stats = by_category.setdefault(event["category"], [0, 0])
        stats[0] += correct
        stats[1] += len(answers)
        error_note = f", 에러 {errors}번" if errors else ""
        print(
            f"{number}번 사건 정확도: {correct / len(answers):.0%} "
            f"({correct}/{len(answers)}{error_note}) [{event['id']}]"
        )

    print("\n분류별 정확도")
    for category, (correct, count) in by_category.items():
        print(f"  {category}: {correct / count:.0%} ({correct}/{count})")
    if total_calls:
        print(f"\n전체 정확도: {correct_total / total_calls:.0%} ({correct_total}/{total_calls})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
