"""Tests for layout solver and logic validator."""

from livegen.schema import DungeonSpec
from livegen.solver.layout import solve_layout
from livegen.solver.logic import validate_logic


def _make_spec(**overrides) -> DungeonSpec:
    base = {
        "metadata": {"name": "Test", "theme": "ice", "difficulty": "medium"},
        "rooms": [
            {"id": "entrance", "template": "small_chamber_2exit", "chests": []},
            {"id": "middle", "template": "corridor_straight", "chests": [{"id": "c1", "contents": "small_key"}]},
            {"id": "boss", "template": "boss_arena", "chests": []},
        ],
        "connections": [
            {"from": "entrance", "to": "middle", "type": "open_door"},
            {"from": "middle", "to": "boss", "type": "small_key_door"},
        ],
        "logic": {"small_keys_required": 1, "boss": {"type": "iron_knuckle", "room": "boss"}},
    }
    base.update(overrides)
    return DungeonSpec.model_validate(base)


class TestLayout:
    def test_basic_layout(self):
        spec = _make_spec()
        result = solve_layout(spec)
        assert result.is_valid
        assert len(result.placements) == 3

    def test_no_overlaps(self):
        spec = _make_spec()
        result = solve_layout(spec)
        positions = {(p.grid_x, p.grid_y) for p in result.placements}
        assert len(positions) == len(result.placements)

    def test_larger_dungeon(self):
        spec = DungeonSpec.model_validate({
            "metadata": {"name": "Big", "theme": "fire", "difficulty": "hard"},
            "rooms": [{"id": f"room_{i}", "template": "small_chamber_2exit"} for i in range(8)],
            "connections": [
                {"from": "room_0", "to": "room_1"},
                {"from": "room_0", "to": "room_2"},
                {"from": "room_1", "to": "room_3"},
                {"from": "room_2", "to": "room_4"},
                {"from": "room_3", "to": "room_5"},
                {"from": "room_4", "to": "room_5"},
                {"from": "room_5", "to": "room_6"},
                {"from": "room_6", "to": "room_7"},
            ],
            "logic": {},
        })
        result = solve_layout(spec)
        assert result.is_valid
        assert len(result.placements) == 8


class TestLogic:
    def test_solvable_dungeon(self):
        spec = _make_spec()
        result = validate_logic(spec)
        assert result.is_solvable
        assert len(result.reachable_rooms) == 3

    def test_unsolvable_no_key(self):
        spec = DungeonSpec.model_validate({
            "metadata": {"name": "Stuck", "theme": "ice", "difficulty": "easy"},
            "rooms": [
                {"id": "entrance", "template": "small_chamber_2exit", "chests": []},
                {"id": "locked", "template": "corridor_straight",
                 "chests": [{"id": "c1", "contents": "small_key"}]},
                {"id": "boss", "template": "boss_arena", "chests": []},
            ],
            "connections": [
                {"from": "entrance", "to": "locked", "type": "small_key_door"},
                {"from": "locked", "to": "boss", "type": "open_door"},
            ],
            "logic": {"boss": {"type": "stalfos", "room": "boss"}},
        })
        result = validate_logic(spec)
        assert not result.is_solvable
        assert "Unreachable" in result.errors[0]

    def test_key_before_door(self):
        """Key is in a reachable room before the locked door."""
        spec = DungeonSpec.model_validate({
            "metadata": {"name": "Keyed", "theme": "forest", "difficulty": "medium"},
            "rooms": [
                {"id": "entrance", "template": "large_hall_4exit",
                 "chests": [{"id": "k1", "contents": "small_key"}]},
                {"id": "locked_room", "template": "corridor_straight", "chests": []},
                {"id": "boss", "template": "boss_arena", "chests": []},
            ],
            "connections": [
                {"from": "entrance", "to": "locked_room", "type": "small_key_door"},
                {"from": "locked_room", "to": "boss", "type": "open_door"},
            ],
            "logic": {"small_keys_required": 1, "boss": {"type": "stalfos", "room": "boss"}},
        })
        result = validate_logic(spec)
        assert result.is_solvable

    def test_boss_key_logic(self):
        """Boss key must be found before boss door."""
        spec = DungeonSpec.model_validate({
            "metadata": {"name": "BossKey", "theme": "shadow", "difficulty": "hard"},
            "rooms": [
                {"id": "entrance", "template": "small_chamber_2exit", "chests": []},
                {"id": "key_room", "template": "corridor_straight",
                 "chests": [{"id": "bk", "contents": "boss_key"}]},
                {"id": "boss", "template": "boss_arena", "chests": []},
            ],
            "connections": [
                {"from": "entrance", "to": "key_room", "type": "open_door"},
                {"from": "entrance", "to": "boss", "type": "boss_key_door"},
            ],
            "logic": {"boss_key_chest": "key_room.bk", "boss": {"type": "iron_knuckle", "room": "boss"}},
        })
        result = validate_logic(spec)
        assert result.is_solvable
