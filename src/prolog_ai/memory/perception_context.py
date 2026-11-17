"""Connect omitted sensory details to a corroborated viewpoint, as an inference.

Never rewrite the extractor/verifier's null verdict or count this as their
agreement. Only the current snapshot and its existing, source-backed decisions
are used. These links are not eligible to bootstrap another viewpoint link.
"""

import re

from prolog_ai.memory.schema import Evidence, PerceptionContext

SENSES = (
    re.compile(r"소리|음성|울림|기척"),
    re.compile(r"빛|불빛|색깔|형체|흔적"),
    re.compile(r"냄새|향기"),
)
ABSENCE = re.compile(r"없(?:었|다|는)|들리지\s*않|보이지\s*않|느껴지지\s*않")
PARAGRAPH = re.compile(r"\n[ \t]*\n")


def paragraph_ids(units):
    result, current, previous_scene = {}, -1, None
    for unit in units:
        if unit["scene"] != previous_scene or "\n" in unit.get("gap_before", ""):
            current += 1
        result[unit["id"]] = current
        previous_scene = unit["scene"]
    return result


def corroborated_awareness(row):
    if row.kind != "inner_thought" or row.behavior_role != "awareness":
        return False
    if row.attribution != "certain" or row.character_id is None:
        return False
    return all(
        any(
            c.stage == stage
            and c.attribution == "certain"
            and c.character_id == row.character_id
            and any(
                e.scene_id == row.evidence.scene_id
                and e.start <= row.evidence.start
                and e.end >= row.evidence.end
                for e in c.evidence
            )
            for c in row.attribution_checks
        )
        for stage in ("extract", "verify")
    )


def infer_perception_contexts(memory):
    """Return auditable context links, not new confirmed subject assignments."""
    result = {}
    for scene in memory.scenes:
        rows = sorted(
            (o for o in memory.observations if o.evidence.scene_id == scene.scene_id),
            key=lambda o: (o.evidence.start, o.evidence.end, o.observation_id),
        )
        thoughts = [o for o in rows if o.kind == "inner_thought"]
        breaks = list(PARAGRAPH.finditer(scene.text))
        for row in rows:
            if (
                row.kind != "narration"
                or row.presentation != "narrator_claim"
                or row.character_id is not None
                or row.subject_name is not None
                or row.attribution != "uncertain"
                or row.behavior_role != "other"
                or not ABSENCE.search(row.evidence.quote)
                or any(c.name is not None for c in row.attribution_checks)
                or not {"extract", "verify"} <= {c.stage for c in row.attribution_checks}
            ):
                continue
            senses = [sense for sense in SENSES if sense.search(row.evidence.quote)]
            if not senses or re.search(r'["“”「」]', row.evidence.quote):
                continue
            start = max((b.end() for b in breaks if b.end() <= row.evidence.start), default=0)
            end = min(
                (b.start() for b in breaks if b.start() >= row.evidence.end),
                default=len(scene.text),
            )
            if end - start > 500:
                continue
            # The following perception must be in the SAME paragraph. The prior
            # viewpoint can be separated by quoted speech, but stays within 800 chars.
            following = [o for o in thoughts if row.evidence.end <= o.evidence.start < end]
            previous = [
                o
                for o in thoughts
                if row.evidence.start - 800 <= o.evidence.end <= row.evidence.start
            ]
            if not following or not previous:
                continue
            left, right = previous[-1], following[0]
            if not (corroborated_awareness(left) and corroborated_awareness(right)):
                continue
            cid = left.character_id
            if right.character_id != cid or not any(s.search(right.evidence.quote) for s in senses):
                continue
            if not any(s.search(left.evidence.quote) for s in senses):
                continue
            # A competing/unknown viewpoint invalidates the bridge; physical
            # actors and quoted speakers are not automatically the perceiver.
            intervening = [
                o
                for o in thoughts
                if left.evidence.start <= o.evidence.start <= right.evidence.start
            ]
            if any(not corroborated_awareness(o) or o.character_id != cid for o in intervening):
                continue
            quote = scene.text[start:end]
            if re.search(r'["“”「」]', quote):
                continue
            result[row.observation_id] = PerceptionContext(
                character_id=cid,
                anchor_observation_ids=[left.observation_id, right.observation_id],
                evidence=[
                    left.evidence,
                    Evidence(
                        scene_id=scene.scene_id,
                        revision=scene.revision,
                        start=start,
                        end=end,
                        quote=quote,
                    ),
                ],
                reason="앞뒤에서 추출·독립 검증이 일치한 동일 인물의 인지와 같은 감각 문맥을 연결. 대상 문장 자체의 주체 판정은 미확정으로 보존.",
            )
    return result
