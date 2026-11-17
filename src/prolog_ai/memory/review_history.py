"""Reuse a paid independent review for unchanged source, never a majority vote.

A new uncertainty is not a refutation of a prior source-backed review. A new,
registered competing subject with direct or identifying proof blocks reuse.
"""

import re
from collections import defaultdict

from prolog_ai.memory.schema import AttributionCheck, Memory
from prolog_ai.memory.source import identity, validate_memory

VERSION = "source-review-history-v1"


def key(o):
    e = o.evidence
    return (e.scene_id, e.revision, e.start, e.end, e.quote, o.kind)


def covers(proof, target):
    return (
        proof.scene_id == target.scene_id
        and proof.revision == target.revision
        and proof.start <= target.start
        and proof.end >= target.end
    )


def identifies(proof, cid, characters):
    character = characters[cid]
    forms = [character.name, *character.aliases]
    if re.fullmatch(r"[가-힣]{3,5}", character.name):
        short = character.name[-2:]
        if {
            c.character_id
            for c in characters.values()
            if c.name.endswith(short) or short in c.aliases
        } == {cid}:
            forms.append(short)
    return any(
        re.search(
            r"(?<![\w가-힣])"
            + re.escape(f)
            + r"(?=$|[^\w가-힣]|은|는|이|가|의|을|를|에게|께|와|과|도|만)",
            proof.quote,
        )
        for f in forms
    )


def reuse_reviews(memory: Memory, previous: dict | None, *, analysis_id: str) -> dict:
    """Called before synthesis; input history is immutable and all decisions audited."""
    report = {"version": VERSION, "source_analysis_id": analysis_id, "reused": [], "blocked": []}
    if previous is None:
        return report
    prior = validate_memory(previous, require_complete=True)
    if (
        prior.project_id != memory.project_id
        or prior.mode != memory.mode
        or prior.scenes != memory.scenes
    ):
        report["ineligible"] = "source_snapshot_changed"
        return report
    if memory.patterns or memory.hypotheses:
        raise ValueError("Review history must be applied before pattern synthesis")
    chars = {c.character_id: c for c in memory.characters}
    prior_chars = {c.character_id: c for c in prior.characters}
    history = defaultdict(list)
    for o in prior.observations:
        if (
            o.attribution == "certain"
            and o.character_id in chars
            and chars[o.character_id] == prior_chars[o.character_id]
        ):
            history[key(o)].append(o)
    existing_ids = {o.observation_id for o in memory.observations}
    for o in memory.observations:
        if o.attribution != "uncertain":
            continue
        candidates = {
            c.character_id
            for c in o.attribution_checks
            if c.stage == "extract" and c.attribution == "certain" and c.character_id
        }
        previous_rows = history.get(key(o), [])
        old_candidates = {r.character_id for r in previous_rows}
        if len(candidates) != 1 or old_candidates != candidates:
            continue
        cid = next(iter(candidates))
        # Keep a genuine competing source-backed model decision unresolved.
        opposing = [
            c
            for c in o.attribution_checks
            if c.stage != "extract"
            and c.attribution == "certain"
            and c.character_id in chars
            and c.character_id != cid
            and any(
                covers(e, o.evidence) or identifies(e, c.character_id, chars) for e in c.evidence
            )
        ]
        if opposing:
            report["blocked"].append(
                {"observation_id": o.observation_id, "reason": "conflicting_current_proof"}
            )
            continue
        support = []
        for row in previous_rows:
            for c in row.attribution_checks:
                if c.stage == "extract" or c.attribution != "certain" or c.character_id != cid:
                    continue
                proof = [
                    e
                    for e in c.evidence
                    if e.scene_id == o.evidence.scene_id
                    and e.revision == o.evidence.revision
                    and e.start >= o.evidence.start - 1800
                    and e.end <= o.evidence.end + 1800
                    and (covers(e, o.evidence) or identifies(e, cid, chars))
                ]
                if proof:
                    support.append((row, c, proof))
        if not support:
            continue
        row, check, proof = min(
            support,
            key=lambda item: (not any(covers(e, o.evidence) for e in item[2]), len(item[2])),
        )
        original_id = o.observation_id
        new_id = identity(
            "obs", [o.evidence.model_dump(), cid, o.kind, o.presentation, o.behavior_role]
        )
        if new_id in existing_ids and new_id != original_id:
            report["blocked"].append({"observation_id": original_id, "reason": "duplicate_target"})
            continue
        reason = f"이전 분석 검증 재사용 ({analysis_id}). 동일 원고 버전·원문 위치·추출 주체 확인. {check.reason}"[
            :500
        ]
        reused = AttributionCheck(
            stage="verify",
            name=check.name,
            character_id=cid,
            attribution="certain",
            reason=reason,
            evidence=proof,
        )
        o.attribution_checks.append(reused)
        o.character_id, o.attribution, o.observation_id = cid, "certain", new_id
        existing_ids.discard(original_id)
        existing_ids.add(new_id)
        for verification in memory.speaker_verifications:
            if verification.observation_id == original_id:
                verification.observation_id = new_id
                verification.proposed_character_id = cid
                verification.proposed_attribution = "certain"
                verification.reason = reason
                verification.evidence = proof[0]
                verification.adjudicated = True
        report["reused"].append(
            {
                "observation_id": new_id,
                "previous_observation_id": original_id,
                "source_observation_id": row.observation_id,
                "character_id": cid,
                "evidence": [e.model_dump() for e in proof],
            }
        )
    validate_memory(memory.model_dump())
    return report
