"""Pydantic models for the dungeon generation schema.

The LLM produces a DungeonSpec — a graph of rooms, connections, and logic
constraints. It never produces raw geometry; the layout solver handles that.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Theme(str, Enum):
    forest = "forest"
    fire = "fire"
    water = "water"
    shadow = "shadow"
    spirit = "spirit"
    ice = "ice"
    stone = "stone"
    generic = "generic"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class DoorType(str, Enum):
    open_door = "open_door"
    small_key_door = "small_key_door"
    boss_key_door = "boss_key_door"
    puzzle_door = "puzzle_door"
    one_way = "one_way"


class ActorType(str, Enum):
    """Enemy and NPC types available in OoT."""
    keese = "keese"
    skulltula = "skulltula"
    stalfos = "stalfos"
    lizalfos = "lizalfos"
    wolfos = "wolfos"
    white_wolfos = "white_wolfos"
    freezard = "freezard"
    iron_knuckle = "iron_knuckle"
    dinolfos = "dinolfos"
    gibdo = "gibdo"
    redead = "redead"
    poe = "poe"
    floormaster = "floormaster"
    wallmaster = "wallmaster"
    armos = "armos"
    beamos = "beamos"
    like_like = "like_like"
    bubble = "bubble"
    torch_slug = "torch_slug"
    dodongo = "dodongo"
    tektite = "tektite"


class ChestContent(str, Enum):
    small_key = "small_key"
    boss_key = "boss_key"
    map = "map"
    compass = "compass"
    arrows_10 = "arrows_10"
    arrows_30 = "arrows_30"
    bombs_5 = "bombs_5"
    bombs_10 = "bombs_10"
    rupees_5 = "rupees_5"
    rupees_20 = "rupees_20"
    rupees_50 = "rupees_50"
    recovery_heart = "recovery_heart"
    piece_of_heart = "piece_of_heart"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class ThemeOverrides(BaseModel):
    floor: str | None = None
    walls: str | None = None
    ceiling: str | None = None


class Actor(BaseModel):
    type: ActorType
    count: int = Field(ge=1, le=10, default=1)


class Chest(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    contents: ChestContent


class Room(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    template: str = Field(description="Template ID from the room catalog")
    theme_overrides: ThemeOverrides | None = None
    actors: list[Actor] = Field(default_factory=list)
    chests: list[Chest] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_chest_ids(self) -> Room:
        ids = [c.id for c in self.chests]
        if len(ids) != len(set(ids)):
            msg = f"Duplicate chest IDs in room '{self.id}'"
            raise ValueError(msg)
        return self


class Connection(BaseModel):
    from_room: str = Field(alias="from")
    to_room: str = Field(alias="to")
    type: DoorType = DoorType.open_door

    model_config = {"populate_by_name": True}


class BossSpec(BaseModel):
    type: ActorType
    room: str


class Logic(BaseModel):
    small_keys_required: int = Field(ge=0, default=0)
    boss_key_chest: str | None = Field(
        default=None,
        description="Room.chest reference like 'room_id.chest_id'",
    )
    map_chest: str | None = None
    compass_chest: str | None = None
    boss: BossSpec | None = None


class Metadata(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    theme: Theme = Theme.generic
    difficulty: Difficulty = Difficulty.medium
    estimated_minutes: int = Field(ge=5, le=120, default=20)


# ---------------------------------------------------------------------------
# Top-level spec
# ---------------------------------------------------------------------------

class DungeonSpec(BaseModel):
    """Complete dungeon specification produced by the LLM agent."""

    metadata: Metadata
    rooms: list[Room] = Field(min_length=2)
    connections: list[Connection] = Field(min_length=1)
    logic: Logic = Field(default_factory=Logic)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> DungeonSpec:
        room_ids = {r.id for r in self.rooms}

        # All connections reference existing rooms
        for conn in self.connections:
            if conn.from_room not in room_ids:
                msg = f"Connection references unknown room '{conn.from_room}'"
                raise ValueError(msg)
            if conn.to_room not in room_ids:
                msg = f"Connection references unknown room '{conn.to_room}'"
                raise ValueError(msg)

        # Chest references in logic are valid
        def _check_chest_ref(ref: str | None, field: str) -> None:
            if ref is None:
                return
            parts = ref.split(".")
            if len(parts) != 2:
                msg = f"logic.{field} must be 'room_id.chest_id', got '{ref}'"
                raise ValueError(msg)
            room_id, chest_id = parts
            if room_id not in room_ids:
                msg = f"logic.{field} references unknown room '{room_id}'"
                raise ValueError(msg)
            room = next(r for r in self.rooms if r.id == room_id)
            if not any(c.id == chest_id for c in room.chests):
                msg = f"logic.{field} references unknown chest '{chest_id}' in room '{room_id}'"
                raise ValueError(msg)

        _check_chest_ref(self.logic.boss_key_chest, "boss_key_chest")
        _check_chest_ref(self.logic.map_chest, "map_chest")
        _check_chest_ref(self.logic.compass_chest, "compass_chest")

        # Boss room must exist
        if self.logic.boss and self.logic.boss.room not in room_ids:
            msg = f"Boss room '{self.logic.boss.room}' does not exist"
            raise ValueError(msg)

        # Unique room IDs
        if len(room_ids) != len(self.rooms):
            msg = "Duplicate room IDs"
            raise ValueError(msg)

        # Key count consistency
        key_doors = sum(1 for c in self.connections if c.type == DoorType.small_key_door)
        key_chests = sum(
            1
            for r in self.rooms
            for c in r.chests
            if c.contents == ChestContent.small_key
        )
        if key_chests < key_doors:
            msg = (
                f"Not enough small keys: {key_doors} locked doors but only "
                f"{key_chests} key chests"
            )
            raise ValueError(msg)

        return self


# ---------------------------------------------------------------------------
# Agent interaction models
# ---------------------------------------------------------------------------

class PlayerQuestion(BaseModel):
    """A question the agent asks the player before generating."""
    question: str
    options: list[str] | None = None


class GenerationResult(BaseModel):
    """Result of a dungeon generation session."""
    status: Literal["questions", "complete", "error"]
    question: PlayerQuestion | None = None
    spec: DungeonSpec | None = None
    error: str | None = None
