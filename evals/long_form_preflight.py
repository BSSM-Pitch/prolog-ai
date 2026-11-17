"""Offline capacity check using the production planner; not an LLM accuracy test.

Run: python -m evals.long_form_preflight [--source /path/to/source.json]
The optional source JSON must contain `scenes`. Manuscript text is never printed.
"""

import argparse
import json
from pathlib import Path

from prolog_ai.memory import compact


def inspect(label: str, scenes: list[dict]) -> dict:
    batches = compact.plan(scenes)
    planned_steps = 2 * len(batches) + 2
    return {
        "case": label,
        "characters": sum(len(scene["text"]) for scene in scenes),
        "chapters": len(scenes),
        "batches": len(batches),
        "planned_steps": planned_steps,
        "step_limit": compact.MAX_STEPS,
        "passes_backend_plan_gate": planned_steps <= compact.MAX_STEPS,
    }


def synthetic_scenes(total: int, chapter_size: int) -> list[dict]:
    # Repeated prose checks capacity only, never comprehension or recall.
    sentence = "서윤은 기록을 읽고 창가에 앉았다. 도겸은 문을 닫고 기다렸다.\n"
    text = (sentence * (chapter_size // len(sentence) + 1))[:chapter_size]
    return [
        {"scene_id": f"s{i}", "revision": "r1", "order": i, "text": text[:remaining]}
        for i, remaining in enumerate(range(total, 0, -chapter_size), 1)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    rows = []
    if args.source:
        rows.append(inspect("existing_manuscript", json.loads(args.source.read_text())["scenes"]))
    for total, chapter_size in [(100_000, 5_000), (300_000, 5_000), (1_000_000, 5_000)]:
        rows.append(inspect(f"synthetic_{total}_{chapter_size}", synthetic_scenes(total, chapter_size)))
    print(json.dumps({"harness": compact.VERSION, "api_calls": 0, "cases": rows}, indent=2))


if __name__ == "__main__":
    main()
