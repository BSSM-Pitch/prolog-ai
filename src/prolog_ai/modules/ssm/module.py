"""SSM 모듈의 공개 함수.

3단계에서 정한 경계대로, 청킹(chunking.py)은 run_module 밖에서 먼저 실행하고,
챕터마다 run_module을 반복 호출한 뒤 acts/nodes/edges를 이 함수가 직접 병합한다.

청크마다 LLM이 node_id를 따로 매기므로(모두 node_1부터 시작) 병합할 때 전체에서
겹치지 않게 다시 매기고, 같은 청크의 edges도 새 id로 바꾼다. 없는 노드를 가리키는
edge는 버리고 개수를 meta.removed_edge_count에 남긴다.
TODO: 노드의 chapter 번호와 acts를 전체 원고 기준으로 맞추는 방법은 WARN.md T6·A10 결정 필요.
"""

from typing import Any

from prolog_ai.core.errors import ErrorCode, make_error, make_success
from prolog_ai.core.guard import expect_type, public_api
from prolog_ai.core.runner import run_module
from prolog_ai.modules.ssm.chunking import split_into_chapters
from prolog_ai.modules.ssm.prompt import build_prompt
from prolog_ai.modules.ssm.schema import SSMChunkOutput

# TODO: 실제 "분량 부족" 기준(문자 수 등)이 명세에 없어, 완전히 비어 있는 경우만 최소로 막는다.
MIN_MANUSCRIPT_LENGTH = 1


@public_api("ssm")
def run_ssm(manuscript_text: str) -> dict[str, Any]:
    stripped = expect_type(manuscript_text, str, "manuscript_text").strip()
    if len(stripped) < MIN_MANUSCRIPT_LENGTH:
        return make_error(
            ErrorCode.MANUSCRIPT_TOO_SHORT,
            "구조 분석을 수행하기에 원고 분량이 부족합니다.",
            {"length": len(stripped)},
        )

    acts: list[dict] = []
    nodes: list[dict] = []
    edges: list[dict] = []
    removed_edge_count = 0

    for chunk in split_into_chapters(manuscript_text):
        result = run_module(
            module="ssm",
            input_data=chunk,
            validate=lambda text: text,
            build_prompt=build_prompt,
            output_schema=SSMChunkOutput,
        )
        if "error" in result:
            # TODO(WARN.md A11): 청크 하나가 실패했을 때 전체를 실패로 볼지는 팀 결정 필요.
            # 우선 첫 실패를 그대로 반환한다.
            return result

        acts.extend(result["data"]["acts"])

        new_ids: dict[str, str] = {}
        for node in result["data"]["nodes"]:
            new_id = f"node_{len(nodes) + 1}"
            new_ids.setdefault(node["node_id"], new_id)
            nodes.append({**node, "node_id": new_id})

        for edge in result["data"]["edges"]:
            if edge["from_node_id"] in new_ids and edge["to_node_id"] in new_ids:
                edges.append(
                    {
                        **edge,
                        "from_node_id": new_ids[edge["from_node_id"]],
                        "to_node_id": new_ids[edge["to_node_id"]],
                    }
                )
            else:
                removed_edge_count += 1

    return make_success(
        {"acts": acts, "nodes": nodes, "edges": edges},
        {"removed_edge_count": removed_edge_count},
    )
