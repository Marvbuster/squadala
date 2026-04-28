"""Tests for dungeon spec schema validation."""

import pytest
from pydantic import ValidationError

from livegen.schema import (
    ActorType,
    ChestContent,
    Connection,
    DoorType,
    DungeonSpec,
    Logic,
    Metadata,
    Room,
)


def _minimal_spec(**overrides) -> dict:
    """Return a minimal valid DungeonSpec as a dict."""
    base = {
        "metadata": {"name": "Test Dungeon", "theme": "ice", "difficulty": "medium"},
        "rooms": [
            {
                "id": "entrance",
                "template": "small_chamber_2exit",
                "actors": [],
                "chests": [],
            },
            {
                "id": "boss_arena",
                "template": "boss_arena",
                "actors": [{"type": "iron_knuckle", "count": 1}],
                "chests": [],
            },
        ],
        "connections": [
            {"from": "entrance", "to": "boss_arena", "type": "open_door"},
        ],
        "logic": {},
    }
    base.update(overrides)
    return base


class TestMinimalSpec:
    def test_valid_minimal(self):
        spec = DungeonSpec.model_validate(_minimal_spec())
        assert spec.metadata.name == "Test Dungeon"
        assert len(spec.rooms) == 2
        assert len(spec.connections) == 1

    def test_rooms_minimum(self):
        data = _minimal_spec()
        data["rooms"] = [data["rooms"][0]]
        with pytest.raises(ValidationError, match="too_short"):
            DungeonSpec.model_validate(data)

    def test_connections_minimum(self):
        data = _minimal_spec()
        data["connections"] = []
        with pytest.raises(ValidationError, match="too_short"):
            DungeonSpec.model_validate(data)


class TestGraphIntegrity:
    def test_connection_unknown_room(self):
        data = _minimal_spec()
        data["connections"] = [{"from": "entrance", "to": "nonexistent"}]
        with pytest.raises(ValidationError, match="unknown room 'nonexistent'"):
            DungeonSpec.model_validate(data)

    def test_duplicate_room_ids(self):
        data = _minimal_spec()
        data["rooms"].append(data["rooms"][0])
        with pytest.raises(ValidationError, match="Duplicate room IDs"):
            DungeonSpec.model_validate(data)

    def test_duplicate_chest_ids_in_room(self):
        room = {
            "id": "test_room",
            "template": "small_chamber_2exit",
            "chests": [
                {"id": "c1", "contents": "small_key"},
                {"id": "c1", "contents": "map"},
            ],
        }
        with pytest.raises(ValidationError, match="Duplicate chest IDs"):
            Room.model_validate(room)


class TestKeyConsistency:
    def test_more_key_doors_than_keys_fails(self):
        data = _minimal_spec()
        data["connections"] = [
            {"from": "entrance", "to": "boss_arena", "type": "small_key_door"},
        ]
        # No key chests — should fail
        with pytest.raises(ValidationError, match="Not enough small keys"):
            DungeonSpec.model_validate(data)

    def test_matching_keys_and_doors(self):
        data = _minimal_spec()
        data["rooms"][0]["chests"] = [{"id": "c1", "contents": "small_key"}]
        data["connections"] = [
            {"from": "entrance", "to": "boss_arena", "type": "small_key_door"},
        ]
        spec = DungeonSpec.model_validate(data)
        assert spec.logic.small_keys_required == 0  # logic field, not auto-counted


class TestLogicReferences:
    def test_valid_boss_key_chest_ref(self):
        data = _minimal_spec()
        data["rooms"][0]["chests"] = [{"id": "bk", "contents": "boss_key"}]
        data["logic"] = {"boss_key_chest": "entrance.bk"}
        spec = DungeonSpec.model_validate(data)
        assert spec.logic.boss_key_chest == "entrance.bk"

    def test_invalid_chest_ref_bad_format(self):
        data = _minimal_spec()
        data["logic"] = {"boss_key_chest": "just_a_string"}
        with pytest.raises(ValidationError, match="room_id.chest_id"):
            DungeonSpec.model_validate(data)

    def test_invalid_chest_ref_missing_chest(self):
        data = _minimal_spec()
        data["logic"] = {"boss_key_chest": "entrance.nonexistent"}
        with pytest.raises(ValidationError, match="unknown chest"):
            DungeonSpec.model_validate(data)

    def test_boss_room_must_exist(self):
        data = _minimal_spec()
        data["logic"] = {"boss": {"type": "iron_knuckle", "room": "nowhere"}}
        with pytest.raises(ValidationError, match="does not exist"):
            DungeonSpec.model_validate(data)


class TestFullSpec:
    """Test with the example from the spec document."""

    def test_spec_example(self):
        spec = DungeonSpec.model_validate({
            "metadata": {
                "name": "Forsaken Ice Tomb",
                "theme": "ice",
                "difficulty": "medium",
                "estimated_minutes": 25,
            },
            "rooms": [
                {
                    "id": "entrance",
                    "template": "small_chamber_2exit",
                    "theme_overrides": {"floor": "ice", "walls": "frozen_stone"},
                    "actors": [{"type": "freezard", "count": 2}],
                    "chests": [],
                },
                {
                    "id": "key_puzzle",
                    "template": "block_push_room",
                    "actors": [{"type": "white_wolfos", "count": 1}],
                    "chests": [{"id": "c1", "contents": "small_key"}],
                },
                {
                    "id": "boss_arena",
                    "template": "boss_arena",
                    "actors": [],
                    "chests": [],
                },
            ],
            "connections": [
                {"from": "entrance", "to": "key_puzzle", "type": "open_door"},
                {"from": "entrance", "to": "boss_arena", "type": "small_key_door"},
            ],
            "logic": {
                "small_keys_required": 1,
                "boss": {"type": "iron_knuckle", "room": "boss_arena"},
            },
        })
        assert spec.metadata.name == "Forsaken Ice Tomb"
        assert len(spec.rooms) == 3
        assert spec.logic.boss.type == ActorType.iron_knuckle
