import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from replay_verifier_harness import run

from prolog_ai.memory import compact
from prolog_ai.memory.source import validate_memory

parser = argparse.ArgumentParser(
    description="Offline full-corpus verifier and pattern evidence audit"
)
parser.add_argument("--input-dir", type=Path, required=True)
parser.add_argument("--previous-memory", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
p = args.input_dir
bundle = json.loads((p / "replay-input.json").read_text())
old = json.loads(args.previous_memory.read_text())
cases = json.loads((p / "cases.json").read_text())["checks"]
started = time.perf_counter()
regression, new, audits = run(bundle, old, cases)
scenes = {s["scene_id"]: s for s in new["scenes"]}
names = {c["character_id"]: c["name"] for c in new["characters"]}


def signature(e, kind, presentation, role):
    return e["scene_id"], e["revision"], e["start"], e["end"], kind, presentation, role


def key(o):
    return signature(o["evidence"], o["kind"], o["presentation"], o["behavior_role"])


expected = set()
coverage = []
for batch, extract, review in zip(bundle["batches"], bundle["extracts"], bundle["reviews"]):
    assert not compact.missing_units(batch, extract)
    assert not compact.missing_verifications(compact.verification_payload(batch, extract), review)
    for r in extract["observations"]:
        expected.add(signature(compact.record_evidence(batch, r), r["k"], r["p"], r["b"]))
    coverage.append(
        {
            "target_units": len(batch["target_ids"]),
            "rows": len(extract["observations"]),
            "skipped_units": len(extract.get("skipped_units", [])),
        }
    )
assert expected == {key(o) for o in new["observations"]}
validate_memory(new)
assert new["characters"] == old["characters"] and new["scenes"] == old["scenes"]
oldgroups = defaultdict(list)
newgroups = defaultdict(list)
for o in old["observations"]:
    oldgroups[key(o)].append(o)
for o in new["observations"]:
    newgroups[key(o)].append(o)
changes = []
status = Counter()
for k, after in newgroups.items():
    before = oldgroups[k]
    b = {(o["character_id"], o["attribution"]) for o in before}
    a = {(o["character_id"], o["attribution"]) for o in after}
    if b == a:
        continue
    bc = {c for c, s in b if s == "certain"}
    ac = {c for c, s in a if s == "certain"}
    label = (
        "newly_confirmed"
        if not bc and ac
        else "withheld"
        if bc and not ac
        else "changed_confirmed_owner"
        if bc and ac and bc != ac
        else "other"
    )
    status[label] += 1
    changes.append(
        {
            "chapter": scenes[k[0]]["order"],
            "quote": after[0]["evidence"]["quote"],
            "change": label,
            "before": [{"name": names.get(c), "attribution": s} for c, s in b],
            "after": [{"name": names.get(c), "attribution": s} for c, s in a],
            "records": after,
        }
    )
newbyid = {o["observation_id"]: o for o in new["observations"]}
patterns = []
for pattern in old["patterns"]:

    def valid(oid, character_id=pattern["character_id"]):
        o = newbyid.get(oid)
        return o is not None and o["attribution"] == "certain" and o["character_id"] == character_id

    invalid_support = [i for i in pattern["supporting_observation_ids"] if not valid(i)]
    invalid_counter = [i for i in pattern["counterexample_observation_ids"] if not valid(i)]
    patterns.append(
        {
            "pattern_id": pattern["pattern_id"],
            "name": names[pattern["character_id"]],
            "description": pattern["description"],
            "support_count": len(pattern["supporting_observation_ids"]),
            "counter_count": len(pattern["counterexample_observation_ids"]),
            "invalid_support_ids": invalid_support,
            "invalid_counter_ids": invalid_counter,
            "existing_evidence_still_valid": not invalid_support and not invalid_counter,
        }
    )
chapters = []
for s in new["scenes"]:
    rows = [o for o in new["observations"] if o["evidence"]["scene_id"] == s["scene_id"]]
    chapters.append(
        {
            "order": s["order"],
            "observations": len(rows),
            "certain": sum(o["attribution"] == "certain" for o in rows),
            "uncertain": sum(o["attribution"] == "uncertain" for o in rows),
        }
    )
result = {
    "status": "completed",
    "scope": "All saved extraction and verification responses across 18 chapters, plus all 24 prior pattern evidence sets; no new semantic model review.",
    "api_calls": 0,
    "additional_usd": 0,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
    "chapters": chapters,
    "coverage": coverage,
    "logical_record_signatures": len(expected),
    "all_extracted_details_preserved": True,
    "all_source_quotes_and_character_refs_valid": True,
    "all_source_targets_accounted_for": True,
    "raw_inputs_and_author_roster_unchanged": True,
    "alignment_decisions": regression["aligned_decisions"],
    "source_anchor_passed": regression["after_passed"],
    "source_anchor_total": regression["case_count"],
    "observations_before": len(old["observations"]),
    "observations_after": len(new["observations"]),
    "certain_before": sum(o["attribution"] == "certain" for o in old["observations"]),
    "certain_after": sum(o["attribution"] == "certain" for o in new["observations"]),
    "uncertain_after": sum(o["attribution"] == "uncertain" for o in new["observations"]),
    "changed_logical_records": dict(status),
    "prior_patterns": len(patterns),
    "patterns_with_valid_existing_evidence": sum(
        p["existing_evidence_still_valid"] for p in patterns
    ),
    "patterns_needing_reassessment": sum(not p["existing_evidence_still_valid"] for p in patterns),
    "patterns": patterns,
    "limits": [
        "Source fidelity and ID integrity are not semantic correctness. Only nine cases have expected-name regression labels.",
        "All new attribution candidates remain model output; the whole novel has not been manually ground-truthed.",
        "Uncertain records and invalidated pattern evidence are retained for review, not silently promoted.",
        "No pattern synthesis or database overwrite.",
    ],
}
out = args.output
out.mkdir(parents=True, exist_ok=True)
for n, d in [
    ("results.json", result),
    ("changes.json", changes),
    ("partial-memory.json", new),
    ("alignment-audit.json", audits),
]:
    (out / n).write_text(json.dumps(d, ensure_ascii=False, indent=2))
print(
    json.dumps(
        {
            k: v
            for k, v in result.items()
            if k not in ["chapters", "coverage", "patterns", "limits"]
        },
        ensure_ascii=False,
        indent=2,
    )
)
for p in patterns:
    if not p["existing_evidence_still_valid"]:
        print(
            "PATTERN_REVIEW",
            p["name"],
            p["description"],
            len(p["invalid_support_ids"]),
            len(p["invalid_counter_ids"]),
        )
for c in changes:
    if c["change"] == "changed_confirmed_owner":
        print("OWNER_CHANGED", c["chapter"], c["quote"][:100], c["before"], c["after"])
