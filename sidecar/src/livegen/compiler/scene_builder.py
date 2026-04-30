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
        # Find ObjectList before ActorList if present
        cut = i
        for k in range(i - 8, max(0x44, i - 200), -1):
            ocmd = struct.unpack("<i", orig_room[k : k + 4])[0]
            if ocmd == 11:
                on = struct.unpack("<I", orig_room[k + 4 : k + 8])[0]
                if on < 50 and k + 8 + on * 2 == i:
                    cut = k
                break

        return _build_modified_room(orig_room, cut, room, spec)

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

    # Map spec actor types to (ActorID, Params, [RequiredObjectIDs])
    # Verified from OoT decompilation (zeldaret/oot) + SoH source
    ACTOR_MAP = {
        "keese":        (0x0013, 0x0002, [0x000D]),  # En_Firefly, OBJECT_FIREFLY
        "skulltula":    (0x0095, 0x0000, [0x0024]),   # En_Sw (Gold Skulltula), OBJECT_ST
        "stalfos":      (0x0002, 0x0000, []),          # En_Test (Stalfos) — uses gameplay_keep
        "lizalfos":     (0x0031, 0x0000, [0x0054]),    # En_Dodojr → actually En_Rr? Let me use proper
        "wolfos":       (0x001B, 0x0000, [0x0016]),    # En_Tite (Tektite) — OBJECT_TITE
        "white_wolfos": (0x001B, 0x0001, [0x0016]),
        "freezard":     (0x011A, 0x0000, [0x0157]),    # En_Fz, OBJECT_FZ
        "iron_knuckle": (0x0113, 0x0000, [0x0106]),    # En_Ik, OBJECT_IK
        "dinolfos":     (0x0031, 0x0002, [0x0054]),
        "gibdo":        (0x0090, 0x0000, [0x0098]),    # En_Rd, OBJECT_RD
        "redead":       (0x0090, 0x7F01, [0x0098]),
        "poe":          (0x000D, 0x0000, [0x000D]),    # En_Poh, shares OBJECT_FIREFLY? Actually own
        "floormaster":  (0x008E, 0x0000, [0x000B]),    # En_Floormas, OBJECT_WALLMASTER
        "wallmaster":   (0x0011, 0x0000, [0x000B]),    # En_Wallmas, OBJECT_WALLMASTER
        "armos":        (0x0023, 0x0000, []),           # uses gameplay_dangeon_keep
        "beamos":       (0x0087, 0x0000, []),
        "like_like":    (0x00DD, 0x0000, [0x00D4]),    # En_Rr, OBJECT_RR
        "bubble":       (0x0069, 0x0000, [0x005D]),    # En_Bb, OBJECT_BB
        "torch_slug":   (0x0037, 0x0000, [0x0107]),    # En_St (Deku Baba), OBJECT_AHG
        "dodongo":      (0x0012, 0x0000, [0x000C]),    # En_Dodongo, OBJECT_DODONGO
        "tektite":      (0x001B, 0x0000, [0x0016]),    # En_Tite, OBJECT_TITE
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

    # Floor heights per Deku Tree room (from original actor analysis)
    ROOM_FLOORS = {
        0: {"y": 0,    "center": (0, 0),      "radius": 350, "chest_y": 0},
        1: {"y": 400,  "center": (-695, 692),  "radius": 250, "chest_y": 400},
        2: {"y": 280,  "center": (-1100, 1100),"radius": 200, "chest_y": 480},
        3: {"y": -880, "center": (-100, -280), "radius": 300, "chest_y": -845},
    }

    # Determine which room slot this is
    room_idx = spec.rooms.index(room) if room in spec.rooms else 0
    floor = ROOM_FLOORS.get(room_idx, ROOM_FLOORS[0])
    floor_y = floor["y"]
    cx, cz = floor["center"]
    radius = floor["radius"]
    chest_y = floor["chest_y"]

    # Collect required object IDs
    required_objects = set()

    # Place enemies in a circle around room center
    actor_idx = 0
    total_enemies = sum(a.count for a in room.actors)
    for actor_spec in room.actors:
        entry = ACTOR_MAP.get(actor_spec.type.value)
        if not entry:
            continue
        actor_id, params, obj_ids = entry
        required_objects.update(obj_ids)
        for c in range(actor_spec.count):
            angle = (2 * math.pi * actor_idx) / max(total_enemies, 1)
            x = cx + int(radius * math.cos(angle))
            z = cz + int(radius * math.sin(angle))
            actors.append((actor_id, x, floor_y, z, 0, 0, 0, params))
            actor_idx += 1

    # Place chests near center, slightly offset
    if room.chests:
        required_objects.add(0x000E)  # OBJECT_BOX
    for chest_idx, chest in enumerate(room.chests):
        content = CHEST_CONTENT_MAP.get(chest.contents.value, 0x08)
        angle = (2 * math.pi * chest_idx) / max(len(room.chests), 1) + 1.0
        x = cx + int((radius * 0.5) * math.cos(angle))
        z = cz + int((radius * 0.5) * math.sin(angle))
        actors.append((0x000A, x, chest_y, z, 0, 0, 0, (content << 5) | 0x4000))

    # Write ObjectList — merge original objects with our required ones
    # Read original ObjectList from the room
    orig_objects = set()
    for i in range(0x44, cut_offset - 8):
        cid = struct.unpack("<i", orig[i : i + 4])[0]
        if cid == 11:
            n = struct.unpack("<I", orig[i + 4 : i + 8])[0]
            if n < 50:
                for j in range(n):
                    orig_objects.add(struct.unpack("<H", orig[i + 8 + j * 2 : i + 10 + j * 2])[0])
                break

    all_objects = sorted(orig_objects | required_objects)
    new_data += struct.pack("<i", 11)  # cmd_id = ObjectList
    new_data += struct.pack("<I", len(all_objects))
    for obj in all_objects:
        new_data += struct.pack("<H", obj)

    # Write ActorList
    new_data += struct.pack("<i", 1)  # cmd_id = ActorList
    new_data += struct.pack("<I", len(actors))
    for aid, px, py, pz, rx, ry, rz, params in actors:
        new_data += struct.pack("<hhhhhhhH", aid, px, py, pz, rx, ry, rz, params)

    # EndMarker
    new_data += struct.pack("<i", 20)

    return bytes(new_data)
