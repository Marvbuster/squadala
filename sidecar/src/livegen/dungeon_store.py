"""Persistent storage for generated dungeons."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from livegen.schema import DungeonSpec

STORE_DIR = Path.home() / ".squadala" / "dungeons"


@dataclass
class StoredDungeon:
    id: str
    name: str
    theme: str
    difficulty: str
    rooms: int
    connections: int
    created_at: float
    spec: dict
    compiled: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "theme": self.theme,
            "difficulty": self.difficulty,
            "rooms": self.rooms,
            "connections": self.connections,
            "created_at": self.created_at,
            "compiled": self.compiled,
            "spec": self.spec,
        }


class DungeonStore:
    def __init__(self, store_dir: Path = STORE_DIR):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._active_id: str | None = None
        self._load_active()

    def save(self, spec: DungeonSpec) -> StoredDungeon:
        """Save a generated dungeon and return its stored entry."""
        dungeon_id = f"{int(time.time())}_{spec.metadata.name.lower().replace(' ', '_')[:20]}"
        entry = StoredDungeon(
            id=dungeon_id,
            name=spec.metadata.name,
            theme=spec.metadata.theme.value,
            difficulty=spec.metadata.difficulty.value,
            rooms=len(spec.rooms),
            connections=len(spec.connections),
            created_at=time.time(),
            spec=spec.model_dump(exclude_none=True),
        )
        path = self.store_dir / f"{dungeon_id}.json"
        path.write_text(json.dumps(entry.to_dict(), indent=2))
        return entry

    def list_all(self) -> list[StoredDungeon]:
        """List all saved dungeons, newest first."""
        dungeons = []
        for path in sorted(self.store_dir.glob("*.json"), reverse=True):
            if path.name == "active.json":
                continue
            try:
                data = json.loads(path.read_text())
                dungeons.append(StoredDungeon(**data))
            except Exception:
                continue
        return dungeons

    def get(self, dungeon_id: str) -> StoredDungeon | None:
        path = self.store_dir / f"{dungeon_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return StoredDungeon(**data)

    def delete(self, dungeon_id: str) -> bool:
        path = self.store_dir / f"{dungeon_id}.json"
        if path.exists():
            path.unlink()
            if self._active_id == dungeon_id:
                self._active_id = None
                self._save_active()
            return True
        return False

    def set_active(self, dungeon_id: str) -> bool:
        """Set which dungeon is the active one (will be loaded on SoH start)."""
        if self.get(dungeon_id) is None:
            return False
        self._active_id = dungeon_id
        self._save_active()
        return True

    def get_active_id(self) -> str | None:
        return self._active_id

    def get_active(self) -> StoredDungeon | None:
        if not self._active_id:
            return None
        return self.get(self._active_id)

    def mark_compiled(self, dungeon_id: str) -> None:
        entry = self.get(dungeon_id)
        if entry:
            entry.compiled = True
            path = self.store_dir / f"{dungeon_id}.json"
            path.write_text(json.dumps(entry.to_dict(), indent=2))

    def _load_active(self) -> None:
        path = self.store_dir / "active.json"
        if path.exists():
            data = json.loads(path.read_text())
            self._active_id = data.get("active_id")

    def _save_active(self) -> None:
        path = self.store_dir / "active.json"
        path.write_text(json.dumps({"active_id": self._active_id}))
