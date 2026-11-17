"""Combine sparse repairs without mixing original source or observation IDs."""

from prolog_ai.memory import compact


def pack(stage: str, payloads: list[dict]) -> tuple[dict, list[dict]]:
    if stage == "verify" and len(payloads) == 1:
        payload = payloads[0]
        if payload.get("alias_names"):
            raise ValueError("Repair must not replace identity bindings")
        if len(payload["observations"]) > 1500:
            raise ValueError("Too many missing records for one bounded repair")
        # Keep source/target keys and cache context when no cross-batch remap is needed.
        return {**payload, "allow_partial": True, "repair": True}, [
            {
                "units": {u["id"]: u["id"] for u in payload["units"]},
                "observations": {o["i"]: o["i"] for o in payload["observations"]},
            }
        ]

    def source_key(unit: dict) -> tuple:
        return unit["scene"], unit["revision"], unit["start"], unit["end"]

    unique = {}
    for payload in payloads:
        for unit in payload["units"]:
            key = source_key(unit)
            if key in unique and unique[key]["text"] != unit["text"]:
                raise ValueError("Conflicting repair source")
            unique[key] = unit
    ordered = sorted(unique.values(), key=lambda u: (u["order"], u["scene"], u["start"]))
    source_ids = {source_key(u): i for i, u in enumerate(ordered)}
    units = [{**u, "id": i} for i, u in enumerate(ordered)]
    mappings = []
    observations = []
    targets = []
    for payload in payloads:
        refs = {u["id"]: source_ids[source_key(u)] for u in payload["units"]}
        ids = {}
        for observation in payload.get("observations", []):
            ids[observation["i"]] = len(observations)
            observations.append(
                {**observation, "i": len(observations), "e": [refs[n] for n in observation["e"]]}
            )
        targets.extend(refs[n] for n in payload.get("target_ids", []))
        mappings.append({"units": refs, "observations": ids})
    known = {p["name"]: p for payload in payloads for p in payload.get("known_people", [])}
    combined = {
        "units": units,
        "known_people": sorted(known.values(), key=lambda p: p["name"]),
        "allow_partial": True,
        "repair": True,
    }
    if stage == "extract":
        combined["target_ids"] = sorted(set(targets))
    elif stage == "verify":
        from prolog_ai.memory.identity_context import checked_passages

        if any(p.get("alias_names") for p in payloads):
            raise ValueError("Repair must not replace identity bindings")
        combined.update(
            people=sorted({name for p in payloads for name in p["people"]}),
            alias_names=[],
            observations=observations,
            identity_context=list(
                checked_passages(
                    [passage for p in payloads for passage in p.get("identity_context", [])]
                ).values()
            ),
        )
    else:
        raise ValueError("Unsupported repair stage")
    if len(targets if stage == "extract" else observations) > 1500:
        raise ValueError("Too many missing records for one bounded repair")
    return combined, mappings


def unpack(stage: str, payloads: list[dict], result: dict, mappings: list[dict]) -> list[dict]:
    outputs = []
    for payload, mapping in zip(payloads, mappings, strict=True):
        units = {global_id: local_id for local_id, global_id in mapping["units"].items()}
        if stage == "extract":
            targets = set(payload["target_ids"])
            people = [
                {**p, "e": units[p["e"]]}
                for p in result["people"]
                if p["e"] in units and units[p["e"]] in targets
            ]
            rows = []
            for row in result["observations"]:
                if not all(n in units and units[n] in targets for n in row["e"]):
                    continue
                refs = [units[n] for n in row["e"]]
                local_units = {u["id"]: u for u in payload["units"]}
                context = [
                    n
                    for n in (refs[0] - 2, refs[0] - 1)
                    if n in local_units and local_units[n]["scene"] == local_units[refs[0]]["scene"]
                ]
                restored = {**row, "e": refs, "x": context}
                for field in ("identity", "identity_scope"):
                    if not row.get(field):
                        continue
                    proof = row[field]
                    if all(n in units for n in proof["evidence"]):
                        restored[field] = {
                            **proof,
                            "evidence": [units[n] for n in proof["evidence"]],
                        }
                    else:
                        restored.update({field: None, "identity_unresolved": True})
                rows.append(restored)
            invalid = [
                [units[row[0]], *row[1:]]
                for row in (result.get("validation_audit", {}).get("wire") or {}).get(
                    "invalid_code_rows", []
                )
                if row[0] in units and units[row[0]] in targets
            ]
            local = {
                "people": people,
                "observations": rows,
                "covered_units": [
                    units[n] for n in result["covered_units"] if n in units and units[n] in targets
                ],
                "skipped_units": [
                    units[n]
                    for n in result.get("skipped_units", [])
                    if n in units and units[n] in targets
                ],
                "validation_audit": {"invalid_code_rows": invalid},
            }
            outputs.append(compact.validate_extraction(payload, local))
        else:
            from prolog_ai.memory.verification_wire import target_key

            ids = {global_id: local_id for local_id, global_id in mapping["observations"].items()}
            expected = {o["i"]: o for o in payload["observations"]}
            # An invalid combined proof stays missing; never turn its fallback
            # quote into a confirmed decision when remapping to the local batch.
            audit = result.get("validation_audit", {})
            invalid = {r[0] for r in audit.get("invalid_proof_rows", [])}
            invalid.update(r["decision"]["i"] for r in audit.get("invalid_source_proofs", []))
            decisions = []
            for decision in result["decisions"]:
                if decision["i"] not in ids or decision["i"] in invalid:
                    continue
                local_id = ids[decision["i"]]
                if not all(n in units for n in decision["e"]):
                    # Another batch's source cannot establish this batch's owner.
                    continue
                decisions.append(
                    {**decision, "i": local_id, "e": [units[n] for n in decision["e"]]}
                )
                assert local_id in expected
            target_keys = {
                target_key(
                    {
                        "i": mapping["observations"][o["i"]],
                        "e": [mapping["units"][n] for n in o["e"]],
                    }
                ): target_key(o)
                for o in payload["observations"]
            }
            proposals = [
                {**p, "r": target_keys[p["r"]]}
                for p in audit.get("context_resolution_proposals", [])
                if p["r"] in target_keys
            ]
            outputs.append(
                compact.validate_verification(
                    {**payload, "allow_partial": True},
                    {
                        "decisions": decisions,
                        "bindings": [],
                        "validation_audit": {"context_resolution_proposals": proposals},
                    },
                )
            )
    return outputs
