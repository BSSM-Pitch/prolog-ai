"""Replay a cold-start run's recorded responses with all networking disabled."""

import argparse
import hashlib
import json
import re
import socket
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact as c
from prolog_ai.memory import compact_wire as w
from prolog_ai.memory import repairs
from prolog_ai.memory import verification_wire as v

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", type=Path, required=True)
parser.add_argument("--cases", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
P = args.run
S = json.loads((P / "source.json").read_text())
J = json.loads((P / "job-result.json").read_text())
assert S["characters"] == [] and J["compact"]["seed_characters"] == []
assert J["compact"]["requests"] <= 40
calls = [json.loads(p.read_text()) for p in sorted((P / "raw-responses").glob("call-*.json"))]
used = []


def invoke(stage, payload, kind):
    orders = sorted({u["order"] for u in payload.get("units", [])})
    count = len(payload.get("target_ids", payload.get("observations", [])))
    found = [
        d
        for d in calls
        if d["meta"]["kind"] == kind
        and d["meta"]["orders"] == orders
        and d["meta"]["target_count"] == count
    ]
    assert len(found) == 1, (kind, orders, count, len(found))
    d = found[0]
    assert d["meta"]["number"] not in used
    used.append(d["meta"]["number"])
    raw = json.loads(d["arguments"][0])
    if stage == "extract":
        return c.validate_extraction(payload, w.extraction_response(payload, raw))
    return c.validate_verification(payload, v.response(payload, raw))


def repair(stage, ps, values):
    missing = c.missing_units if stage == "extract" else c.missing_verifications
    make = c.repair_payload if stage == "extract" else c.verification_repair_payload
    merge = c.merge_extractions if stage == "extract" else c.merge_verifications
    for turn in range(2):
        pending = [(i, missing(p, x)) for i, (p, x) in enumerate(zip(ps, values)) if missing(p, x)]
        if not pending:
            return
        local = [
            make(ps[i], ms, values[i]) if stage == "extract" else make(ps[i], ms)
            for i, ms in pending
        ]
        combined, maps = repairs.pack(stage, local)
        fixed = invoke(stage, combined, stage + "_repair")
        for (i, _), out in zip(pending, repairs.unpack(stage, local, fixed, maps), strict=True):
            values[i] = merge(ps[i], values[i], out, require_complete=False)
    if stage == "verify":
        for i, p in enumerate(ps):
            values[i] = c.defer_verifications(p, values[i])
    else:
        assert not any(missing(p, x) for p, x in zip(ps, values))


with (
    patch.object(c, "call_llm", side_effect=AssertionError("No paid calls")),
    patch.object(socket.socket, "connect", side_effect=AssertionError("No network")),
):
    batches = [
        {**c.batch_payload(b, []), "allow_partial": True, "review_actions": True}
        for b in c.plan(S["scenes"])
    ]
    extracts = [invoke("extract", b, "extract") for b in batches]
    repair("extract", batches, extracts)
    batches = c.share_discovered_people(batches, extracts)
    ps = [
        {**c.verification_payload(b, e), "allow_partial": True} for b, e in zip(batches, extracts)
    ]
    reviews = [invoke("verify", p, "verify") for p in ps]
    repair("verify", ps, reviews)
    for e, p, r in zip(extracts, ps, reviews):
        disputed = set(c.ownership_disputes(e, r))
        if disputed:
            r["adjudications"] = invoke(
                "verify",
                {**c.focused_verification(p, disputed), "allow_partial": False},
                "attribution",
            )["decisions"]
    m = c.build_memory(
        S["project_id"],
        S["scenes"],
        J["memory"]["characters"],
        batches,
        extracts,
        reviews,
        model=J["memory"]["model"],
    )
    assert {
        (
            o.evidence.scene_id,
            o.evidence.start,
            o.evidence.end,
            o.kind,
            o.presentation,
            o.behavior_role,
        )
        for o in m.observations
    } == {
        (
            o["evidence"]["scene_id"],
            o["evidence"]["start"],
            o["evidence"]["end"],
            o["kind"],
            o["presentation"],
            o["behavior_role"],
        )
        for o in J["memory"]["observations"]
    }
    out = args.output
    out.mkdir(exist_ok=True, parents=True)
    m.complete = True
    from prolog_ai.memory.source import validate_memory

    validate_memory(m.model_dump(), require_complete=True)
    old = J["memory"]
    new = m.model_dump()

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

    before_confirmed = {
        (signature(o), o["character_id"])
        for o in old["observations"]
        if o["attribution"] == "certain"
    }
    after_confirmed = {
        (signature(o), o["character_id"])
        for o in new["observations"]
        if o["attribution"] == "certain"
    }
    names = {x["character_id"]: x["name"] for x in new["characters"]}
    orders = {x["scene_id"]: x["order"] for x in new["scenes"]}
    checks = []
    for case in json.loads(args.cases.read_text())["checks"]:
        order = int(re.search(r"(\d+)장", case["case"]).group(1))
        hits = [
            o
            for o in new["observations"]
            if orders[o["evidence"]["scene_id"]] == order
            and case["source_quote"] in o["evidence"]["quote"]
        ]
        checks.append(
            {
                **case,
                "captured": bool(hits),
                "context_linked": any(
                    o.get("perception_context") is not None
                    and names.get(o["perception_context"]["character_id"])
                    == case["expected_character"]
                    for o in hits
                ),
                "passed": any(
                    o["attribution"] == "certain"
                    and names.get(o["character_id"]) == case["expected_character"]
                    for o in hits
                ),
                "records": [{"character": names.get(o["character_id"]), **o} for o in hits],
            }
        )
    report = {
        "source_analysis_id": json.loads((P / "telemetry.json").read_text())["job_id"],
        "pipeline_version": c.VERSION,
        "network_blocked": True,
        "additional_api_calls": 0,
        "additional_usd": 0,
        "initial_registered_characters": 0,
        "historical_run_outputs_imported": False,
        "replayed_calls": sorted(used),
        "request_limit": c.MAX_REQUESTS,
        "previous_actual_requests": J["compact"]["requests"],
        "before": {
            "observations": len(old["observations"]),
            "certain": sum(o["attribution"] == "certain" for o in old["observations"]),
            "passed": json.loads((P / "results.json").read_text())["quality"]["passed"],
        },
        "after": {
            "observations": len(new["observations"]),
            "certain": sum(o["attribution"] == "certain" for o in new["observations"]),
            "uncertain": sum(o["attribution"] == "uncertain" for o in new["observations"]),
            "passed": sum(x["passed"] for x in checks),
            "total": len(checks),
            "context_linked": sum(x["context_linked"] for x in checks),
            "confirmed_or_context_linked": sum(x["passed"] or x["context_linked"] for x in checks),
        },
        "checks": checks,
        "all_source_detail_signatures_preserved": True,
        "previous_confirmed_attributions_lost": len(before_confirmed - after_confirmed),
        "saved_subjects_without_entity_id": sum(
            o["identity_status"] == "unlinked" for o in new["observations"]
        ),
        "patterns_pending_reanalysis": len(old["patterns"]),
        "context_inferences": [
            {
                "observation_id": o["observation_id"],
                "quote": o["evidence"]["quote"],
                "observer": names.get(o["perception_context"]["character_id"]),
                **o["perception_context"],
            }
            for o in new["observations"]
            if o.get("perception_context")
        ],
        "limits": [
            "Deterministic replay of this cold-start live run, not new model inference.",
            "New prompt behavior is not measured without new paid calls.",
            "Pattern synthesis was not rerun after expanding the resolved observations; old patterns kept separately.",
        ],
        "input_hashes": {
            str(p.relative_to(P)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                P / "source.json",
                P / "job-result.json",
                *sorted((P / "raw-responses").glob("call-*.json")),
            ]
        },
    }
    assert report["previous_confirmed_attributions_lost"] == 0
    (out / "replay-input.json").write_text(
        json.dumps(
            {
                "source": S,
                "characters": new["characters"],
                "batches": batches,
                "extracts": extracts,
                "reviews": reviews,
            },
            ensure_ascii=False,
        )
    )
    (out / "memory.json").write_text(json.dumps(new, ensure_ascii=False, indent=2))
    (out / "patterns-pending-review.json").write_text(
        json.dumps(
            {"patterns": old["patterns"], "hypotheses": old["hypotheses"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["checks", "input_hashes"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    for case in checks:
        print(
            case["case"],
            case["passed"],
            [(o["character"], o["attribution"]) for o in case["records"]],
        )
