"""SSM 모듈의 공개 함수.

3단계에서 정한 경계대로, 청킹(chunking.py)은 run_module 밖에서 먼저 실행하고,
챕터마다 run_module을 반복 호출한 뒤 acts/nodes/edges를 이 함수가 직접 병합한다.
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

    for chunk in split_into_chapters(manuscript_text):
        result = run_module(
            module="ssm",
            input_data=chunk,
            validate=lambda text: text,
            build_prompt=build_prompt,
            output_schema=SSMChunkOutput,
        )
        if "error" in result:
            # TODO: 청크 하나가 실패했을 때 전체를 실패로 볼지, 나머지는 계속 진행할지는
            # 팀 확인 필요. 우선 첫 실패를 그대로 반환한다.
            return result

        acts.extend(result["data"]["acts"])
        nodes.extend(result["data"]["nodes"])
        edges.extend(result["data"]["edges"])

    return make_success({"acts": acts, "nodes": nodes, "edges": edges})
