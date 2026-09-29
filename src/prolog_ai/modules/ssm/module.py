"""SSM 모듈의 공개 함수.

3단계에서 정한 경계대로, 청킹(chunking.py)은 run_module 밖에서 먼저 실행하고,
챕터마다 run_module을 반복 호출한 뒤 acts/nodes/edges를 이 함수가 직접 병합한다.

청크마다 LLM이 node_id를 따로 매기므로(모두 node_1부터 시작) 병합할 때 전체에서
겹치지 않게 다시 매기고, 같은 청크의 edges도 새 id로 바꾼다. 없는 노드를 가리키거나
자기 자신을 가리키는 edge, 이미 있는 edge와 같은 edge는 버리고 개수를 meta.removed_edge_count에 남긴다.

노드의 character_ids는 백엔드 structure_node_characters.character_id(캐릭터 uuid 외래키)에
저장되므로, 넘겨받은 확정 캐릭터(ASS ConfirmedCharacter) 목록의 character_id만 남긴다.
목록을 주지 않으면 비운다(WARN.md A12 ①, D5).
노드 chapter와 acts의 chapter_from/to는 LLM이 쓴 값 대신 청크의 챕터 번호(chunking.chapter_numbers)로 채운다.
LLM은 챕터 하나만 보므로 번호를 모른다(WARN.md T6). 챕터마다 새로 생기는 같은 이름의 막이 이어지면
하나로 합쳐 chapter_to를 늘린다(3장 원고에서 "발단"이 세 번 나오던 문제).
TODO: 챕터를 넘는 연결(T23)과 챕터 목록 입력(A10)은 결정 필요.
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode, make_error, make_success
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.ssm.chunking import chapter_numbers, split_into_chapters
from prolog_ai.modules.ssm.prompt import build_prompt
from prolog_ai.modules.ssm.schema import TITLE_MAX_LENGTH, SSMChunkOutput

# TODO: 실제 "분량 부족" 기준(문자 수 등)이 명세에 없어, 완전히 비어 있는 경우만 최소로 막는다.
MIN_MANUSCRIPT_LENGTH = 1
# 챕터 하나를 분석하는 데 기본 제한(30초)을 넘기기 쉽다. 명세상 SSM은 비동기(폴링)라
# 시간 상한이 없으므로 AIQ·SCDS와 같이 둔다(WARN.md T35).
SSM_TIMEOUT_SECONDS = 90.0


def _validate_characters(characters: Any) -> list[dict[str, str]]:
    """ASS ConfirmedCharacter 목록에서 character_id, name만 꺼낸다."""
    expect_list_of(characters, dict, "characters")
    roster = []
    for index, character in enumerate(characters):
        field = f"characters[{index}]"
        character_id = expect_text(character.get("character_id"), f"{field}.character_id")
        name = expect_text(character.get("name"), f"{field}.name")
        roster.append({"character_id": character_id, "name": name})
    return roster


# SSM 2.2 acts 예시 순서. 이야기 단계는 뒤로 돌아가지 않는다.
ACT_ORDER = ("발단", "전개", "위기", "절정", "결말")


def _goes_back(previous: str, current: str) -> bool:
    return (
        previous in ACT_ORDER
        and current in ACT_ORDER
        and ACT_ORDER.index(current) < ACT_ORDER.index(previous)
    )


def _merge_acts(acts: list[dict], chunk_acts: list[dict], chapter: int) -> None:
    """청크의 막을 이 챕터 번호로 고치고, 바로 앞 막과 이름이 같으면 이어 붙인다.

    LLM은 챕터 하나만 보고 단계를 정해, 앞 챕터보다 이른 단계를 고르기도 한다(실제 호출: 발단 → 위기 → 전개).
    단계는 되돌아가지 않으므로 그런 막은 바로 앞 막에 이어 붙인다.
    """
    for act in chunk_acts:
        previous = acts[-1] if acts else None
        name = act["act_name"].strip()
        if previous and (previous["act_name"].strip() == name or _goes_back(previous["act_name"].strip(), name)):
            previous["chapter_to"] = max(previous["chapter_to"], chapter)
            summary = act["summary"].strip()
            if summary and summary not in previous["summary"]:
                joined = previous["summary"].rstrip()
                if joined and joined[-1] not in ".!?。":
                    joined += "."
                previous["summary"] = f"{joined} {summary}".strip()
            continue
        acts.append({**act, "chapter_from": chapter, "chapter_to": chapter})


@public_api("ssm")
def run_ssm(
    manuscript_text: str, characters: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    stripped = expect_type(manuscript_text, str, "manuscript_text").strip()
    roster = [] if characters is None else _validate_characters(characters)
    if len(stripped) < MIN_MANUSCRIPT_LENGTH:
        return make_error(
            ErrorCode.MANUSCRIPT_TOO_SHORT,
            "구조 분석을 수행하기에 원고 분량이 부족합니다.",
            {"length": len(stripped)},
        )

    known_ids = {c["character_id"] for c in roster}
    acts: list[dict] = []
    nodes: list[dict] = []
    edges: list[dict] = []
    edge_keys: set[tuple[str, str, str]] = set()
    removed_edge_count = 0

    chunks = split_into_chapters(manuscript_text)
    numbers = chapter_numbers(chunks)
    for chunk_index, (chunk, chapter) in enumerate(zip(chunks, numbers, strict=True)):
        result = run_module(
            module="ssm",
            input_data={"chapter_text": chunk, "chapter": chapter, "characters": roster},
            validate=lambda data: data,
            build_prompt=build_prompt,
            output_schema=SSMChunkOutput,
            timeout=SSM_TIMEOUT_SECONDS,
        )
        if "error" in result:
            # WARN.md A11: 청크 하나가 실패하면 전체 실패로 반환한다. 몇 번째 청크인지 남긴다.
            result["error"]["details"].update(
                {"chunk_index": chunk_index, "chunk_count": len(chunks)}
            )
            return result

        _merge_acts(acts, result["data"]["acts"], chapter)

        new_ids: dict[str, str] = {}
        for node in result["data"]["nodes"]:
            new_id = f"node_{len(nodes) + 1}"
            new_ids.setdefault(node["node_id"], new_id)
            character_ids = [cid for cid in dict.fromkeys(node["character_ids"]) if cid in known_ids]
            nodes.append(
                {
                    **node,
                    "node_id": new_id,
                    "chapter": chapter,
                    "title": node["title"].strip()[:TITLE_MAX_LENGTH],
                    "character_ids": character_ids,
                }
            )

        for edge in result["data"]["edges"]:
            from_id = new_ids.get(edge["from_node_id"])
            to_id = new_ids.get(edge["to_node_id"])
            key = (from_id, to_id, edge["relation"])
            if from_id is None or to_id is None or from_id == to_id or key in edge_keys:
                removed_edge_count += 1
                continue
            edge_keys.add(key)
            edges.append({**edge, "from_node_id": from_id, "to_node_id": to_id})

    return make_success(
        {"acts": acts, "nodes": nodes, "edges": edges},
        {"removed_edge_count": removed_edge_count},
    )
