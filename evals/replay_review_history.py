"""Offline review reuse audit; keeps prior paid inputs immutable."""

import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact
from prolog_ai.memory.review_history import reuse_reviews
from prolog_ai.memory.source import validate_memory

parser = argparse.ArgumentParser(
    description="Replay previously paid reviews against unchanged source without network access"
)
parser.add_argument("--current-memory", type=Path, required=True)
parser.add_argument("--prior-bundle", type=Path, required=True)
parser.add_argument("--prior-memory", type=Path, required=True)
parser.add_argument("--pattern-memory", type=Path, required=True)
parser.add_argument("--source-analysis-id", required=True)
parser.add_argument("--output", type=Path, required=True)
a = parser.parse_args()


def read_memory(path):
    data = json.loads(path.read_text())
    return data.get("memory", data)


old = read_memory(a.current_memory)
bundle = json.loads(a.prior_bundle.read_text())
source = bundle["source"]
priorjob = {"memory": read_memory(a.prior_memory)}
out = a.output
out.mkdir(parents=True, exist_ok=True)
with (
    patch.object(compact, "call_llm", side_effect=AssertionError("No API calls")),
    patch.object(socket.socket, "connect", side_effect=AssertionError("No network")),
):
    prior = compact.build_memory(
        source["project_id"],
        source["scenes"],
        priorjob["memory"]["characters"],
        bundle["batches"],
        bundle["extracts"],
        bundle["reviews"],
        model=priorjob["memory"]["model"],
    )
    prior.complete = True
    validate_memory(prior.model_dump(), require_complete=True)
    m = validate_memory(old, require_complete=True)
    m.patterns = []
    m.hypotheses = []
    audit = reuse_reviews(m, prior.model_dump(), analysis_id=a.source_analysis_id)
    priorpatterns = read_memory(a.pattern_memory)
    pattern_audit = []
    byid = {o.observation_id: o for o in m.observations}
    for ptn in priorpatterns["patterns"]:
        refs = ptn["supporting_observation_ids"] + ptn["counterexample_observation_ids"]
        valid = all(
            i in byid
            and byid[i].attribution == "certain"
            and byid[i].character_id == ptn["character_id"]
            for i in refs
        )
        oldscope = {
            o["observation_id"]
            for o in priorpatterns["observations"]
            if o["attribution"] == "certain" and o["character_id"] == ptn["character_id"]
        }
        newscope = {
            o.observation_id
            for o in m.observations
            if o.attribution == "certain" and o.character_id == ptn["character_id"]
        }
        kept = valid and oldscope == newscope
        pattern_audit.append(
            {"pattern_id": ptn["pattern_id"], "description": ptn["description"], "retained": kept}
        )
        if kept:
            from prolog_ai.memory.schema import Pattern

            m.patterns.append(Pattern.model_validate(ptn))
    kept = {p.pattern_id for p in m.patterns}
    from prolog_ai.memory.schema import Hypothesis

    m.hypotheses = [
        Hypothesis.model_validate(h) for h in priorpatterns["hypotheses"] if h["pattern_id"] in kept
    ]
    validate_memory(m.model_dump(), require_complete=True)
    for name, data in [
        ("memory", m.model_dump()),
        ("history-source-memory", prior.model_dump()),
        ("reuse-audit", audit),
        ("patterns", pattern_audit),
    ]:
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def signatures(rows):
        return {
            (
                o["evidence"]["scene_id"],
                o["evidence"]["revision"],
                o["evidence"]["start"],
                o["evidence"]["end"],
                o["kind"],
                o["presentation"],
                o["behavior_role"],
            )
            for o in rows
        }

    assert signatures(old["observations"]) == signatures(m.model_dump()["observations"])
    report = {
        "additional_api_calls": 0,
        "additional_usd": 0,
        "source_analysis_id": a.source_analysis_id,
        "chapters": len(m.scenes),
        "reused_reviews": len(audit["reused"]),
        "blocked_competing_proof": len(audit["blocked"]),
        "observations_before": len(old["observations"]),
        "observations_after": len(m.observations),
        "certain_before": sum(o["attribution"] == "certain" for o in old["observations"]),
        "certain_after": sum(o.attribution == "certain" for o in m.observations),
        "uncertain_after": sum(o.attribution == "uncertain" for o in m.observations),
        "all_source_spans_preserved": True,
        "roster_unchanged": old["characters"] == m.model_dump()["characters"],
        "retained_patterns": len(m.patterns),
        "patterns_pending_review": sum(not p["retained"] for p in pattern_audit),
        "limits": [
            "Reuses an earlier paid run on the identical manuscript; not a fresh model evaluation.",
            "No semantic re-review of patterns; original patterns with changed review coverage retained separately for review.",
            "Stored uncertainty and conflicting checks are preserved alongside the reused review.",
        ],
    }
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
