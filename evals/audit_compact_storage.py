"""Offline materialization audit of saved compact responses; never invokes an LLM.

Input is a replay bundle containing source, batches, normalized extracts/reviews,
proposals and assessments. Compare against a saved Memory JSON. No DB writes.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact
from prolog_ai.memory.retrieval import prepare_context
from prolog_ai.memory.source import validate_memory


def audit(replay: dict, saved: dict) -> tuple[dict, dict]:
    source = replay["source"]
    with patch.object(
        compact, "call_llm", side_effect=AssertionError("Offline audit forbids API calls")
    ):
        memory = compact.build_memory(
            source["project_id"],
            source["scenes"],
            saved["characters"],
            replay["batches"],
            replay["extracts"],
            replay["reviews"],
            model=saved["model"],
        )
        compact.apply_patterns(memory, replay["proposals"], replay["assessments"])
        memory.complete = True
        validate_memory(memory.model_dump(), require_complete=True)

    old = validate_memory(saved, require_complete=True)
    old_by_id = {o.observation_id: o for o in old.observations}
    assert len(old.observations) == len(memory.observations)
    assert old.patterns == memory.patterns and old.hypotheses == memory.hypotheses
    changed_fields = Counter()
    for o in memory.observations:
        previous = old_by_id[o.observation_id].model_dump(exclude={"attribution_checks"})
        current = o.model_dump(exclude={"attribution_checks"})
        changed_fields.update(k for k in previous if previous[k] != current[k])
    # This corpus should only gain provenance, never different accepted facts.
    assert not changed_fields, changed_fields
    assert compact.synthesis_payload(old) == compact.synthesis_payload(memory)
    for query in ("서하린의 휘파람 버릇", "서윤하의 심리 변화", "하소리와 윤하의 관계"):
        assert prepare_context(saved, query) == prepare_context(memory.model_dump(), query)

    recovered = []
    unassigned = []
    known = {c.character_id: c.name for c in memory.characters}
    for o in memory.observations:
        if o.kind == "speech" or o.attribution != "uncertain":
            continue
        candidates = sorted({c.character_id for c in o.attribution_checks if c.character_id})
        row = {
            "observation_id": o.observation_id,
            "kind": o.kind,
            "quote": o.evidence.quote,
            "scene_id": o.evidence.scene_id,
            "candidate_names": [known[c] for c in candidates],
            "checks": [c.model_dump() for c in o.attribution_checks],
        }
        (recovered if candidates else unassigned).append(row)

    def count_audit(value, key):
        if not isinstance(value, dict):
            return 0
        return len(value.get(key, [])) + sum(
            count_audit(v, key) for k, v in value.items() if k != key and isinstance(v, dict)
        )

    extraction_count = sum(len(e["observations"]) for e in replay["extracts"])
    proposals = replay["proposals"]["proposals"]
    below_threshold = []
    for assessment in replay["assessments"]["assessments"]:
        if len({memory.observations[i].evidence.scene_id for i in assessment["support"]}) < 2:
            below_threshold.append(proposals[assessment["i"]]["description"])
    report = {
        "status": "passed",
        "scope": "Offline replay of all 18 chapters; original production result unchanged.",
        "api_calls": 0,
        "additional_usd": 0,
        "observations_before": len(old.observations),
        "observations_after": len(memory.observations),
        "normalized_extraction_records": extraction_count,
        "duplicate_records_collapsed": extraction_count - len(memory.observations),
        "context_only_rows_excluded": sum(
            count_audit(e.get("validation_audit"), "context_only_rows") for e in replay["extracts"]
        ),
        "withheld_literal_name_candidates": sum(
            count_audit(e.get("validation_audit"), "withheld_people") for e in replay["extracts"]
        ),
        "certain_count_unchanged": sum(o.attribution == "certain" for o in memory.observations),
        "patterns_before": len(old.patterns),
        "patterns_after": len(memory.patterns),
        "patterns_below_two_scene_threshold": below_threshold,
        "synthesis_input_unchanged": True,
        "question_contexts_unchanged": True,
        "stored_checks": sum(len(o.attribution_checks) for o in memory.observations),
        "uncertain_non_speech_records": len(recovered) + len(unassigned),
        "recovered_candidate_links": len(recovered),
        "recovered_by_kind": dict(Counter(r["kind"] for r in recovered)),
        "still_unknown": len(unassigned),
        "recovered_records": recovered,
        "unknown_records": unassigned,
        "limitations": [
            "Candidates remain uncertain; this is retention and visibility, not increased inference accuracy.",
            "No new full-novel model analysis, live DB overwrite, or browser E2E was performed.",
            "The generic dedup recipient-loss edge case is covered by a regression; this corpus lost no recipient IDs.",
            "Invalid evidence and below-threshold pattern proposals are intentionally not promoted to facts.",
        ],
    }
    return report, memory.model_dump()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-input", type=Path, required=True)
    parser.add_argument("--saved-memory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report, memory = audit(
        json.loads(args.replay_input.read_text()), json.loads(args.saved_memory.read_text())
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in [("results.json", report), ("replayed-memory.json", memory)]:
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"recovered_records", "unknown_records"}},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
