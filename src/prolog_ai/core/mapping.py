"""NLCD/ASS 확정 캐릭터 필드를 SCDS Character 필드로 변환하는 레이어.

ASS ConfirmedCharacter (docs/specs/claude/api 명세/ASS.md 2.4)
와 SCDS Character (docs/specs/claude/api 명세/SCDS.md 2.1)는 같은 캐릭터를 가리키지만
필드명이 다르다. 이 모듈은 저장 시점의 필드명을 통일하지 않고, SCDS가 참조할 때만
변환하는 매핑 레이어(2단계 선택지 3번)를 제공한다.

대응 관계 (ConfirmedCharacter -> SCDS Character)
    personality_tags (string[])                                  -> traits (string[])
    core_values      (string[])                                  -> values (string[])
    influence_relations (object[] {target, type, status})        -> influences (string[])

대응 필드가 없는 항목
    emotion_keywords: SCDS Character에는 대응 필드가 없다(0단계 조사 결과).
    이 함수는 emotion_keywords를 SCDS 쪽 반환값에 포함하지 않고 버리며,
    몇 개를 버렸는지 확인할 수 있도록 반환값에 `dropped_emotion_keywords`로 남긴다.
    influence_relations의 `type`, `status`도 SCDS의 influences(string[])에는
    담을 곳이 없어 대상 이름(target/value)만 남기고 버려진다.
"""

from typing import Any


def map_confirmed_character_to_scds(character: dict[str, Any]) -> dict[str, Any]:
    """ASS ConfirmedCharacter 딕셔너리를 SCDS Character 필드로 변환한다.

    입력에 없는 필드는 빈 리스트로 취급한다(명세상 두 리소스 모두 N=선택 필드).
    """
    influence_relations = character.get("influence_relations") or []
    influences = [item["target"] for item in influence_relations]

    return {
        "traits": list(character.get("personality_tags") or []),
        "values": list(character.get("core_values") or []),
        "influences": influences,
        "dropped_emotion_keywords": len(character.get("emotion_keywords") or []),
    }
