"""SSM 모듈의 출력 스키마.

docs/specs/claude/api 명세/SSM.md 2.2 StructureMap, 2.3 StructureNode를 따른다.
이 스키마는 청크(챕터) 하나를 분석한 결과이며, module.py가 여러 청크의 결과를 병합해
최종 StructureMap을 만든다.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Act(BaseModel):
    act_name: str
    chapter_from: int
    chapter_to: int
    summary: str


class StructureNode(BaseModel):
    node_id: str
    type: Literal["event", "turning_point", "climax"]
    chapter: int
    title: str
    summary: str
    # TODO: 캐릭터 이름 -> character_id 매핑 방법이 이 패키지 범위에 없어,
    # 실제로 이 필드를 채울 수 있는지는 팀 확인 필요.
    character_ids: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    from_node_id: str
    to_node_id: str
    relation: str


class SSMChunkOutput(BaseModel):
    acts: list[Act]
    nodes: list[StructureNode]
    edges: list[Edge] = Field(default_factory=list)
