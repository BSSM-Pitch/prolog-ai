"""Reuse an already reviewed identity within a source-backed relation scope.

Missing scopes may reuse model-declared, independently cited adjacent context.
No aliases are installed and no new relationship is guessed from proximity alone.
Both the target scope and the canonical identity retain their exact source proof.
"""

import re
from collections import defaultdict
from itertools import pairwise

ROLE_FORMS = {
    "어머니": ("어머니", "엄마", "어미", "모친"),
    "아버지": ("아버지", "아빠", "아비", "부친"),
}


def relation_key(name):
    return next((role for role, forms in ROLE_FORMS.items() if name in forms), name)


def recover_reviewed_scope(batch, extracted, row, decision, known_ids, aliases):
    """Recover a missing scope from context the verifier actually read and cited.

    A repair can retain the subject but lose its original identity_scope. Reuse
    an existing relation declaration at most two contiguous units away, in either
    direction, only when its owner proof and the target are cited together. Never
    propagate inferred scopes recursively or use an entire chapter as evidence.
    """
    role = relation_key(row["c"])
    if (
        role not in ROLE_FORMS
        or row["k"] != "narration"
        or row["p"] not in {"depicted", "narrator_claim"}
        or row["a"] != "certain"
        or not decision
        or decision["a"] != "certain"
        or relation_key(decision["c"]) != role
        or not set(row["e"]) <= set(decision["e"])
    ):
        return None
    units = {u["id"]: u for u in batch["units"]}
    if len(row["e"]) != 1:
        return None
    target = row["e"][0]
    forms = dict(known_ids)
    for alias, canonical in aliases.items():
        forms[alias.casefold()] = known_ids.get(canonical.casefold(), set())

    def mentions(name, text):
        return (
            re.search(
                r"(?<!\w)"
                + re.escape(name)
                + r"(?=(?:은|는|이|가|의|와|과|에게|을|를|도|만)?(?:\W|$))",
                text.casefold(),
            )
            is not None
        )

    candidates = []
    for other in extracted["observations"]:
        scope = other.get("identity_scope") or other.get("identity")
        if not scope or relation_key(scope["reference"]) != role:
            continue
        owner = aliases.get(scope["relative_to"], scope["relative_to"])
        owner_ids = known_ids.get(owner.casefold(), set())
        if len(owner_ids) != 1:
            continue
        for witness in set(scope["evidence"]) & set(decision["e"]):
            if not 1 <= abs(witness - target) <= 2:
                continue
            path = [units.get(n) for n in range(min(target, witness), max(target, witness) + 1)]
            if any(
                u is None
                or u["scene"] != units[target]["scene"]
                or u["revision"] != units[target]["revision"]
                for u in path
            ):
                continue
            if any(
                "\n" in right["gap_before"]
                or right["start"] != left["end"] + len(right["gap_before"])
                for left, right in pairwise(path)
            ):
                continue
            text = " ".join(u["text"] for u in path)
            # A quoted speaker or a representation of someone is not the person.
            # Those need an explicit per-record decision, not inherited scope.
            if re.search(r'["“”‘’「」『』]|목소리|흉내|모습을\s*빌|둔갑|변장', text):
                continue
            owner_forms = [name for name, ids in forms.items() if ids == owner_ids]
            witness_text = units[witness]["text"]
            if not any(mentions(n, witness_text) for n in owner_forms) or not any(
                mentions(n, witness_text) for n in ROLE_FORMS[role]
            ):
                continue
            if any(
                relation_key(name) != role and ids != owner_ids and mentions(name, text)
                for name, ids in forms.items()
            ):
                continue
            candidates.append(
                (
                    next(iter(owner_ids)),
                    {
                        "reference": row["c"],
                        "relative_to": owner,
                        "evidence": sorted({target, witness}),
                    },
                )
            )
    if len({owner_id for owner_id, _ in candidates}) != 1:
        return None
    return min((scope for _, scope in candidates), key=lambda s: tuple(s["evidence"]))


