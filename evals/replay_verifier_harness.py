"""Replay saved extraction/verification responses without provider or synthesis calls.

Expected labels are used only for evaluation, never by production realignment.
The output is a partial attribution-only Memory, not a new completed analysis.
"""

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact
from prolog_ai.memory.source import encode, validate_memory
from prolog_ai.memory.verification_alignment import VERSION, realign


def run(bundle, previous, cases):
    source = bundle["source"]
    before = encode(bundle)
    started = time.perf_counter()
    with patch.object(
        compact, "call_llm", side_effect=AssertionError("Offline replay forbids API calls")
    ):
        memory = compact.build_memory(
            source["project_id"],
            source["scenes"],
            previous["characters"],
            bundle["batches"],
            bundle["extracts"],
            bundle["reviews"],
            model=previous["model"],
        )
    assert encode(bundle) == before
    validate_memory(memory.model_dump())
    assert not memory.complete and not memory.patterns
    names = {c.character_id: c.name for c in memory.characters}
    orders = {s.scene_id: s.order for s in memory.scenes}
    old_names = {c["character_id"]: c["name"] for c in previous["characters"]}
    checked = []
    for case in cases:
        order = int(re.search(r"(\d+)장", case["case"]).group(1))
        hits = [
            o
            for o in memory.observations
            if orders[o.evidence.scene_id] == order and case["source_quote"] in o.evidence.quote
        ]
        old = [
            o
            for o in previous["observations"]
            if orders[o["evidence"]["scene_id"]] == order
            and case["source_quote"] in o["evidence"]["quote"]
        ]
        checked.append(
            {
                "case": case["case"],
                "expected_character": case["expected_character"],
                "before_passed": any(
                    o["attribution"] == "certain"
                    and old_names.get(o["character_id"]) == case["expected_character"]
                    for o in old
                ),
                "after_passed": any(
                    o.attribution == "certain"
                    and names.get(o.character_id) == case["expected_character"]
                    for o in hits
                ),
                "records": [o.model_dump() for o in hits],
            }
        )
    alignment = []
    for batch, extracted, review in zip(
        bundle["batches"], bundle["extracts"], bundle["reviews"], strict=True
    ):
        aligned = realign(compact.verification_payload(batch, extracted), review)
        audit = aligned.get("validation_audit", {}).get("source_alignment")
        alignment.append(audit)
    result = {
        "harness_version": VERSION,
        "api_calls": 0,
        "additional_usd": 0,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "source_chapters": len(memory.scenes),
        "original_inputs_unchanged": True,
        "before_passed": sum(c["before_passed"] for c in checked),
        "after_passed": sum(c["after_passed"] for c in checked),
        "case_count": len(checked),
        "aligned_decisions": sum(len(run) for a in alignment if a for run in a["runs"]),
        "new_attribution_counts": dict(Counter(o.attribution for o in memory.observations)),
        "observations": len(memory.observations),
        "checks": checked,
        "limitations": [
            "Offline replay, not fresh model performance or overall accuracy.",
            "No synthesis rerun and no live DB overwrite.",
            "Four exact consecutive source matches detect systematic index drift; isolated context references remain untouched.",
            "A direct competing decision or ambiguous source span remains uncertain.",
        ],
    }
    return result, memory.model_dump(), alignment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--previous-memory", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-all", action="store_true", help="Fail if any expected case is not confirmed"
    )
    args = parser.parse_args()
    result, memory, audits = run(
        json.loads(args.bundle.read_text()),
        json.loads(args.previous_memory.read_text()),
        json.loads(args.cases.read_text())["checks"],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("results.json", result),
        ("partial-memory.json", memory),
        ("alignment-audit.json", audits),
    ]:
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(
        json.dumps({k: v for k, v in result.items() if k != "checks"}, ensure_ascii=False, indent=2)
    )
    for c in result["checks"]:
        print(c["case"], c["before_passed"], "->", c["after_passed"])
    if any(c["before_passed"] and not c["after_passed"] for c in result["checks"]):
        raise SystemExit("Regression: a previously passing case failed")
    if args.require_all and result["after_passed"] != result["case_count"]:
        raise SystemExit("Not all expected attributions passed")


if __name__ == "__main__":
    main()
