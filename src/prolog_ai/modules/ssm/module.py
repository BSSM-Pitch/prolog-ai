"""SSM 모듈의 공개 함수.

3단계에서 정한 경계대로, 청킹(chunking.py)은 run_module 밖에서 먼저 실행하고,
챕터마다 run_module을 반복 호출한 뒤 acts/nodes/edges를 이 함수가 직접 병합한다.

청크마다 LLM이 node_id를 따로 매기므로(모두 node_1부터 시작) 병합할 때 전체에서
겹치지 않게 다시 매기고, 같은 청크의 edges도 새 id로 바꾼다. 없는 노드를 가리키거나
자기 자신을 가리키는 edge, 이미 있는 edge와 같은 edge는 버리고 개수를 meta.removed_edge_count에 남긴다.

노드의 character_ids는 백엔드 structure_node_characters.character_id(캐릭터 uuid 외래키)에
저장되므로, 넘겨받은 확정 캐릭터(ASS ConfirmedCharacter) 목록의 character_id만 남긴다.
목록을 주지 않으면 비운다(WARN.md A12 ①, D5).
TODO: 노드의 chapter 번호와 acts를 전체 원고 기준으로 맞추는 방법은 WARN.md T6·A10 결정 필요.
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode, make_error, make_success
from prolog_ai.core.guard import expect_list_of, expect_text, expect_type, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.ssm.chunking import split_into_chapters
from prolog_ai.modules.ssm.prompt import build_prompt
from prolog_ai.modules.ssm.schema import SSMChunkOutput

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
    for chunk_index, chunk in enumerate(chunks):
        result = run_module(
            module="ssm",
            input_data={"chapter_text": chunk, "characters": roster},
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

        acts.extend(result["data"]["acts"])

        new_ids: dict[str, str] = {}
        for node in result["data"]["nodes"]:
            new_id = f"node_{len(nodes) + 1}"
            new_ids.setdefault(node["node_id"], new_id)
            character_ids = [cid for cid in dict.fromkeys(node["character_ids"]) if cid in known_ids]
            nodes.append({**node, "node_id": new_id, "character_ids": character_ids})

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
