"""AIQ 답변 측정 스크립트 (실제 API 호출).

questions.json의 질문마다 run_aiq를 --repeat번(기본 5번) 호출해 모든 답변을 출력하고,
질문별 정확도를 출력한다. 채점은 답변에 들어 있어야 할 말(must_include), 없어야 할 말
(must_not_include), 원고에 없는 정보일 때 "확인되지 않습니다" 같은 표현(unanswerable)으로 한다.
글자 포함 여부로 보는 대략적인 채점이라, X인 답변은 직접 읽어 보고 판단한다.

실행 (프로젝트 루트에서, .env를 셸에 불러온 뒤):
    python evals/aiq_bench/run_bench.py --workers 5
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench_common import (
    UNANSWERABLE_PHRASES,
    check_real_env,
    contains_any,
    header,
    parse_args,
    print_accuracy,
    run_parallel,
)

from prolog_ai import run_aiq

DATA_DIR = Path(__file__).parent
DEFAULT_DATA = "questions.json"


def chapter_text(manuscript: str, heading: str) -> str:
    """원고에서 heading으로 시작하는 장만 잘라 낸다. 다음 "N장"/"제N장" 줄 앞에서 끝난다."""
    start = manuscript.find(heading)
    if start < 0:
        raise ValueError(f"'{heading}' 장을 원고에서 찾지 못했습니다.")
    after = manuscript[start + len(heading):]
    match = re.search(r"^\s*(?:제\s*)?\d+\s*장", after, re.MULTILINE)
    end = start + len(heading) + (match.start() if match else len(after))
    return manuscript[start:end].strip()


def build_call(question: dict, manuscript: str) -> dict:
    # scope=chapter는 백엔드가 그 장의 본문만 넘기는 경우다(aiq/module.py SCOPES 주석).
    if question.get("chapter_heading"):
        manuscript = chapter_text(manuscript, question["chapter_heading"])
    kwargs = {
        "question": question["question"],
        "manuscript_text": manuscript,
        "scope": question.get("scope", "project"),
        "messages": question.get("messages"),
    }
    if kwargs["scope"] == "selection":
        start = manuscript.find(question["selection_text"])
        if start < 0:
            raise ValueError(f"{question['id']}: selection_text를 원고에서 찾지 못했습니다.")
        kwargs["selection_range"] = {"start": start, "end": start + len(question["selection_text"])}
    return kwargs


def failed_checks(answer: str, checks: dict) -> list[str]:
    failures = []
    for group in checks.get("must_include", []):
        if not contains_any(answer, group):
            failures.append(f"{group} 중 하나가 있어야 함")
    for word in checks.get("must_not_include", []):
        if contains_any(answer, [word]):
            failures.append(f"'{word}'가 있으면 안 됨")
    if checks.get("unanswerable") and not contains_any(answer, UNANSWERABLE_PHRASES):
        failures.append("원고에 없는 정보라는 표현이 있어야 함")
    return failures


def main() -> int:
    args = parse_args(__doc__)
    if not check_real_env():
        return 1

    data = json.loads((DATA_DIR / (args.data or DEFAULT_DATA)).read_text(encoding="utf-8"))
    manuscript, questions = data["manuscript"], data["questions"]
    calls = [build_call(q, manuscript) for q in questions]
    jobs = [call for call in calls for _ in range(args.repeat)]
    print(f"AI 호출 {len(jobs)}번을 시작합니다 (질문 {len(questions)}개 × {args.repeat}번).")
    results = run_parallel(lambda kwargs: run_aiq(**kwargs), jobs, args.workers)

    header("답변 전체")
    items = []
    for number, question in enumerate(questions, 1):
        scope = question.get("scope", "project")
        print(f"\n{number}번 질문 [{question['id']} / {question['category']} / scope={scope}]")
        if question.get("messages"):
            for message in question["messages"]:
                print(f"  (이전 대화) {message['role']}: {message['content']}")
        print(f"  질문: {question['question']}")
        outcomes = []
        for attempt in range(args.repeat):
            result = results[(number - 1) * args.repeat + attempt]
            if "error" in result:
                outcomes.append(None)
                print(f"  {attempt + 1}회차 X 에러 {result['error']['code']}: {result['error']['message']}")
                continue
            answer = result["data"]["content"]
            failures = failed_checks(answer, question["checks"])
            outcomes.append(not failures)
            print(f"  {attempt + 1}회차 {'O' if not failures else 'X'} {answer}")
            for failure in failures:
                print(f"      - {failure}")
        items.append({"label": question["id"], "category": question["category"], "results": outcomes})

    print_accuracy(items, unit="질문")
    return 0


if __name__ == "__main__":
    sys.exit(main())
