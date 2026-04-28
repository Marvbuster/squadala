"""Room template library — loads and indexes OoT dungeon room templates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path


@dataclass
class RoomTemplate:
    """A single room template extracted from an OoT dungeon."""

    dungeon: str
    scene: str
    room_id: str
    theme: str
    room_type: str  # entrance, hub, junction, corridor, dead_end, pre_boss
    exits: int
    connects_to: list[int]
    size: str  # small, medium, large

    @property
    def template_id(self) -> str:
        return f"{self.scene}_{self.room_id}"


@dataclass
class DungeonPattern:
    """A reusable dungeon layout pattern."""

    name: str
    description: str


@dataclass
class TemplateLibrary:
    """Indexes and queries room templates from the catalog."""

    templates: list[RoomTemplate] = field(default_factory=list)
    patterns: dict[str, DungeonPattern] = field(default_factory=dict)

    @classmethod
    def load(cls, catalog_path: Path | None = None) -> TemplateLibrary:
        """Load templates from the JSON catalog."""
        if catalog_path is None:
            catalog_path = Path(__file__).parent / "catalog" / "rooms.json"

        with open(catalog_path) as f:
            data = json.load(f)

        lib = cls()

        for dungeon_key, dungeon in data.get("dungeons", {}).items():
            theme = dungeon.get("theme", "generic")
            scene = dungeon.get("scene", dungeon_key)
            for room_id, room in dungeon.get("rooms", {}).items():
                lib.templates.append(
                    RoomTemplate(
                        dungeon=dungeon.get("name", dungeon_key),
                        scene=scene,
                        room_id=room_id,
                        theme=theme,
                        room_type=room.get("type", "corridor"),
                        exits=room.get("exits", 0),
                        connects_to=room.get("connects", []),
                        size=room.get("size", "medium"),
                    )
                )

        for pattern_key, pattern in data.get("design_patterns", {}).items():
            lib.patterns[pattern_key] = DungeonPattern(
                name=pattern_key,
                description=pattern,
            )

        return lib

    def by_type(self, room_type: str) -> list[RoomTemplate]:
        """Get all templates of a specific type."""
        return [t for t in self.templates if t.room_type == room_type]

    def by_exits(self, min_exits: int, max_exits: int | None = None) -> list[RoomTemplate]:
        """Get templates with a specific exit count range."""
        if max_exits is None:
            max_exits = min_exits
        return [t for t in self.templates if min_exits <= t.exits <= max_exits]

    def by_theme(self, theme: str) -> list[RoomTemplate]:
        """Get all templates matching a theme."""
        return [t for t in self.templates if t.theme == theme]

    def by_dungeon(self, dungeon: str) -> list[RoomTemplate]:
        """Get all templates from a specific dungeon."""
        return [t for t in self.templates if t.dungeon.lower() == dungeon.lower()]

    def hubs(self) -> list[RoomTemplate]:
        """Get all hub rooms (4+ exits)."""
        return self.by_type("hub")

    def dead_ends(self) -> list[RoomTemplate]:
        """Get all dead-end rooms (1 exit)."""
        return self.by_type("dead_end")

    def summary(self) -> dict:
        """Return a summary of the template library."""
        from collections import Counter

        types = Counter(t.room_type for t in self.templates)
        themes = Counter(t.theme for t in self.templates)
        dungeons = Counter(t.dungeon for t in self.templates)
        return {
            "total_templates": len(self.templates),
            "by_type": dict(types),
            "by_theme": dict(themes),
            "by_dungeon": dict(dungeons),
            "patterns": list(self.patterns.keys()),
        }
