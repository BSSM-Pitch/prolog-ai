"""Offline planner and exact-source replay. Never imports credentials or calls a model.

python evals/plan_compact_memory.py /path/to/saved-memory.json
"""

import argparse
import json
from pathlib import Path

from prolog_ai.memory import compact


def inspect(memory):
    batches = compact.plan(memory["scenes"])
    sources = {s["scene_id"]: s for s in memory["scenes"]}
    count = 0
    for batch in batches:
        for unit in batch["units"]:
            ev = compact.evidence(batch, [unit["id"]])
            assert sources[ev["scene_id"]]["text"][ev["start"] : ev["end"]] == ev["quote"]
            if unit["id"] in batch["target_ids"]:
                count += 1
    # Replay existing exact anchors through the new compact source representation.
    # Batch boundaries can intersect existing quotes; validate against the whole scene.
    replayed = 0
    for scene in memory["scenes"]:
        local = compact.plan([scene])
        units = {}
        for batch in local:
            for u in batch["units"]:
                units[u["start"]] = u
        payload = {"units": [{**u, "id": i} for i, u in enumerate(units[k] for k in sorted(units))]}
        for obs in memory.get("observations", []):
            e = obs["evidence"]
            if e["scene_id"] != scene["scene_id"]:
                continue
            refs = [
                u["id"] for u in payload["units"] if u["start"] < e["end"] and u["end"] > e["start"]
            ]
            full = compact.evidence(payload, refs)
            local_start = e["start"] - full["start"]
            n, start = 0, full["quote"].find(e["quote"])
            while 0 <= start < local_start:
                n += 1
                start = full["quote"].find(e["quote"], start + 1)
            assert compact.record_evidence(payload, {"e": refs, "q": e["quote"], "n": n}) == e
            replayed += 1
    return {
        "chapters": len(sources),
        "source_chars": sum(len(s["text"]) for s in sources.values()),
        "source_units_verified": count,
        "existing_anchors_replayed": replayed,
        "extraction_batches": len(batches),
        "normal_request_upper_bound": 2 * len(batches) + 2,
        "physical_request_cap": compact.MAX_REQUESTS,
        "fits_plan": 2 * len(batches) + 2 <= compact.MAX_STEPS,
        "paid_requests": 0,
        "quality_evaluated": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("memory", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(json.loads(args.memory.read_text())), ensure_ascii=False, indent=2))
