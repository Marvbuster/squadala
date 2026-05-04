"""Bridge: DungeonSpec → custom box-room .o2r via tooling/build_box_room.

Closes the M6 loop: the LLM produces an abstract DungeonSpec (rooms with
actors and chests, no positions). This module turns that abstract spec into
a concrete actor-placement list and feeds it through the box-room builder
that already powers the standalone debug-room test.

Currently emits exactly one custom-geometry room (room 0 of the spec). The
rest of the spec is ignored — multi-room is M7.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from livegen.schema import ActorType, ChestContent, DungeonSpec, Room

# tooling/ is a sibling of sidecar/ — add it to the import path so we can
# call into build_box_room directly. Avoids duplicating the ~830 LoC of
# o2r-byte-layout code.
_TOOLING_DIR = Path(__file__).resolve().parents[4] / "tooling"
if str(_TOOLING_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLING_DIR))

import build_box_room as bbr  # noqa: E402

# ---------------------------------------------------------------------------
# Mappings — DungeonSpec abstract types → tooling/build_box_room concrete IDs
# ---------------------------------------------------------------------------

# ActorType enum value → ACTOR_LIBRARY key in build_box_room. Each ActorType
# from the schema is mapped to its corresponding library entry; unmapped
# values would silently disappear from the placement, so keep this in sync
# with bbr.ACTOR_LIBRARY when new actors land there.
ACTOR_TYPE_TO_LIBRARY: dict[str, str] = {
    ActorType.keese.value:        "keese",
    ActorType.skulltula.value:    "skulltula",
    ActorType.stalfos.value:      "stalfos",
    ActorType.lizalfos.value:     "lizalfos",
    ActorType.wolfos.value:       "wolfos",
    ActorType.white_wolfos.value: "white_wolfos",
    ActorType.freezard.value:     "freezard",
    ActorType.iron_knuckle.value: "iron_knuckle",
    ActorType.dinolfos.value:     "dinolfos",
    ActorType.gibdo.value:        "gibdo",
    ActorType.redead.value:       "redead",
    ActorType.poe.value:          "poe",
    ActorType.floormaster.value:  "floormaster",
    ActorType.wallmaster.value:   "wallmaster",
    ActorType.armos.value:        "armos",
    ActorType.beamos.value:       "beamos",
    ActorType.like_like.value:    "like_like",
    ActorType.bubble.value:       "bubble",
    ActorType.torch_slug.value:   "torch_slug",
    ActorType.dodongo.value:      "dodongo",
    ActorType.tektite.value:      "tektite",
}

# ChestContent enum value → GetItemID byte that fits En_Box's 7-bit
# chest-params field. Pulled from the verified GI_* constants in
# tooling/build_box_room.py and z64item.h.
CHEST_CONTENT_TO_GI: dict[str, int] = {
    ChestContent.piece_of_heart.value: bbr.GI_HEART_PIECE,
    ChestContent.map.value:            bbr.GI_MAP,
    ChestContent.compass.value:        bbr.GI_COMPASS,
    ChestContent.small_key.value:      bbr.GI_KEY_SMALL,
    ChestContent.boss_key.value:       bbr.GI_KEY_BOSS,
    ChestContent.rupees_5.value:       bbr.GI_RUPEE_GREEN,
    ChestContent.rupees_20.value:      bbr.GI_RUPEE_RED,
    ChestContent.rupees_50.value:      bbr.GI_RUPEE_PURPLE,
    # Custom Squadala item — registered additively in soh-fork
    ChestContent.livegen_mario.value:  bbr.GI_LIVEGEN_MARIO,
}

# ---------------------------------------------------------------------------
# Layout — abstract spec → concrete (x, y, z) positions inside the box room
# ---------------------------------------------------------------------------

ROOM_FLOOR_Y = -100        # box-room floor matches the standalone debug-room
ENEMY_RING_RADIUS = 350    # actors arranged on this circle
CHEST_OFFSET_RADIUS = 0    # chest at room centre


def _enemies_to_actors(actors_field: list, ring_total: int) -> list[dict]:
    """Distribute enemies evenly on a circle around the room centre."""
    placed: list[dict] = []
    idx = 0
    for actor_spec in actors_field:
        lib_name = ACTOR_TYPE_TO_LIBRARY.get(actor_spec.type.value)
        if lib_name is None:
            continue  # silently skip unmapped enemy types for now
        for _ in range(actor_spec.count):
            angle = (2 * math.pi * idx) / max(ring_total, 1)
            x = int(ENEMY_RING_RADIUS * math.cos(angle))
            z = int(ENEMY_RING_RADIUS * math.sin(angle))
            placed.append({"name": lib_name, "x": x, "y": ROOM_FLOOR_Y, "z": z})
            idx += 1
    return placed


def _chests_to_actors(chests_field: list) -> list[dict]:
    """Place chests at room centre, fanned out if there are several."""
    placed: list[dict] = []
    n = len(chests_field)
    for i, chest in enumerate(chests_field):
        gi = CHEST_CONTENT_TO_GI.get(chest.contents.value, bbr.GI_HEART_PIECE)
        # Fan out only when more than one chest sits in the room.
        angle = (2 * math.pi * i) / max(n, 1)
        x = int(CHEST_OFFSET_RADIUS * math.cos(angle))
        z = int(CHEST_OFFSET_RADIUS * math.sin(angle))
        placed.append({
            "name": "chest",
            "x": x,
            "y": ROOM_FLOOR_Y,
            "z": z,
            "rot_y": 0x8000,                    # face south so player approaches naturally
            "params": bbr.chest_params(item_id=gi, treasure_flag=(i + 1) & 0x1F),
        })
    return placed


def spec_to_actors(room: Room) -> list[dict]:
    """Translate a single Room from a DungeonSpec into a list of placed actors.

    Output format matches what build_box_room.build_room_header expects:
    [{"name": <library_key>, "x": int, "y": int, "z": int, "rot_y": int?, "params": int?}, ...]
    """
    total_enemies = sum(
        a.count for a in room.actors
        if a.type.value in ACTOR_TYPE_TO_LIBRARY
    )
    return _enemies_to_actors(room.actors, total_enemies) + _chests_to_actors(room.chests)


def build_dungeon_o2r(spec: DungeonSpec, output_path: Path | str) -> Path:
    """Compile a DungeonSpec to a custom-geometry .o2r.

    Currently uses spec.rooms[0] as the only custom room. Multi-room (M7)
    will fan out to additional templates and connect them via En_Holl.
    """
    room0 = spec.rooms[0]
    actors = spec_to_actors(room0)
    return bbr.build_dungeon_o2r(output_path, actors=actors)
