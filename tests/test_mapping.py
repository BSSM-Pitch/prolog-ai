from prolog_ai.core.mapping import map_confirmed_character_to_scds

CONFIRMED_CHARACTER = {
    "character_id": "char_001",
    "name": "피터 파커",
    "personality_tags": ["책임감 강함", "자신감 부족"],
    "core_values": ["폭력 회피", "책임 중시"],
    "influence_relations": [{"target": "벤 삼촌", "type": "영향", "status": "고인"}],
    "emotion_keywords": ["불안"],
    "status": "confirmed",
}


def test_maps_tags_and_values_directly():
    result = map_confirmed_character_to_scds(CONFIRMED_CHARACTER)
    assert result["traits"] == ["책임감 강함", "자신감 부족"]
    assert result["values"] == ["폭력 회피", "책임 중시"]


def test_influence_relations_flattened_to_target_names():
    result = map_confirmed_character_to_scds(CONFIRMED_CHARACTER)
    assert result["influences"] == ["벤 삼촌"]


def test_emotion_keywords_dropped_but_counted():
    result = map_confirmed_character_to_scds(CONFIRMED_CHARACTER)
    assert "emotion_keywords" not in result
    assert result["dropped_emotion_keywords"] == 1


def test_missing_optional_fields_default_to_empty():
    result = map_confirmed_character_to_scds({"character_id": "char_002", "name": "무명"})
    assert result == {
        "traits": [],
        "values": [],
        "influences": [],
        "dropped_emotion_keywords": 0,
    }
