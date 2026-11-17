"""Re-run one whole original batch; keep other batches and roster frozen.

Use the production prompts, schemas, validation, repair and merge functions.
Only the model selector is overridden. A file queue carries the exact SDK HTTP
body to an authenticated network relay; credentials never enter the queue.
"""

import argparse
import hashlib
import json
import os
import time
import traceback
import uuid
from copy import deepcopy
from pathlib import Path

import httpx
import openai

from prolog_ai.core import llm
from prolog_ai.core.request_policy import RequestPolicy, request_policy
from prolog_ai.memory import compact as c
from prolog_ai.memory import repairs
from prolog_ai.memory.source import validate_memory

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--reuse-extraction",
    type=Path,
    help="Freeze this replacement.json extraction to compare verifier transports",
)
args = parser.parse_args()
assert args.model in ["gpt-6-luna", "gpt-6-sol", "gpt-6.1-terra", "gpt-6.1-sol"]
root = args.output / args.model
root.mkdir(parents=True, exist_ok=False)
queue = root / "queue"
queue.mkdir()
report = {
    "model": args.model,
    "harness_version": c.VERSION,
    "batch_index": 0,
    "status": "running",
    "calls": [],
    "steps": [],
    "started_at": time.time(),
    "scope": "Fresh batch 0; other eight batches and final character roster frozen.",
    "reasoning_effort": "low",
    "max_output_tokens": 32768,
}


def write(name, data):
    dest = root / name
    temp = dest.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(dest)


class Relay(httpx.BaseTransport):
    def handle_request(self, request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["model"] == args.model
        ident = uuid.uuid4().hex
        pending = queue / (ident + ".request.json")
        temp = queue / (ident + ".tmp")
        temp.write_text(json.dumps({"body": body}))
        temp.replace(pending)
        response_path = queue / (ident + ".response.json")
        start = time.monotonic()
        while not response_path.exists():
            if time.monotonic() - start > 340:
                raise httpx.ReadTimeout("Relay wait timed out")
            time.sleep(0.2)
        result = json.loads(response_path.read_text())
        report["calls"][-1].update(
            seconds=time.monotonic() - start,
            http_status=result["status"],
            returned_model=result["body"].get("model"),
            usage=result["body"].get("usage"),
            request_sha256=hashlib.sha256(request.content).hexdigest(),
        )
        write("report.json", report)
        return httpx.Response(
            result["status"],
            json=result["body"],
            headers=result.get("headers", {}),
            request=request,
        )


original_client = openai.OpenAI


def client(**kwargs):
    return original_client(**kwargs, http_client=httpx.Client(transport=Relay()))


openai.OpenAI = client
os.environ.update(
    PROLOG_AI_PROVIDER="openai",
    PROLOG_AI_MODEL=args.model,
    OPENAI_API_KEY="relay-placeholder-not-a-secret",
)
os.environ.pop("USE_FAKE_LLM", None)
llm.OPENAI_QUERY_MODEL = args.model


def reserve():
    if len(report["calls"]) >= 14:
        raise RuntimeError("Bounded experiment request cap reached")
    report["calls"].append({"stage": active_stage, "started_at": time.time()})
    write("report.json", report)


def execute(stage, payload, label):
    global active_stage
    active_stage = label
    write(label + "-input.json", payload)
    with request_policy(RequestPolicy(before_attempt=reserve)):
        result = c.run_step(stage, payload)
    result = c.check(stage, payload, result)
    write(label + "-output.json", result)
    report["steps"].append(label)
    write("report.json", report)
    return result


def repair(stage, payload, value):
    missing_for = c.missing_units if stage == "extract" else c.missing_verifications
    merge = c.merge_extractions if stage == "extract" else c.merge_verifications
    for turn in range(2):
        missing = missing_for(payload, value)
        if not missing:
            return value
        local = [
            c.repair_payload(payload, missing, value)
            if stage == "extract"
            else c.verification_repair_payload(payload, missing)
        ]
        combined, mappings = repairs.pack(stage, local)
        fixed = execute(stage, combined, f"{stage}-repair-{turn + 1}")
        unpacked = repairs.unpack(stage, local, fixed, mappings)[0]
        value = merge(payload, value, unpacked, require_complete=False)
    if missing_for(payload, value):
        if stage == "extract":
            raise ValueError("Coverage incomplete after two bounded combined repairs")
        value = c.defer_verifications(payload, value)
    return value


try:
    bundle = json.loads(args.input.read_text())
    source = bundle["source"]
    batches = [
        {**c.batch_payload(b, source["characters"]), "allow_partial": True, "review_actions": True}
        for b in c.plan(source["scenes"])
    ]
    batch = batches[0]
    assert batch["units"] == bundle["batches"][0]["units"]
    assert batch["target_ids"] == bundle["batches"][0]["target_ids"]
    if args.reuse_extraction:
        extracted = json.loads(args.reuse_extraction.read_text())["extracted"]
        report["extraction_reused"] = str(args.reuse_extraction)
    else:
        extracted = execute("extract", batch, "extract")
        extracted = repair("extract", batch, extracted)
    c.check("extract", {**batch, "allow_partial": False}, extracted)
    extracts = deepcopy(bundle["extracts"])
    extracts[0] = extracted
    shared = c.share_discovered_people(batches, extracts)
    batch = shared[0]
    payload = {**c.verification_payload(batch, extracted), "allow_partial": True}
    review = execute("verify", payload, "verify")
    review = repair("verify", payload, review)
    c.check("verify", {**payload, "allow_partial": False}, review)
    disputes = set(c.ownership_disputes(extracted, review))
    if disputes:
        checked = execute(
            "verify",
            {**c.focused_verification(payload, disputes), "allow_partial": False},
            "attribution",
        )
        review = c.attach_adjudication(payload, review, checked)
        c.check("verify", payload, review)
    final_batches = deepcopy(bundle["batches"])
    final_batches[0] = batch
    reviews = deepcopy(bundle["reviews"])
    reviews[0] = review
    write("replacement.json", {"batch": batch, "extracted": extracted, "review": review})
    memory = c.build_memory(
        source["project_id"],
        source["scenes"],
        bundle["characters"],
        final_batches,
        extracts,
        reviews,
        model=args.model,
    )
    validate_memory(memory.model_dump())
    write("memory.json", memory.model_dump())
    names = {x.character_id: x.name for x in memory.characters}
    targets = [
        "그 순서는 어머니가 가르쳐 준 것이었다.",
        "누구를 부르든 꼭 짧게 휘파람부터 불고 나서 이름을 부르던 버릇까지.",
        "어머니는 글씨를 못 썼다.",
        "여자는 아기를 달래며 문을 나섰다.",
    ]
    report["targets"] = [
        {
            "quote": q,
            "records": [
                {"character": names.get(o.character_id), **o.model_dump()}
                for o in memory.observations
                if q in o.evidence.quote
            ],
        }
        for q in targets
    ]
    report.update(
        status="completed",
        observations=len(memory.observations),
        fresh_observations=len(extracted["observations"]),
        disputes=len(disputes),
    )
except Exception as exc:  # noqa: BLE001 - persist a terminal experiment outcome
    report.update(
        status="failed",
        error_type=type(exc).__name__,
        error=str(exc)[:2000],
        traceback=traceback.format_exc(),
    )
finally:
    report["elapsed_seconds"] = time.time() - report["started_at"]
    write("report.json", report)
    print(
        json.dumps(
            {
                "model": args.model,
                "status": report["status"],
                "calls": len(report["calls"]),
                "error": report.get("error"),
            },
            ensure_ascii=False,
        )
    )
