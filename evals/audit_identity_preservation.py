"""Reprocess saved extraction responses; reuse original reviews, never call a model.

No new adjudications or patterns are inferred. Retain prior patterns only when
all their original cited observations still belong to the same confirmed owner.
"""

import argparse
import json
import socket
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact, compact_wire, repairs
from prolog_ai.memory.source import validate_memory


def signature(o):
    e = o["evidence"]
    return (
        e["scene_id"],
        e["revision"],
        e["start"],
        e["end"],
        o["kind"],
        o["presentation"],
        o["behavior_role"],
    )


def run(bundle, old, calls):
    batches = bundle["batches"]
    normalizations = []

    def extraction(payload, kind):
        orders = sorted({u["order"] for u in payload["units"]})
        candidates = [
            c
            for c in calls
            if c["meta"]["kind"] == kind
            and (
                c["meta"]["target_count"] == len(payload["target_ids"])
                and (kind.endswith("repair") or c["meta"]["orders"] == orders)
            )
        ]
        assert len(candidates) == 1, (kind, orders, len(candidates))
        raw = json.loads(candidates[0]["arguments"][0])
        result = compact.validate_extraction(
            payload, compact_wire.extraction_response(payload, raw)
        )
        normalizations.append(
            {
                "stage": "extract",
                "payload": payload,
                "result": result,
                "call": candidates[0]["meta"]["number"],
            }
        )
        return result

    extracts = [extraction(b, "extract") for b in batches]
    for _ in range(2):
        pending = [
            (i, compact.missing_units(b, e)) for i, (b, e) in enumerate(zip(batches, extracts))
        ]
        pending = [(i, missing) for i, missing in pending if missing]
        if not pending:
            break
        local = [compact.repair_payload(batches[i], missing, extracts[i]) for i, missing in pending]
        combined, mappings = repairs.pack("extract", local)
        result = extraction(combined, "extract_repair")
        for (i, _), output in zip(
            pending, repairs.unpack("extract", local, result, mappings), strict=True
        ):
            extracts[i] = compact.merge_extractions(
                batches[i], extracts[i], output, require_complete=False
            )
    assert all(not compact.missing_units(b, e) for b, e in zip(batches, extracts))
    affected, affected_signatures = [], set()
    for i, (b, before, after) in enumerate(zip(batches, bundle["extracts"], extracts, strict=True)):
        # Independent reviews must address exactly the same source observations.
        assert compact.verification_payload(b, before) == compact.verification_payload(b, after)
        for n, (a, z) in enumerate(zip(before["observations"], after["observations"], strict=True)):
            if (a["c"], a["a"]) == (z["c"], z["a"]):
                continue
            ev = compact.record_evidence(b, z)
            s = signature(
                {"evidence": ev, "kind": z["k"], "presentation": z["p"], "behavior_role": z["b"]}
            )
            affected_signatures.add(s)
            affected.append(
                {
                    "batch": i,
                    "index": n,
                    "quote": ev["quote"],
                    "before_subject": a["c"],
                    "before_certainty": a["a"],
                    "after_subject": z["c"],
                    "after_certainty": z["a"],
                    "identity_unresolved": z["identity_unresolved"],
                    "evidence": ev,
                }
            )
    memory = compact.build_memory(
        old["project_id"],
        old["scenes"],
        old["characters"],
        batches,
        extracts,
        bundle["reviews"],
        model=old["model"],
    )
    new = memory.model_dump()
    before_groups, after_groups = defaultdict(list), defaultdict(list)
    for o in old["observations"]:
        before_groups[signature(o)].append(o)
    for o in new["observations"]:
        after_groups[signature(o)].append(o)
    assert set(before_groups) == set(after_groups), "Source detail lost or invented"
    changes = []
    names = {c["character_id"]: c["name"] for c in old["characters"]}
    for s, after in after_groups.items():
        before = before_groups[s]
        states = lambda rows: {(o["character_id"], o["attribution"]) for o in rows}
        if states(before) != states(after):
            changes.append(
                {
                    "quote": after[0]["evidence"]["quote"],
                    "evidence": after[0]["evidence"],
                    "before": [
                        {"name": names.get(c), "attribution": a}
                        for c, a in sorted(states(before), key=str)
                    ],
                    "after": [
                        {"name": names.get(c), "attribution": a}
                        for c, a in sorted(states(after), key=str)
                    ],
                }
            )
    categories, unresolved = Counter(), []
    for o in old["observations"]:
        if o["attribution"] != "uncertain":
            continue
        checks = o["attribution_checks"]
        ex = [c for c in checks if c["stage"] == "extract"]
        ver = [c for c in checks if c["stage"] == "verify"]
        reasons = " ".join(c["reason"] for c in ver)
        if signature(o) in affected_signatures:
            cause = "identity_link_erased_subject"
        elif "번호 복구" in reasons and any(c["character_id"] is None for c in ver):
            cause = "alignment_missing_or_collision"
        elif any(word in reasons for word in ("근거 오류", "근거 범위 오류", "검증 미확정")):
            cause = "invalid_verification_evidence"
        elif any(
            c["attribution"] == "certain" and c["name"] and not c["character_id"] for c in checks
        ):
            cause = "unresolved_character_registration"
        elif any(c["attribution"] == "uncertain" or c["name"] is None for c in ex):
            cause = "extractor_uncertainty"
        elif any(c["attribution"] == "uncertain" or c["name"] is None for c in ver):
            cause = "verifier_uncertainty"
        else:
            cause = "conflicting_confirmed_subjects"
        categories[cause] += 1
        candidates = after_groups[signature(o)]
        unresolved.append(
            {
                "observation_id": o["observation_id"],
                "cause": cause,
                "evidence": o["evidence"],
                "checks": checks,
                "after": [
                    {"name": names.get(c["character_id"]), "attribution": c["attribution"]}
                    for c in candidates
                ],
            }
        )
    # Preserve the exact previous pattern evidence sets, not positional indices.
    by_id = {o.observation_id: o for o in memory.observations}
    patterns = []
    original_memory = validate_memory(old)
    for p in old["patterns"]:
        refs = p["supporting_observation_ids"] + p["counterexample_observation_ids"]
        valid = all(
            i in by_id
            and by_id[i].attribution == "certain"
            and by_id[i].character_id == p["character_id"]
            for i in refs
        )
        before_scope = {
            o["observation_id"]
            for o in old["observations"]
            if o["attribution"] == "certain" and o["character_id"] == p["character_id"]
        }
        after_scope = {
            o.observation_id
            for o in memory.observations
            if o.attribution == "certain" and o.character_id == p["character_id"]
        }
        unchanged_scope = before_scope == after_scope
        patterns.append(
            {
                "pattern_id": p["pattern_id"],
                "description": p["description"],
                "original_evidence_valid": valid,
                "evaluated_scope_unchanged": unchanged_scope,
                "retained": valid and unchanged_scope,
            }
        )
        if valid and unchanged_scope:
            memory.patterns.append(
                next(x for x in original_memory.patterns if x.pattern_id == p["pattern_id"])
            )
    kept = {p.pattern_id for p in memory.patterns}
    memory.hypotheses = [h for h in original_memory.hypotheses if h.pattern_id in kept]
    memory.complete = True
    validate_memory(memory.model_dump(), require_complete=True)
    report = {
        "additional_api_calls": 0,
        "additional_usd": 0,
        "chapters": len(old["scenes"]),
        "all_existing_detail_spans_preserved": True,
        "logical_details": len(after_groups),
        "raw_subjects_restored": len(affected),
        "restored_subject_names": dict(Counter(r["after_subject"] for r in affected)),
        "old_uncertain_causes": dict(categories),
        "old_uncertain_total": len(unresolved),
        "old_certain": sum(o["attribution"] == "certain" for o in old["observations"]),
        "new_certain": sum(o.attribution == "certain" for o in memory.observations),
        "old_uncertain": sum(o["attribution"] == "uncertain" for o in old["observations"]),
        "new_uncertain": sum(o.attribution == "uncertain" for o in memory.observations),
        "old_records": len(old["observations"]),
        "new_records": len(memory.observations),
        "changed_source_groups": len(changes),
        "retained_patterns": len(memory.patterns),
        "patterns_needing_new_review": sum(not p["retained"] for p in patterns),
        "limits": [
            "Diagnostic causes describe pipeline states, not model-written reasoning.",
            "Same-source multi-owner records are grouped for change comparison.",
            "Only previously paid independent reviews are reused; no new identity is inferred.",
            "Retained patterns preserve their prior evidence and evaluation coverage; newly restored observations have not been assessed for patterns.",
        ],
    }
    return {
        "results": report,
        "memory": memory.model_dump(),
        "restored-subjects": affected,
        "changes": changes,
        "uncertainty-audit": unresolved,
        "patterns": patterns,
        "normalized-responses": normalizations,
        "replay-input": {**bundle, "extracts": extracts},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    folder = args.run_dir
    bundle = json.loads((folder / "replay-input.json").read_text())
    old = json.loads((folder / "job-result.json").read_text())["memory"]
    calls = [json.loads(p.read_text()) for p in sorted(folder.glob("call-*.json"))]
    with (
        patch.object(
            compact, "call_llm", side_effect=AssertionError("Offline audit forbids API calls")
        ),
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("Offline audit forbids network")
        ),
    ):
        result = run(bundle, old, calls)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in result.items():
        (args.output / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(json.dumps(result["results"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
