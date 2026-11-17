"""Inspect cold-pass wire invariants. This does not measure model accuracy."""

import argparse
import json
import socket
from pathlib import Path
from unittest.mock import patch

from prolog_ai.memory import compact, compact_wire, verification_wire
from prolog_ai.memory.source import encode

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bundle", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
a = parser.parse_args()
bundle = json.loads(a.bundle.read_text())
with (
    patch.object(compact, "call_llm", side_effect=AssertionError("No provider calls")),
    patch.object(socket.socket, "connect", side_effect=AssertionError("No network")),
):
    batches = compact.share_discovered_people(bundle["batches"], bundle["extracts"])
    rows = []
    for i, (b, e) in enumerate(zip(batches, bundle["extracts"], strict=True)):
        p = compact.verification_payload(b, e)
        w = verification_wire.request(p)
        targets = {t["r"]: (u, t) for u in w["source"] for t in u.get("targets", [])}
        assert len(targets) == len(p["observations"]) == w["target_count"]
        assert all(
            u["text"] == next(s["text"] for s in p["units"] if f"U{s['id']}" == u["u"])
            for u in w["source"]
        )
        for o in p["observations"]:
            u, t = targets[verification_wire.target_key(o)]
            assert u["u"] == f"U{o['e'][0]}"
            assert "c" not in t and "subject" not in t
            assert t["kind"] == o["kind"] and t["role"] == o["role"]
        size = len((verification_wire.INSTRUCTION + "\n" + encode(w)).encode())
        assert size <= compact.MAX_INPUT_BYTES
        rows.append(
            {
                "batch": i,
                "targets": len(targets),
                "new_input_bytes": size,
                "legacy_input_bytes": len(
                    (
                        compact_wire.VERIFY + "\n" + encode(compact_wire.verification_request(p))
                    ).encode()
                ),
            }
        )
    report = {
        "version": compact.VERSION,
        "verification_protocol": verification_wire.VERSION,
        "additional_api_calls": 0,
        "additional_usd": 0,
        "live_inference_tested": False,
        "historical_verdict_fallback_enabled": False,
        "cold_start_test": {
            "author_characters": 0,
            "previous_analysis": False,
            "chapters": 18,
            "provider_requests_simulated": 20,
            "stages": {"extract": 9, "verify": 9, "propose": 1, "assess": 1},
        },
        "request_budget": compact.MAX_REQUESTS,
        "source_target_count": sum(x["targets"] for x in rows),
        "all_target_keys_unique": True,
        "all_source_quotes_exact": True,
        "all_packets_within_byte_limit": True,
        "verification_input_byte_ratio": sum(x["new_input_bytes"] for x in rows)
        / sum(x["legacy_input_bytes"] for x in rows),
        "packets": rows,
        "limits": [
            "Cold-start call counts are integration-test measurements with simulated model responses.",
            "Real model accuracy, time and token cost for the new protocol have not been measured.",
            "Corpus packets use existing extracts only as protocol input; no previous verification decisions are reused.",
            "Changed prompts and schemas use new versioned cache keys.",
        ],
    }
    a.output.mkdir(exist_ok=True, parents=True)
    (a.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ["packets", "limits"]},
            ensure_ascii=False,
            indent=2,
        )
    )
