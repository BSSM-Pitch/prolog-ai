"""모듈별 측정 스크립트(evals/*_bench/run_bench.py)가 함께 쓰는 도구.

실제 API를 부르는 측정 전용이다. 채점 단위(항목)마다 --repeat번의 성공 여부를 모아
항목별·분류별·전체 정확도를 출력한다. 에러 응답은 오답으로 센다.
"""

import argparse
import os
import re
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

UNANSWERABLE_PHRASES = [
    "확인되지 않",
    "확인할 수 없",
    "나와 있지 않",
    "나오지 않",
    "언급되지 않",
    "드러나지 않",
    "알 수 없",
    "적혀 있지 않",
    "밝혀지지 않",
]


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--repeat", type=int, default=5, help="케이스마다 AI 답변을 받을 횟수 (기본 5)")
    parser.add_argument("--workers", type=int, default=1, help="동시에 보낼 요청 수 (기본 1, 순서대로)")
    parser.add_argument(
        "--data", help="측정 데이터 파일 이름 (스크립트와 같은 폴더). 검증용 세트는 기본 파일 이름 뒤에 _2 (예: cases_2.json)"
    )
    return parser.parse_args()


def check_real_env() -> bool:
    """실제 API를 부를 수 있는 환경인지 확인하고, 아니면 안내를 출력한다."""
    if os.environ.get("USE_FAKE_LLM") == "1":
        print("USE_FAKE_LLM=1이면 가짜 응답만 나옵니다. 비우고 다시 실행하세요.")
        return False
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY가 없습니다. .env를 셸에 불러오세요: set -a; source .env; set +a")
        return False
    return True


def run_parallel(fn: Callable[[Any], Any], jobs: list[Any], workers: int) -> list[Any]:
    """jobs 순서대로 결과를 돌려준다."""
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        return list(pool.map(fn, jobs))


def norm(text: str) -> str:
    """비교용: 공백을 모두 지운다."""
    return re.sub(r"\s+", "", text or "")


def contains_any(text: str, words: Iterable[str]) -> bool:
    target = norm(text)
    return any(norm(word) in target for word in words)


def header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def print_accuracy(items: list[dict[str, Any]], unit: str = "케이스") -> None:
    """items: [{"label", "category", "results": [True/False/None, ...]}]. None은 에러(오답으로 셈)."""
    header(f"{unit}별 정확도")
    by_category: dict[str, list[int]] = {}
    correct_total = count_total = 0
    for number, item in enumerate(items, 1):
        results = item["results"]
        correct = sum(r is True for r in results)
        errors = sum(r is None for r in results)
        correct_total += correct
        count_total += len(results)
        stats = by_category.setdefault(item["category"], [0, 0])
        stats[0] += correct
        stats[1] += len(results)
        error_note = f", 에러 {errors}번" if errors else ""
        rate = correct / len(results) if results else 0
        print(f"{number}번 {unit} 정확도: {rate:.0%} ({correct}/{len(results)}{error_note}) [{item['label']}]")

    print("\n분류별 정확도")
    for category, (correct, count) in by_category.items():
        print(f"  {category}: {correct / count:.0%} ({correct}/{count})")
    if count_total:
        print(f"\n전체 정확도: {correct_total / count_total:.0%} ({correct_total}/{count_total})")
