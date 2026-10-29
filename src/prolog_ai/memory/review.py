"""기억과 새 사건을 비교한다. 세계관 rule_id와 인물 패턴 ID를 섞지 않는다."""

from prolog_ai.core.errors import make_success
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import InputValidationError, run_module
from prolog_ai.memory import prompt
from prolog_ai.memory.retrieval import prepare_context
from prolog_ai.memory.schema import CharacterReviewOutput
from prolog_ai.memory.source import encode


def prepare_review(event, memory, as_of_order):
    expect_type(event, dict, "event")
    content = expect_text(event.get("content"), "event.content")
    ids = expect_list_of(event.get("character_ids"), str, "event.character_ids")
    # 긴 현재 장면은 호출자가 장면 단위로 나눈다. 과거 기억은 검색 예산으로 제한한다.
    if len(encode(content)) > 8000:
        raise InputValidationError("event.content가 8000자 문맥 한도를 넘습니다.")
    context = prepare_context(memory, content, ids, as_of_order, 16000)
    return {"event": {"content": content, "character_ids": ids}, "memory": context}


def review_prepared(data):
    context = data["memory"]
    content, ids = data["event"]["content"], data["event"]["character_ids"]
    if not context["observations"]:
        return make_success(
            {"findings": [], "coverage": context["coverage"], "snapshot_id": context["snapshot_id"]}
        )
    result = run_module(
        module="memory",
        input_data=data,
        validate=lambda x: x,
        build_prompt=lambda x: prompt.build(prompt.REVIEW, x),
        output_schema=CharacterReviewOutput,
        timeout=90.0,
    )
    if "error" in result:
        return result
    by_id = {o["observation_id"]: o for o in context["observations"]}
    kept = []
    for f in result["data"]["findings"]:
        references = f["observation_ids"]
        if (
            f["character_id"] not in ids
            or not f["event_quote"].strip()
            or f["event_quote"] not in content
            or not references
            or any(
                i not in by_id
                or by_id[i]["character_id"] != f["character_id"]
                or by_id[i]["attribution"] != "certain"
                for i in references
            )
        ):
            continue
        kept.append(
            {
                **f,
                "observation_ids": list(dict.fromkeys(references)),
                "evidence": [by_id[i]["evidence"] for i in dict.fromkeys(references)],
            }
        )
    return make_success(
        {"findings": kept, "coverage": context["coverage"], "snapshot_id": context["snapshot_id"]},
        {"removed_finding_count": len(result["data"]["findings"]) - len(kept)},
    )


@public_api("memory")
def run_character_review(event: dict, memory: dict, *, as_of_order: int | None = None) -> dict:
    return review_prepared(prepare_review(event, memory, as_of_order))
