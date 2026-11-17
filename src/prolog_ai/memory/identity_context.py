"""Bounded, snapshot-local source retrieval and independently cited referents.

Retrieval proposes passages, never identities. No novel names or role vocabulary
are special-cased. A contextual designation stays local to the addressed record.
"""

import hashlib
import json
from collections import Counter, defaultdict

MAX_PASSAGES = 16
MAX_CONTEXT_CHARS = 10000
MAX_PASSAGE_CHARS = 1200


def passage_key(proof):
    value = [proof[k] for k in ("scene_id", "revision", "start", "end", "quote")]
    return "C" + hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()[:20]


def checked_passages(passages):
    from prolog_ai.memory.schema import Evidence

    result = {}
    for item in passages:
        proof = Evidence.model_validate(item["evidence"]).model_dump()
        if item["key"] != passage_key(proof):
            raise ValueError("Identity context source fingerprint changed")
        if item["key"] in result and result[item["key"]] != item:
            raise ValueError("Conflicting identity context source")
        result[item["key"]] = item
    return result


def retrieve(batches, extracts):
    """Select raw windows around discovered names and proposed identity citations.

    Literal name mentions and source coordinates from this extraction pass select
    windows; no model summaries or accepted/rejected relation labels are sent.
    """
    from prolog_ai.memory.compact import evidence

    candidates = {}
    for batch, extracted in zip(batches, extracts, strict=True):
        units = {u["id"]: u for u in batch["units"]}
        seeds = {p["e"]: 1 for p in extracted["people"]}
        # Registered characters need source retrieval too: extraction need not
        # rediscover a name already present in the supplied roster.
        for person in batch.get("known_people", []):
            for name in [person["name"], *person.get("aliases", [])]:
                if name:
                    first = next((u["id"] for u in batch["units"] if name in u["text"]), None)
                    if first is not None:
                        seeds.setdefault(first, 1)
        for row in extracted["observations"]:
            for field in ("identity", "identity_scope"):
                for ref in (row.get(field) or {}).get("evidence", []):
                    seeds[ref] = 3
        for ref, weight in seeds.items():
            if ref not in units:
                continue
            anchor = units[ref]
            if len(anchor["text"]) > MAX_PASSAGE_CHARS:
                continue
            refs = [ref]
            # Extend both ways, preserving original whitespace and scene bounds.
            for distance in range(1, 9):
                for n in (ref - distance, ref + distance):
                    if n not in units or units[n]["scene"] != anchor["scene"]:
                        continue
                    trial = sorted([*refs, n])
                    if trial != list(range(trial[0], trial[-1] + 1)):
                        continue
                    if units[trial[-1]]["end"] - units[trial[0]]["start"] <= MAX_PASSAGE_CHARS:
                        refs = trial
            proof = evidence(batch, sorted(refs))
            key = passage_key(proof)
            candidates[key] = {
                "key": key,
                "chapter": anchor["order"],
                "evidence": proof,
                "weight": max(weight, candidates.get(key, {}).get("weight", 0)),
            }
    result = []
    for batch, extracted in zip(batches, extracts, strict=True):
        local_names = {p["name"] for p in extracted["people"]}
        local_names.update(r["c"] for r in extracted["observations"] if r["c"])
        relevant = set(local_names)
        for names in batch.get("binding_candidates", {}).values():
            relevant.update(names)
        local_spans = defaultdict(list)
        for u in batch["units"]:
            local_spans[(u["scene"], u["revision"])].append((u["start"], u["end"]))
        ranked = []
        for passage in candidates.values():
            proof = passage["evidence"]
            spans = local_spans.get((proof["scene_id"], proof["revision"]), [])
            if (
                spans
                and min(a for a, _ in spans) <= proof["start"]
                and max(b for _, b in spans) >= proof["end"]
            ):
                continue
            hits = {name for name in relevant if name in proof["quote"]}
            if not hits:
                continue
            # Prefer evidence tying a local name to another discovered name,
            # but retain competing passages rather than selecting a verdict.
            score = len(hits) + passage["weight"] + 3 * len(hits - local_names)
            ranked.append((-score, passage["chapter"], proof["start"], passage["key"], passage))
        selected, chars = [], 0
        for *_, passage in sorted(ranked):
            proof = passage["evidence"]
            if any(
                p["evidence"]["scene_id"] == proof["scene_id"]
                and max(p["evidence"]["start"], proof["start"])
                < min(p["evidence"]["end"], proof["end"])
                for p in selected
            ):
                continue
            if len(selected) >= MAX_PASSAGES or chars + len(proof["quote"]) > MAX_CONTEXT_CHARS:
                continue
            selected.append({k: v for k, v in passage.items() if k != "weight"})
            chars += len(proof["quote"])
        result.append(
            {
                **batch,
                "identity_context": selected,
                "identity_context_audit": {
                    "candidate_windows": len(ranked),
                    "selected_windows": len(selected),
                    "selected_chars": chars,
                    "max_chars": MAX_CONTEXT_CHARS,
                    "source": "current_snapshot_raw_text",
                    "selection_is_not_identity_evidence": True,
                },
            }
        )
    return result


