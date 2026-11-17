"""Repair systematic response-index drift using exact source coordinates only.

This is materialization, not an additional review or a vote for the extractor.
Never use character names, expected labels or manuscript-specific text to align.
"""

from collections import defaultdict
from copy import deepcopy

MIN_RUN = 4
VERSION = "source-alignment-v1"


def realign(payload: dict, review: dict) -> dict:
    from prolog_ai.memory.compact import evidence, record_evidence

    if (
        review.get("validation_audit", {}).get("target_keys_validated")
        or review.get("validation_audit", {}).get("source_alignment", {}).get("version") == VERSION
    ):
        return deepcopy(review)

    def key(e):
        return e["scene_id"], e["revision"], e["start"], e["end"]

    targets = {o["i"]: o for o in payload["observations"]}
    spans = {i: record_evidence(payload, o) for i, o in targets.items()}
    by_span = defaultdict(list)
    for i, span in spans.items():
        by_span[key(span)].append(i)
    groups = defaultdict(list)
    for d in review["decisions"]:
        proof = evidence(payload, d["e"])
        matches = by_span[key(proof)]
        original = spans[d["i"]]
        # Nearby context is legitimate evidence. Only exact, unambiguous spans
        # disjoint from the addressed record can be candidates for relocation.
        if len(matches) != 1 or matches[0] == d["i"]:
            continue
        if proof["scene_id"] != original["scene_id"] or not (
            proof["end"] <= original["start"] or original["end"] <= proof["start"]
        ):
            continue
        target = matches[0]
        groups[(proof["scene_id"], target - d["i"])].append((d["i"], target))

    moves = {}
    runs = []
    for candidates in groups.values():
        run = []
        for pair in sorted(candidates) + [None]:
            if run and (pair is None or pair[0] != run[-1][0] + 1):
                if len(run) >= MIN_RUN:
                    moves.update(run)
                    runs.append([list(p) for p in run])
                run = []
            if pair is not None:
                run.append(pair)
    if not moves:
        return deepcopy(review)

    incoming = defaultdict(list)
    for original in review["decisions"]:
        target = moves.get(original["i"], original["i"])
        decision = deepcopy(original)
        if target != original["i"]:
            decision.update(
                i=target,
                reason=(
                    f"원문 위치로 검증 연결 복구 ({original['i']} → {target}). "
                    + original["reason"]
                )[:160],
            )
        incoming[target].append(decision)
    aligned, withheld, superseded = [], [], []
    for i, target in targets.items():
        decisions = incoming[i]
        if i in moves.values():
            retained = []
            for d in decisions:
                proof = evidence(payload, d["e"])
                span = spans[i]
                if proof["end"] <= span["start"] or span["end"] <= proof["start"]:
                    # A proven drift run supplies a direct exact-span decision.
                    # A non-overlapping old slot is not a competing direct review.
                    superseded.append(d)
                else:
                    retained.append(d)
            decisions = retained
        unique = {(d["c"], d["a"], tuple(d["e"])) for d in decisions}
        if len(unique) == 1:
            aligned.append(decisions[0])
        else:
            # Neither a missing response nor a collision confirms the extractor.
            aligned.append(
                {
                    "i": i,
                    "c": None,
                    "a": "uncertain",
                    "e": target["e"],
                    "reason": "검증 번호 복구 후 판정이 없거나 충돌하여 확정 보류",
                }
            )
            withheld.append({"i": i, "decisions": decisions})
    result = deepcopy(review)
    result["decisions"] = sorted(aligned, key=lambda d: d["i"])
    result["validation_audit"] = {
        **review.get("validation_audit", {}),
        "source_alignment": {
            "version": VERSION,
            "runs": runs,
            "withheld": withheld,
            "superseded_context_decisions": superseded,
            "original_decisions": deepcopy(review["decisions"]),
        },
    }
    return result


def adds_candidate_context(payload: dict, name: str, previous: dict, final: dict) -> bool:
    """Restoring extraction needs new cited context identifying its candidate.

    A targeted review that repeats the same conflicting quote is not stronger
    evidence. Name forms locate a model-cited subject; they never assign one.
    """
    import re

    from prolog_ai.memory.compact import evidence

    # The caller requires the target itself. A better proof may replace an
    # irrelevant following sentence with identifying preceding context.
    if not set(previous["e"]) & set(final["e"]) or not set(final["e"]) - set(previous["e"]):
        return False
    known = payload.get("known_people", [])
    forms = [name, *next((p.get("aliases", []) for p in known if p["name"] == name), [])]
    if re.fullmatch(r"[가-힣]{3,5}", name):
        short = name[-2:]
        competing = {
            p["name"] for p in known if p["name"].endswith(short) or short in p.get("aliases", [])
        }
        if competing == {name}:
            forms.append(short)
    text = " ".join(evidence(payload, [n])["quote"] for n in final["e"] if n not in previous["e"])
    return any(
        re.search(
            r"(?<![\w가-힣])"
            + re.escape(form)
            + r"(?=$|[^\w가-힣]|은|는|이|가|의|을|를|에게|께|와|과|도|만)",
            text,
        )
        for form in forms
    )