def resolve_name_links(batches, extracts, reviews, roster):
    """Pool grounded name decisions within ONE source snapshot, never across jobs.

    Suffix matching proposes candidates only. A non-self model binding and source
    evidence are required. Self-links abstain; competing real identities veto reuse.
    Contextual relationships are deliberately excluded from this name index.
    """
    from prolog_ai.memory.compact import evidence

    proposed, votes, proofs = defaultdict(set), defaultdict(set), defaultdict(list)
    roster_ids = defaultdict(set)
    for person in roster:
        for name in [person.name, *person.aliases]:
            roster_ids[name].add(person.character_id)
    for batch, extracted, review in zip(batches, extracts, reviews, strict=True):
        for alias, candidates in batch.get("binding_candidates", {}).items():
            proposed[alias].update(candidates)
        for person in extracted["people"]:
            if person.get("alias_of"):
                proposed[person["name"]].add(person["alias_of"])
        for binding in review.get("bindings", []):
            alias, canonical = binding["name"], binding["canonical"]
            if not canonical or canonical == alias:
                continue
            votes[alias].add(canonical)
            proof = evidence(batch, [binding["e"]])
            if alias in proof["quote"]:
                proofs[(alias, canonical)].append(proof)
    result = {}
    for alias, candidates in proposed.items():
        if relation_key(alias) in ROLE_FORMS or len(candidates) != 1:
            continue
        canonical = next(iter(candidates))
        target = roster_ids[canonical]
        competitors = {
            c.character_id for c in roster if c.name.endswith(alias) or alias in c.aliases
        }
        if (
            votes[alias] != {canonical}
            or len(target) != 1
            or competitors - target
            or roster_ids[alias] - target
            or not proofs[(alias, canonical)]
        ):
            continue
        mentions = [
            evidence(b, [u["id"]]) for b in batches for u in b["units"] if canonical in u["text"]
        ]
        result[alias] = {
            "reference": alias,
            "canonical": canonical,
            "relative_to": None,
            "evidence": [
                min(proofs[(alias, canonical)], key=lambda e: len(e["quote"])),
                *([min(mentions, key=lambda e: len(e["quote"]))] if mentions else []),
            ],
        }
    return result


def resolve_scoped_records(batches, extracts, reviews, known_ids, alias_maps=None):
    from prolog_ai.memory.compact import evidence

    anchors = defaultdict(lambda: defaultdict(list))
    alias_maps = alias_maps or [{} for _ in batches]
    for bi, (batch, extracted, review) in enumerate(zip(batches, extracts, reviews, strict=True)):
        decisions = {d["i"]: d for d in review["decisions"]}
        for i, row in enumerate(extracted["observations"]):
            proof = row.get("identity")
            if not proof or row["c"] == proof["reference"]:
                continue
            canonical = alias_maps[bi].get(row["c"], row["c"])
            owner = alias_maps[bi].get(proof["relative_to"], proof["relative_to"])
            if (
                len(known_ids.get(canonical.casefold(), set())) != 1
                or len(known_ids.get(owner.casefold(), set())) != 1
            ):
                continue
            owner_id = next(iter(known_ids[owner.casefold()]))
            candidates = anchors[(relation_key(proof["reference"]), owner_id)][canonical]
            decision = decisions.get(i)
            if (
                row["a"] != "certain"
                or not decision
                or decision["a"] != "certain"
                or (
                    relation_key(decision["c"]) != relation_key(proof["reference"])
                    and alias_maps[bi].get(decision["c"], decision["c"]) != canonical
                )
                or not set(row["e"]) & set(decision["e"])
            ):
                continue
            candidates.append([evidence(batch, [n]) for n in proof["evidence"]])
    resolved = {}
    for bi, (batch, extracted, review) in enumerate(zip(batches, extracts, reviews, strict=True)):
        decisions = {d["i"]: d for d in review["decisions"]}
        third = {d["i"]: d for d in review.get("adjudications", [])}
        for i, row in enumerate(extracted["observations"]):
            scope = row.get("identity_scope")
            if not scope and not row.get("identity"):
                scope = recover_reviewed_scope(
                    batch, extracted, row, decisions.get(i), known_ids, alias_maps[bi]
                )
            if (
                not scope
                or row.get("identity")
                or row["a"] != "certain"
                or row["c"] != scope["reference"]
            ):
                continue
            owner = alias_maps[bi].get(scope["relative_to"], scope["relative_to"])
            owner_ids = known_ids.get(owner.casefold(), set())
            if len(owner_ids) != 1:
                continue
            candidates = anchors.get((relation_key(scope["reference"]), next(iter(owner_ids))), {})
            if len(candidates) != 1:
                continue
            canonical, proofs = next(iter(candidates.items()))
            if not proofs:
                continue
            decision = decisions.get(i)
            if (
                not decision
                or decision["a"] != "certain"
                or (
                    relation_key(decision["c"]) != relation_key(scope["reference"])
                    and alias_maps[bi].get(decision["c"], decision["c"]) != canonical
                )
            ):
                continue
            if i in third and (
                third[i]["a"] != "certain"
                or (
                    relation_key(third[i]["c"]) != relation_key(scope["reference"])
                    and alias_maps[bi].get(third[i]["c"], third[i]["c"]) != canonical
                )
            ):
                continue
            local = [evidence(batch, [n]) for n in scope["evidence"]]
            proof = min(proofs, key=len)
            refs = {
                (e["scene_id"], e["revision"], e["start"], e["end"]): e for e in [*local, *proof]
            }
            # Two independent proofs, each up to eight units. The old limit
            # incorrectly applied a single-model citation limit to their union.
            if len(refs) > 16:
                continue
            resolved[(bi, i)] = {
                "reference": scope["reference"],
                "relative_to": scope["relative_to"],
                "canonical": canonical,
                "evidence": list(refs.values()),
            }
    return resolved