def prompt_passages(payload):
    return [
        {"key": p["key"], "chapter": p["chapter"], "text": p["evidence"]["quote"]}
        for p in checked_passages(payload.get("identity_context", [])).values()
    ]


def validate_resolutions(payload, proposals, decisions):
    """Validate local ownership and independently cited distant identity proof."""
    from prolog_ai.memory.compact import evidence
    from prolog_ai.memory.verification_wire import target_key

    passages = checked_passages(payload.get("identity_context", []))
    targets = {target_key(o): o for o in payload["observations"]}
    votes = {d["i"]: d for d in decisions}
    counts = Counter(p["r"] for p in proposals)
    known = set(payload["people"])

    def present(name, text):
        if name in text:
            return True
        aliases = [
            a
            for p in payload.get("known_people", [])
            if p["name"] == name
            for a in p.get("aliases", [])
        ]
        return any(a in text for a in aliases)

    accepted, rejected = {}, []
    for proposal in proposals:
        target = targets.get(proposal["r"])
        try:
            if not target or counts[proposal["r"]] != 1:
                raise ValueError("Unknown or duplicate contextual target")
            d = votes.get(target["i"])
            ref, owner, canonical = (proposal[k] for k in ("reference", "relative_to", "canonical"))
            if not ref or canonical not in known or ref == canonical or owner in {canonical, ref}:
                raise ValueError("Invalid contextual participants")
            if owner is not None and owner not in known:
                raise ValueError("Unknown relation owner")
            if not d or d["a"] != "certain" or d["c"] not in {ref, canonical}:
                raise ValueError("Contextual identity disagrees with independent subject")
            if not set(target["e"]) <= set(d["e"]):
                raise ValueError("Local proof misses target")
            local = evidence(payload, d["e"])
            if not present(ref, local["quote"]) or owner and not present(owner, local["quote"]):
                raise ValueError("Local designation or owner is not cited")
            refs = proposal["context"]
            if not refs or len(refs) != len(set(refs)) or any(k not in passages for k in refs):
                raise ValueError("Missing or unknown identity context citation")
            proofs = [passages[k]["evidence"] for k in refs]
            text = "\n".join(p["quote"] for p in proofs)
            if (
                not present(canonical, text)
                or not present(ref, text)
                or owner
                and not present(owner, text)
            ):
                raise ValueError("Distant identity participants are not cited")
            accepted[target["i"]] = {
                "reference": ref,
                "relative_to": owner,
                "canonical": canonical,
                "evidence": [local, *proofs],
            }
        except ValueError as exc:
            rejected.append({"proposal": proposal, "reason": str(exc)})
    return accepted, rejected


def resolved_records(batches, extracts, reviews, known_ids, alias_maps):
    """Require agreement with the extractor and honor later explicit vetoes."""
    from prolog_ai.memory.compact import verification_payload

    result, conflicting_records = {}, set()
    for bi, (batch, extracted, review) in enumerate(zip(batches, extracts, reviews, strict=True)):
        audit = review.get("validation_audit", {})
        proposals = audit.get("context_resolution_proposals", [])
        later_proposals = audit.get("adjudication", {}).get("context_resolution_proposals", [])
        if not proposals and not later_proposals:
            continue
        payload = verification_payload(batch, extracted)
        links, _ = validate_resolutions(payload, proposals, review["decisions"])
        later, _ = validate_resolutions(payload, later_proposals, review.get("adjudications", []))
        conflicts = {
            i
            for i in links.keys() & later.keys()
            if any(links[i][k] != later[i][k] for k in ("canonical", "relative_to", "reference"))
        }
        links.update(later)
        for i in conflicts:
            links.pop(i)
            conflicting_records.add((bi, i))
        third = {d["i"]: d for d in review.get("adjudications", [])}
        for i, link in links.items():
            row = extracted["observations"][i]
            forms = {link["reference"], link["canonical"]}
            candidate = alias_maps[bi].get(row["c"], row["c"])
            if row["a"] != "certain" or row["c"] not in forms and candidate not in forms:
                continue
            if len(known_ids.get(link["canonical"].casefold(), set())) != 1:
                continue
            if i in third and (
                third[i]["a"] != "certain"
                or alias_maps[bi].get(third[i]["c"], third[i]["c"]) not in forms
            ):
                continue
            result[(bi, i)] = link
    return result, conflicting_records
