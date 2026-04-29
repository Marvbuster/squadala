"""Deterministic dungeon builder — called by LLM via tools."""

from __future__ import annotations

from dataclasses import dataclass, field

from livegen.schema import (
    Actor,
    ActorType,
    BossSpec,
    ChestContent,
    Chest,
    Connection,
    DoorType,
    DungeonSpec,
    Logic,
    Metadata,
    Room,
    Theme,
    Difficulty,
)

VALID_TEMPLATES = [
    "small_chamber_2exit",
    "small_chamber_3exit",
    "corridor_straight",
    "corridor_l_bend",
    "large_hall_4exit",
    "block_push_room",
    "pit_room",
    "lava_bridge_room",
    "water_room",
    "boss_arena",
]

VALID_ENEMIES = [e.value for e in ActorType]
VALID_CHEST_CONTENTS = [c.value for c in ChestContent]
VALID_DOOR_TYPES = [d.value for d in DoorType]
VALID_THEMES = [t.value for t in Theme]


@dataclass
class DungeonBuilder:
    """Accumulates dungeon pieces via simple tool calls, then builds a valid DungeonSpec."""

    name: str = "Generated Dungeon"
    theme: str = "generic"
    difficulty: str = "medium"
    rooms: dict[str, dict] = field(default_factory=dict)
    connections: list[dict] = field(default_factory=list)
    boss_room: str | None = None
    boss_type: str | None = None
    _chest_counter: int = 0

    def create_room(self, name: str, template: str = "small_chamber_2exit") -> str:
        """Create a room. Returns room_id or error message."""
        import re
        room_id = re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_").replace("-", "_"))
        if not room_id or not room_id[0].isalpha():
            room_id = f"room_{room_id}" if room_id else f"room_{len(self.rooms)}"

        if room_id in self.rooms:
            return f"Room '{room_id}' already exists."

        if template not in VALID_TEMPLATES:
            template = "small_chamber_2exit"

        self.rooms[room_id] = {
            "id": room_id,
            "template": template,
            "actors": [],
            "chests": [],
        }
        return f"Room '{room_id}' created with template '{template}'."

    def connect_rooms(self, room_a: str, room_b: str, door_type: str = "open_door") -> str:
        """Connect two rooms. Returns confirmation or error."""
        room_a = self._resolve_room(room_a)
        room_b = self._resolve_room(room_b)

        if room_a not in self.rooms:
            return f"Room '{room_a}' does not exist. Create it first."
        if room_b not in self.rooms:
            return f"Room '{room_b}' does not exist. Create it first."

        if door_type not in VALID_DOOR_TYPES:
            door_type = "open_door"

        # Auto-add key if locked door
        if door_type == "small_key_door":
            self._ensure_small_key(room_a)
        if door_type == "boss_key_door":
            self._ensure_boss_key(room_a)

        self.connections.append({"from": room_a, "to": room_b, "type": door_type})
        return f"Connected '{room_a}' → '{room_b}' via {door_type}."

    def add_enemy(self, room: str, enemy_type: str, count: int = 1) -> str:
        """Add enemies to a room."""
        room = self._resolve_room(room)
        if room not in self.rooms:
            return f"Room '{room}' does not exist."
        if enemy_type not in VALID_ENEMIES:
            return f"Unknown enemy '{enemy_type}'. Valid: {', '.join(VALID_ENEMIES[:10])}..."

        count = max(1, min(count, 10))
        self.rooms[room]["actors"].append({"type": enemy_type, "count": count})
        return f"Added {count}x {enemy_type} to '{room}'."

    def add_chest(self, room: str, contents: str) -> str:
        """Add a chest to a room."""
        room = self._resolve_room(room)
        if room not in self.rooms:
            return f"Room '{room}' does not exist."
        if contents not in VALID_CHEST_CONTENTS:
            return f"Unknown contents '{contents}'. Valid: {', '.join(VALID_CHEST_CONTENTS)}"

        self._chest_counter += 1
        chest_id = f"c{self._chest_counter}"
        self.rooms[room]["chests"].append({"id": chest_id, "contents": contents})
        return f"Chest '{chest_id}' ({contents}) added to '{room}'."

    def set_boss(self, room: str, boss_type: str) -> str:
        """Set the boss for the dungeon."""
        room = self._resolve_room(room)
        if room not in self.rooms:
            return f"Room '{room}' does not exist."
        if boss_type not in VALID_ENEMIES:
            return f"Unknown boss '{boss_type}'. Valid: {', '.join(VALID_ENEMIES[:10])}..."

        self.boss_room = room
        self.boss_type = boss_type
        self.rooms[room]["actors"].append({"type": boss_type, "count": 1})
        return f"Boss '{boss_type}' set in '{room}'."

    def set_dungeon_info(self, name: str, theme: str = "generic", difficulty: str = "medium") -> str:
        """Set dungeon name, theme, and difficulty."""
        self.name = name[:80]
        self.theme = theme if theme in VALID_THEMES else "generic"
        self.difficulty = difficulty if difficulty in ("easy", "medium", "hard") else "medium"
        return f"Dungeon: '{self.name}', theme={self.theme}, difficulty={self.difficulty}."

    def finalize(self) -> DungeonSpec | str:
        """Build and validate the final DungeonSpec. Returns spec or error string."""
        if len(self.rooms) < 2:
            return "Need at least 2 rooms. Use create_room first."
        if not self.connections:
            return "Need at least 1 connection. Use connect_rooms first."

        logic = Logic(small_keys_required=0)
        if self.boss_room and self.boss_type:
            logic.boss = BossSpec(type=ActorType(self.boss_type), room=self.boss_room)

        try:
            spec = DungeonSpec(
                metadata=Metadata(
                    name=self.name,
                    theme=Theme(self.theme),
                    difficulty=Difficulty(self.difficulty),
                ),
                rooms=[Room.model_validate(r) for r in self.rooms.values()],
                connections=[Connection.model_validate(c) for c in self.connections],
                logic=logic,
            )
            return spec
        except Exception as e:
            return f"Validation error: {e}"

    def _resolve_room(self, ref: str) -> str:
        """Resolve a room reference to a valid room ID."""
        import re
        ref = re.sub(r"[^a-z0-9_]", "", str(ref).lower().replace(" ", "_").replace("-", "_"))
        if not ref or not ref[0].isalpha():
            ref = f"room_{ref}" if ref else "room_0"
        if ref in self.rooms:
            return ref
        # Try fuzzy match
        for rid in self.rooms:
            if ref in rid or rid in ref:
                return rid
        return ref

    def _ensure_small_key(self, before_room: str) -> None:
        """Make sure there's a small key chest before a locked door."""
        has_key = any(
            c["contents"] == "small_key"
            for r in self.rooms.values()
            for c in r["chests"]
        )
        if not has_key:
            self._chest_counter += 1
            self.rooms[before_room]["chests"].append(
                {"id": f"c{self._chest_counter}", "contents": "small_key"}
            )

    def _ensure_boss_key(self, before_room: str) -> None:
        """Make sure there's a boss key chest before a boss door."""
        has_key = any(
            c["contents"] == "boss_key"
            for r in self.rooms.values()
            for c in r["chests"]
        )
        if not has_key:
            self._chest_counter += 1
            self.rooms[before_room]["chests"].append(
                {"id": f"c{self._chest_counter}", "contents": "boss_key"}
            )
