"""인물 기억 + 원문 구간 검색. 발췌 범위와 원본 오프셋을 명시한다."""

import re
from collections import Counter

from prolog_ai.memory.retrieval import LexicalIndex, content_query
from prolog_ai.memory.source import chunks, digest


def select_source_windows(memory, context, query, queries=None, max_chars=32000):
    as_of = context["coverage"].get("as_of_order")
    if context["coverage"].get("explicit_character_filter") and not context["coverage"].get(
        "character_ids"
    ):
        return []
    scenes = [s for s in memory["scenes"] if as_of is None or s["order"] <= as_of]
    query = content_query(query)
    queries = list(dict.fromkeys([query, *(queries or [])]))
    wanted = {o["character_id"] for o in context["observations"] if o["character_id"]}
    # 이름 자체가 모든 장면에서 높은 점수를 얻지 않도록 내용어 점수에서 제거한다.
    names = sorted(
        {n for c in memory["characters"] for n in [c["name"], *c.get("aliases", [])]},
        key=len,
        reverse=True,
    )

    def without_names(text):
        for name in names:
            # '민'을 '고민'에서, '소리'라는 이름을 '목소리'에서 지우지 않는다.
            text = re.sub(
                r"(?<!\w)"
                + re.escape(name)
                + r"(?=(?:은|는|이|가|의|와|과|에게|을|를|도|만)?(?:\W|$))",
                " ",
                text,
            )
        return text

    queries = [without_names(q) for q in queries]
    observations = memory["observations"]
    candidates = []
    for scene in scenes:
        obs = [o for o in observations if o["evidence"]["scene_id"] == scene["scene_id"]]
        for start, fragment in chunks(scene["text"], 1000, overlap=160):
            end = start + len(fragment)
            linked = [
                o for o in obs if o["evidence"]["start"] < end and o["evidence"]["end"] > start
            ]
            text = fragment + " " + " ".join(o["summary"] + " " + o["context"] for o in linked)
            candidates.append(
                {
                    "scene": scene,
                    "start": start,
                    "end": end,
                    "search_text": without_names(text),
                    "character_match": not wanted
                    or any(o["character_id"] in wanted for o in linked),
                }
            )
    index = LexicalIndex([c["search_text"] for c in candidates])
    for c in candidates:
        c["scores"] = [index.score(q, c["search_text"]) for q in queries]
        c["score"] = (max(c["scores"], default=0) + 0.25 * sum(c["scores"])) * (
            1 if c["character_match"] else 0.8
        )
    if not candidates or (
        not context["observations"] and not any(c["score"] > 0 for c in candidates)
    ):
        return []
    if sum(len(s["text"]) for s in scenes) <= max_chars:
        return scenes
    selected, size, counts = [], 0, Counter()

    def add(c):
        nonlocal size
        if c in selected:
            return
        cost = c["end"] - c["start"]
        if size + cost <= max_chars:
            selected.append(c)
            size += cost
            counts[c["scene"]["scene_id"]] += 1

    # 세부 질문마다 최고점과 서로 다른 시점의 관련 근거를 먼저 확보한다.
    for qi in range(len(queries)):
        ranked = sorted(
            candidates, key=lambda c: (-c["scores"][qi], c["scene"]["order"], c["start"])
        )
        if not ranked or ranked[0]["scores"][qi] <= 0:
            continue
        add(ranked[0])
        relevant = [c for c in ranked if c["scores"][qi] >= ranked[0]["scores"][qi] * 0.65]
        if relevant:
            add(min(relevant, key=lambda c: (c["scene"]["order"], c["start"])))
            add(max(relevant, key=lambda c: (c["scene"]["order"], c["start"])))
    remaining = [c for c in candidates if c not in selected and c["score"] > 0]
    while remaining:
        c = max(remaining, key=lambda c: c["score"] / (1 + 0.20 * counts[c["scene"]["scene_id"]]))
        remaining.remove(c)
        add(c)
    # 겹치는 원문만 합친다. 떨어진 구간을 연속 인용처럼 보이게 하지 않는다.
    merged = []
    for c in sorted(selected, key=lambda c: (c["scene"]["order"], c["start"])):
        if merged and merged[-1]["scene"] == c["scene"] and merged[-1]["end"] >= c["start"]:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
        else:
            merged.append({"scene": c["scene"], "start": c["start"], "end": c["end"]})
    output = []
    for order, c in enumerate(merged):
        s, start, end = c["scene"], c["start"], c["end"]
        output.append(
            {
                **s,
                "scene_id": "excerpt_" + digest([s["scene_id"], s["revision"], start, end])[:24],
                "source_scene_id": s["scene_id"],
                "source_start": start,
                "source_order": s["order"],
                "order": order,
                "text": s["text"][start:end],
            }
        )
    return output
