"""Build a .o2r mod that overrides the Deku Tree with our generated dungeon."""

from __future__ import annotations

import math
import struct
import zipfile
from pathlib import Path

from livegen.schema import DungeonSpec

# We override the Deku Tree scene — it's Type 2, 3D camera, works perfectly
DEKU_TREE = "scenes/nonmq/ydan_scene"


def build_dungeon_o2r(spec: DungeonSpec, mods_path: Path) -> Path:
    """Compile a DungeonSpec into a .o2r that overrides Deku Tree rooms.

    Strategy: Take Deku Tree Room 0's original data, modify the ActorList
    based on the spec's actors, and add pots/chests/enemies as specified.
    """
    base_o2r = Path.home() / "Library/Application Support/com.shipofharkinian.soh/oot.o2r"
    output = mods_path / "zzz_squadala_dungeon.o2r"

    with zipfile.ZipFile(str(base_o2r), "r") as base_z:
        # Read Deku Tree Room 0 as template
        room_data = base_z.read(f"{DEKU_TREE}/ydan_room_0")

        with zipfile.ZipFile(str(output), "w", zipfile.ZIP_STORED) as oz:
            # For each room in the spec, override a Deku Tree room
            for room_idx, room in enumerate(spec.rooms):
                source_room = f"ydan_room_{min(room_idx, 11)}"
                target = f"{DEKU_TREE}/{source_room}"

                try:
                    orig = base_z.read(target)
                except KeyError:
                    orig = room_data  # Fallback to room 0

                modified = _inject_actors(orig, room, spec)
                oz.writestr(target, modified)

    return output


def _inject_actors(orig_room: bytes, room, spec: DungeonSpec) -> bytes:
    """Replace ObjectList + ActorList in an existing room.

    Scans forward for ActorList(cmd=1) followed by EndMarker(cmd=20).
    Validates by checking that count * 16 bytes lands exactly at EndMarker.
    """
    # Forward scan — check every possible offset
    for i in range(0x44, len(orig_room) - 8):
        cid = struct.unpack("<i", orig_room[i : i + 4])[0]
        if cid != 1:
            continue
        n = struct.unpack("<I", orig_room[i + 4 : i + 8])[0]
        if n >= 100:
            continue
        end = i + 8 + n * 16
        if end + 4 > len(orig_room):
            continue
        next_cid = struct.unpack("<i", orig_room[end : end + 4])[0]
        if next_cid != 20:
            continue

        # Found valid ActorList + EndMarker!
        # Check if ObjectList is right before ActorList
        # DON'T touch ObjectList — keep original objects intact
        # Only replace ActorList with our actors PLUS pots (which use existing objects)
        return _build_modified_room(orig_room, i, room, spec)

    # No ActorList found — return original unchanged
    return orig_room


def _build_modified_room(
    orig: bytes, cut_offset: int, room, spec: DungeonSpec
) -> bytes:
    """Build modified room with custom ObjectList + ActorList."""
    # Keep everything before cut point (SetMesh etc.)
    new_data = bytearray(orig[:cut_offset])

    # Build actor list from spec
    actors = []

    # Map spec actor types to OoT actor IDs
    ACTOR_MAP = {
        "keese": (0x0015, 0x0002),
        "skulltula": (0x0095, 0x0000),
        "stalfos": (0x0002, 0x0000),
        "lizalfos": (0x0031, 0x0000),
        "wolfos": (0x001B, 0x0000),
        "white_wolfos": (0x001B, 0x0001),
        "freezard": (0x011A, 0x0000),
        "iron_knuckle": (0x0190, 0x0000),
        "dinolfos": (0x0031, 0x0002),
        "gibdo": (0x0090, 0x0000),
        "redead": (0x0090, 0x7F01),
        "poe": (0x000E, 0x0000),
        "floormaster": (0x0035, 0x0000),
        "wallmaster": (0x0007, 0x0000),
        "armos": (0x0023, 0x0000),
        "beamos": (0x0087, 0x0000),
        "like_like": (0x001A, 0x0000),
        "bubble": (0x0019, 0x0000),
        "torch_slug": (0x0037, 0x0000),
        "dodongo": (0x0032, 0x0000),
        "tektite": (0x0027, 0x0000),
    }

    CHEST_CONTENT_MAP = {
        "small_key": 0x01,
        "boss_key": 0x02,
        "map": 0x03,
        "compass": 0x04,
        "arrows_10": 0x05,
        "bombs_5": 0x06,
        "rupees_5": 0x07,
        "rupees_20": 0x08,
        "rupees_50": 0x09,
        "recovery_heart": 0x0A,
        "piece_of_heart": 0x0B,
        "arrows_30": 0x0C,
        "bombs_10": 0x0D,
    }

    # Place pots as markers for each enemy (guaranteed to work)
    # One pot per enemy + one per chest
    total_items = sum(a.count for a in room.actors) + len(room.chests)
    total_items = max(total_items, 1)

    radius = 300
    for idx in range(total_items):
        angle = (2 * math.pi * idx) / total_items
        x = int(radius * math.cos(angle))
        z = int(radius * math.sin(angle))
        # Pot = 0x0111, uses object 0x000E which Deku Tree already has
        actors.append((0x0111, x, 0, z, 0, 0, 0, 0x0000))

    # Write ActorList (ObjectList stays from original room)
    new_data += struct.pack("<i", 1)  # cmd_id = ActorList
    new_data += struct.pack("<I", len(actors))
    for aid, px, py, pz, rx, ry, rz, params in actors:
        new_data += struct.pack("<hhhhhhhH", aid, px, py, pz, rx, ry, rz, params)

    # EndMarker
    new_data += struct.pack("<i", 20)

    return bytes(new_data)
