"""SSM 구조 분석 측정 스크립트 (실제 API 호출).

manuscripts.json의 원고마다 run_ssm을 --repeat번(기본 5번) 호출해 모든 결과를 출력하고,
check(항목)별 정확도를 출력한다. run_ssm은 챕터마다 AI를 부르므로 AI 호출은
(원고별 장 수의 합) × --repeat번이다.

check 종류
- valid_chapters: 노드 chapter와 막 chapter_from/to가 1~장 수 안이고, from <= to
- acts_order: 막 이름이 발단 → 전개 → 위기 → 절정 → 결말 순서를 거꾸로 가지 않음
- acts_cover: 첫 막이 1장에서 시작하고 마지막 막이 마지막 장에서 끝남
- node_in_chapter: 그 장의 노드 제목·요약 중 하나에 any_of의 말이 있음
- node_type_in_chapter: 그 장에 node_type 노드가 있음
- character_in_chapter: 그 장의 노드 중 하나의 character_ids에 character_id가 있음

실행 (프로젝트 루트에서, .env를 셸에 불러온 뒤):
    python evals/ssm_bench/run_bench.py --workers 3
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

from prolog_ai import run_ssm

DATA_DIR = Path(__file__).parent
DEFAULT_DATA = "manuscripts.json"
ACT_ORDER = {"발단": 0, "전개": 1, "위기": 2, "절정": 3, "결말": 4}


def passes(check: dict, data: dict, chapter_count: int) -> bool:
    acts, nodes = data["acts"], data["nodes"]
    kind = check["type"]
    if kind == "valid_chapters":
        nodes_ok = all(1 <= n["chapter"] <= chapter_count for n in nodes)
        acts_ok = all(1 <= a["chapter_from"] <= a["chapter_to"] <= chapter_count for a in acts)
        return bool(acts) and nodes_ok and acts_ok
    if kind == "acts_order":
        order = [ACT_ORDER[a["act_name"]] for a in acts if a["act_name"] in ACT_ORDER]
        return bool(order) and order == sorted(order)
    if kind == "acts_cover":
        return bool(acts) and acts[0]["chapter_from"] == 1 and acts[-1]["chapter_to"] == chapter_count
    in_chapter = [n for n in nodes if n["chapter"] == check.get("chapter")]
    if kind == "node_in_chapter":
        return any(contains_any(n["title"] + " " + n["summary"], check["any_of"]) for n in in_chapter)
    if kind == "node_type_in_chapter":
        return any(n["type"] == check["node_type"] for n in in_chapter)
    if kind == "character_in_chapter":
        return any(check["character_id"] in n.get("character_ids", []) for n in in_chapter)
    raise ValueError(f"알 수 없는 check 종류: {kind}")


def print_structure(data: dict, meta: dict) -> None:
    for act in data["acts"]:
        print(f"    막 {act['act_name']} ({act['chapter_from']}~{act['chapter_to']}장): {act['summary']}")
    for node in data["nodes"]:
        chars = f" {node['character_ids']}" if node.get("character_ids") else ""
        print(f"    노드 {node['node_id']} [{node['chapter']}장 {node['type']}]{chars} {node['title']}: {node['summary']}")
    chapter_of = {n["node_id"]: n["chapter"] for n in data["nodes"]}
    cross = sum(chapter_of.get(e["from_node_id"]) != chapter_of.get(e["to_node_id"]) for e in data["edges"])
    removed = meta.get("removed_edge_count", 0)
    print(f"    연결 {len(data['edges'])}개 (챕터를 넘는 연결 {cross}개, 제거 {removed}개)")


def main() -> int:
    args = parse_args(__doc__)
    if not check_real_env():
        return 1

    manuscripts = json.loads((DATA_DIR / (args.data or DEFAULT_DATA)).read_text(encoding="utf-8"))["manuscripts"]
    jobs = [m for m in manuscripts for _ in range(args.repeat)]
    chapter_calls = sum(m["chapter_count"] for m in manuscripts) * args.repeat
    print(f"run_ssm {len(jobs)}번, AI 호출 약 {chapter_calls}번을 시작합니다 (원고 {len(manuscripts)}개 × {args.repeat}번).")
    results = run_parallel(lambda m: run_ssm(m["text"], m.get("characters")), jobs, args.workers)

    header("답변 전체")
    items = []
    for number, manuscript in enumerate(manuscripts, 1):
        print(f"\n{number}번 원고 [{manuscript['id']}, {manuscript['chapter_count']}장]")
        outcomes: dict[str, list] = {check["id"]: [] for check in manuscript["checks"]}
        for attempt in range(args.repeat):
            result = results[(number - 1) * args.repeat + attempt]
            print(f"\n  {attempt + 1}회차")
            if "error" in result:
                print(f"    에러 {result['error']['code']}: {result['error']['message']}")
                for check in manuscript["checks"]:
                    outcomes[check["id"]].append(None)
                continue
            print_structure(result["data"], result["meta"])
            marks = []
            for check in manuscript["checks"]:
                ok = passes(check, result["data"], manuscript["chapter_count"])
                outcomes[check["id"]].append(ok)
                marks.append(f"{'O' if ok else 'X'} {check['id']}")
            print("    채점: " + ", ".join(marks))
        for check in manuscript["checks"]:
            items.append({"label": check["id"], "category": check["category"], "results": outcomes[check["id"]]})

    print_accuracy(items, unit="항목")
    return 0


if __name__ == "__main__":
    sys.exit(main())
