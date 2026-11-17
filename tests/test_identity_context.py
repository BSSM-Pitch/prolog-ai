"""Cross-batch identity proof remains source-bound and record-specific."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from prolog_ai.memory import compact, compact_wire, repairs
from prolog_ai.memory import identity_context as ctx
from prolog_ai.memory import verification_wire as wire
from prolog_ai.memory.source import validate_memory


def fixture(role="선생님"):
    scenes = [
        {
            "scene_id": "early",
            "revision": "r1",
            "order": 1,
            "text": f"민서의 {role}은 책을 펼쳤다. 지훈의 {role}은 문을 닫았다.",
        },
        {
            "scene_id": "later",
            "revision": "r1",
            "order": 2,
            "text": f"민서의 {role}은 정은이다. 지훈의 {role}은 수연이다.",
        },
    ]
    batches, extracts = [], []
    for scene, people, subjects in zip(
        scenes,
        [[("민서", 0), (role, 0), ("지훈", 1)], [("정은", 0), ("수연", 1)]],
        [[1, 1], [0, 1]],
        strict=True,
    ):
        batch = {
            **compact.batch_payload(compact.plan([scene])[0], []),
            "allow_partial": True,
            "review_actions": True,
        }
        raw = {
            "people": [{"name": n, "alias": -1, "u": u} for n, u in people],
            "rows": [[u, subject, 1, 0, 0, 1] for u, subject in enumerate(subjects)],
            "skip": [],
        }
        batches.append(batch)
        extracts.append(
            compact.validate_extraction(batch, compact_wire.extraction_response(batch, raw))
        )
    batches = compact.share_discovered_people(batches, extracts)
    payload = compact.verification_payload(batches[0], extracts[0])
    key = payload["identity_context"][0]["key"]
    raw = {
        "rows": [{"r": f"T{i}.{i}", "c": role, "e": f"U{i}", "n": 1} for i in range(2)],
        "links": [],
        "resolutions": [
            {
                "r": f"T{i}.{i}",
                "reference": role,
                "relative_to": owner,
                "canonical": canonical,
                "context": [key],
            }
            for i, (owner, canonical) in enumerate([("민서", "정은"), ("지훈", "수연")])
        ],
    }
    roster = [{"character_id": n, "name": n, "aliases": []} for n in payload["people"]]
    return scenes, roster, batches, extracts, payload, raw


def build(data, review=None):
    scenes, roster, batches, extracts, payload, raw = data
    reviews = [
        review or wire.response(payload, raw),
        {
            "decisions": [
                {"i": i, "c": row["c"], "a": "certain", "e": row["e"], "reason": "독립 검증"}
                for i, row in enumerate(extracts[1]["observations"])
            ],
            "bindings": [],
        },
    ]
    with patch.object(compact, "call_llm", side_effect=AssertionError("No added model call")):
        result = compact.build_memory("p", scenes, roster, batches, extracts, reviews, model="test")
    result.complete = True
    validate_memory(result.model_dump(), require_complete=True)
    return result


@pytest.mark.parametrize("role", ["선생님", "대장", "어머니", "담당자"])
def test_context_resolves_per_record_without_global_role_alias(role):
    data = fixture(role)
    before = deepcopy(data)
    result = build(data)
    early = [o for o in result.observations if o.evidence.scene_id == "early"]
    assert [o.character_id for o in early] == ["정은", "수연"]
    assert [o.subject_name for o in early] == [role, role]
    assert all(o.attribution == "certain" for o in early)
    assert [o.identity_links[0].relative_to for o in early] == ["민서", "지훈"]
    assert all(
        {e.scene_id for e in o.identity_links[0].evidence} == {"early", "later"} for o in early
    )
    assert all(not c.aliases for c in result.characters)
    assert data == before


@pytest.mark.parametrize(
    "damage",
    [
        "missing_context",
        "unknown_context",
        "duplicate_context",
        "duplicate_target",
        "wrong_target",
        "wrong_owner",
        "unknown_canonical",
        "no_local_owner",
        "different_subject",
        "uncertain_review",
        "uncertain_extract",
        "adjudication_veto",
    ],
)
def test_invalid_or_disagreeing_evidence_does_not_promote(damage):
    data = fixture()
    _, _, _, extracts, payload, raw = data
    proposal = raw["resolutions"][0]
    if damage == "missing_context":
        raw["resolutions"] = []
    elif damage == "unknown_context":
        proposal["context"] = ["Cmissing"]
    elif damage == "duplicate_context":
        proposal["context"] *= 2
    elif damage == "duplicate_target":
        raw["resolutions"].append(deepcopy(proposal))
    elif damage == "wrong_target":
        proposal["r"] = "malformed"
    elif damage == "wrong_owner":
        proposal["relative_to"] = "지훈"
    elif damage == "unknown_canonical":
        proposal["canonical"] = "미등록"
    elif damage == "no_local_owner":
        proposal["reference"] = "미등록호칭"
    elif damage == "different_subject":
        raw["rows"][0]["c"] = "민서"
    elif damage == "uncertain_review":
        raw["rows"][0]["c"] = None
    elif damage == "uncertain_extract":
        extracts[0]["observations"][0]["a"] = "uncertain"
    review = wire.response(payload, raw)
    if damage == "adjudication_veto":
        review["adjudications"] = [{**review["decisions"][0], "c": "지훈"}]
    assert build(data, review).observations[0].character_id != "정은"


def test_retrieval_is_bounded_raw_current_source_and_not_previous_verdicts():
    scenes, _, batches, extracts, payload, _ = fixture()
    for batch in batches:
        passages = batch["identity_context"]
        assert len(passages) <= ctx.MAX_PASSAGES
        assert sum(len(p["evidence"]["quote"]) for p in passages) <= ctx.MAX_CONTEXT_CHARS
        for passage in passages:
            proof = passage["evidence"]
            scene = next(s for s in scenes if s["scene_id"] == proof["scene_id"])
            assert proof["revision"] == scene["revision"]
            assert proof["quote"] == scene["text"][proof["start"] : proof["end"]]
            assert len(proof["quote"]) <= ctx.MAX_PASSAGE_CHARS
    assert all(
        set(p) == {"key", "chapter", "text"} for p in wire.request(payload)["identity_context"]
    )
    before = deepcopy(extracts)
    compact.share_discovered_people(batches, extracts)
    assert extracts == before


@pytest.mark.parametrize("field", ["quote", "revision", "start"])
def test_changed_source_fingerprint_rejected(field):
    *_, payload, _ = fixture()
    proof = payload["identity_context"][0]["evidence"]
    proof[field] = proof[field] + (1 if field == "start" else "changed")
    with pytest.raises(ValueError):
        wire.request(payload)


def test_valid_new_context_cannot_reuse_stale_cache_prefix():
    *_, payload, _ = fixture()
    focused = deepcopy(compact.focused_verification(payload, {0}))
    passage = focused["identity_context"][0]
    passage["evidence"]["revision"] = "next"
    passage["key"] = ctx.passage_key(passage["evidence"])
    with pytest.raises(ValueError, match="Verification cache context changed"):
        wire.cache_parts(focused)


@pytest.mark.parametrize("pooled", [False, True])
def test_sparse_repairs_preserve_context_target_mapping(pooled):
    *_, payload, raw = fixture()
    payloads = [
        compact.verification_repair_payload(payload, [i]) for i in ([1, 0] if pooled else [1])
    ]
    packed, mappings = repairs.pack("verify", payloads)
    result_raw = {"rows": [], "links": [], "resolutions": []}
    for local, mapping in zip(payloads, mappings, strict=True):
        o = local["observations"][0]
        key = wire.target_key(
            {"i": mapping["observations"][o["i"]], "e": [mapping["units"][o["e"][0]]]}
        )
        result_raw["rows"].append(
            {**raw["rows"][o["i"]], "r": key, "e": f"U{mapping['units'][o['e'][0]]}"}
        )
        result_raw["resolutions"].append({**raw["resolutions"][o["i"]], "r": key})
    result = wire.response(packed, result_raw)
    for local, restored in zip(
        payloads, repairs.unpack("verify", payloads, result, mappings), strict=True
    ):
        proposals = restored["validation_audit"]["context_resolution_proposals"]
        links, rejected = ctx.validate_resolutions(local, proposals, restored["decisions"])
        assert not rejected
        assert set(links) == {local["observations"][0]["i"]}


def test_direct_nickname_does_not_require_relation_owner():
    data = fixture("등대")
    raw = data[-1]
    raw["resolutions"][0]["relative_to"] = None
    # Source is a direct naming statement for this test, not a family relation.
    passage = data[-2]["identity_context"][0]
    proof = passage["evidence"]
    quote = "등대라고 불리는 사람의 이름은 정은이다."
    proof.update(quote=quote, start=0, end=len(quote))
    passage["key"] = ctx.passage_key(proof)
    raw["resolutions"] = [{**raw["resolutions"][0], "context": [passage["key"]]}]
    review = wire.response(data[-2], raw)
    links, rejected = ctx.validate_resolutions(data[-2], raw["resolutions"], review["decisions"])
    assert not rejected and links[0]["relative_to"] is None


def test_registered_names_retrieve_source_without_rediscovery():
    _, _, batches, extracts, _, _ = fixture()
    for extracted in extracts:
        extracted["people"] = []
    result = ctx.retrieve(batches, extracts)
    assert result[0]["identity_context"]
    assert "정은" in result[0]["identity_context"][0]["evidence"]["quote"]


def test_retrieval_obeys_budget_when_many_passages_match(monkeypatch):
    _, _, batches, extracts, _, _ = fixture()
    monkeypatch.setattr(ctx, "MAX_PASSAGES", 1)
    monkeypatch.setattr(ctx, "MAX_CONTEXT_CHARS", 10)
    assert all(not b["identity_context"] for b in ctx.retrieve(batches, extracts))


def test_adjudication_keeps_new_identity_proof_and_does_not_modify_previous_vote():
    data = fixture()
    payload, raw = data[-2:]
    review = wire.response(payload, {**raw, "resolutions": []})
    before = deepcopy(review)
    checked = wire.response(payload, raw)
    merged = compact.attach_adjudication(payload, review, checked)
    assert review == before
    result = build(data, merged)
    assert [o.character_id for o in result.observations[:2]] == ["정은", "수연"]
    assert all(
        any(e.scene_id == "later" for e in o.identity_links[0].evidence)
        for o in result.observations[:2]
    )


def test_conflicting_context_reviews_defer_identity():
    data = fixture()
    payload, raw = data[-2:]
    review = wire.response(payload, raw)
    changed = deepcopy(raw)
    # Both names are in the retrieved passage; contradictory model readings
    # must not be resolved by choosing the last response.
    changed["resolutions"][0]["canonical"] = "수연"
    merged = compact.attach_adjudication(payload, review, wire.response(payload, changed))
    record = build(data, merged).observations[0]
    assert record.character_id is None and record.attribution == "uncertain"


def test_repair_replaces_stale_resolution_without_parsing_untrusted_target_id():
    *_, payload, raw = fixture()
    review = wire.response(
        payload,
        {"rows": [], "links": [], "resolutions": [{**raw["resolutions"][0], "r": "malformed"}]},
    )
    fixed = wire.response(payload, raw)
    merged = compact.merge_verifications(payload, review, fixed)
    links, _ = ctx.validate_resolutions(
        payload, merged["validation_audit"]["context_resolution_proposals"], merged["decisions"]
    )
    assert set(links) == {0, 1}
