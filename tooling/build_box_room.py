"""Build a custom box room as .o2r and override Deku Tree Room 0.

Generates a box room with vertex-colored walls, proper N64 Display List
using G_VTX_OTR_HASH to reference a separate OVTX vertex resource.

All binary data is Little-Endian (Endianness::Little = 0 in SoH).
"""

import math
import struct
import zipfile
from pathlib import Path


# ============================================================
# CRC64 — exact port from libultraship/src/ship/utils/StrHash64.cpp
# Polynomial: ECMA-182 (0x42F0E1EBA9EA3693)
# Init: 0xFFFFFFFFFFFFFFFF
# No final inversion (differs from crc64() which inverts!)
# ============================================================

def _make_crc64_table():
    poly = 0x42F0E1EBA9EA3693
    table = []
    for i in range(256):
        crc = i << 56
        for _ in range(8):
            if crc & (1 << 63):
                crc = ((crc << 1) ^ poly) & 0xFFFFFFFFFFFFFFFF
            else:
                crc = (crc << 1) & 0xFFFFFFFFFFFFFFFF
        table.append(crc)
    return table


CRC64_TABLE = _make_crc64_table()


def crc64(s: str) -> int:
    """CRC64 hash matching SoH's CRC64(const char*) — no final inversion."""
    crc = 0xFFFFFFFFFFFFFFFF
    for b in s.encode('ascii'):
        crc = CRC64_TABLE[((crc >> 56) & 0xFF) ^ b] ^ ((crc << 8) & 0xFFFFFFFFFFFFFFFF)
    return crc


# ============================================================
# Resource Header — shared 0x40-byte header for all SoH resources
# ============================================================

# Resource type IDs (from Fast::ResourceType / SOH::ResourceType)
RES_DISPLAY_LIST = 0x4F444C54  # "ODLT"
RES_VERTEX = 0x4F565458        # "OVTX"
RES_SCENE = 0x4F524F4D         # "MORO" as LE uint32 — actually SOH_Scene
RES_ROOM = 0x4F524F4D          # Same type for Room
RES_COLLISION = 0x4F434F4C     # "LOCO" as LE uint32


def build_resource_header(res_type: int, version: int = 0) -> bytes:
    """Build the standard 0x40-byte SoH resource header."""
    header = bytearray(0x40)
    header[0] = 0  # Endianness::Little = 0
    header[1] = 0  # IsCustom = 0
    # bytes 2-3: padding
    struct.pack_into('<I', header, 4, res_type)
    struct.pack_into('<I', header, 8, version)
    struct.pack_into('<Q', header, 0x0C, 0xDEADBEEFDEADBEEF)  # Id
    # Remaining bytes stay 0 (version from table, ROM CRC, ROM enum, reserved)
    return bytes(header)


# ============================================================
# N64 GBI opcodes (F3DEX2)
# ============================================================

G_RDPPIPESYNC = 0xE7
G_SETOTHERMODE_L = 0xE2
G_SETOTHERMODE_H = 0xE3
G_GEOMETRYMODE = 0xD9
G_SETCOMBINE = 0xFC
G_TRI2 = 0x06
G_TRI1 = 0x05
G_ENDDL = 0xDF
G_TEXTURE = 0xD7

# OTR extension — expanded command (16 bytes)
G_VTX_OTR_HASH = 0x32

# Geometry mode flags
G_ZBUFFER = 0x00000001
G_SHADE = 0x00000004
G_CULL_BACK = 0x00002000
G_SHADING_SMOOTH = 0x00200000

# Pre-computed render mode: G_RM_AA_ZB_OPA_SURF | G_RM_AA_ZB_OPA_SURF2
RENDERMODE_AA_ZB_OPA = 0x00552078

# G_RM_OPA_SURF | G_RM_OPA_SURF2 — NO Z test, NO AA, simplest possible opaque
# CVG_DST_CLAMP=0 | FORCE_BL=0x4000 | ZMODE_OPA=0
# GBL_c1(P=0, A=3, M=0, B=2): (0<<30) | (3<<26) | (0<<22) | (2<<18) = 0x0C080000
# GBL_c2(P=0, A=3, M=0, B=2): (0<<28) | (3<<24) | (0<<20) | (2<<16) = 0x03020000
# Total: 0x0C080000 | 0x03020000 | 0x4000 = 0x0F0A4000
RENDERMODE_OPA_SURF_NO_Z = 0x0F0A4000


def gfx_le(w0: int, w1: int) -> bytes:
    """Pack one 8-byte GBI command in Little-Endian."""
    return struct.pack('<II', w0 & 0xFFFFFFFF, w1 & 0xFFFFFFFF)


# ============================================================
# Box Room Geometry
# ============================================================

def build_box_vertices(w=600, h=600, d=600):
    """24 vertices for a complete box room — 4 per face, each face has its own color.

    Player is INSIDE the box. Normals point inward (CCW winding from inside view).
    With G_CULL_BACK enabled, only inward-facing triangles render.
    """
    floor_y = -100   # matches collision floor
    ceiling_y = floor_y + h
    verts = []
    colors = []

    # 6 faces × 4 vertices each = 24 vertices total
    # Per face: (v0, v1, v2, v3) defines a quad, split into 2 tris later
    # Vertex order matters for inward-facing normals
    face_data = [
        # FLOOR (Y=floor_y, normal +Y)
        # Looking from above (inside): CCW order is BL, BR, TR, TL
        [(-w, floor_y,  d), ( w, floor_y,  d), ( w, floor_y, -d), (-w, floor_y, -d),
         (60, 180, 60, 255)],   # green floor

        # CEILING (Y=ceiling_y, normal -Y)
        # Looking from below (inside): CCW order opposite of floor
        [(-w, ceiling_y, -d), ( w, ceiling_y, -d), ( w, ceiling_y,  d), (-w, ceiling_y,  d),
         (180, 60, 60, 255)],   # red ceiling

        # NORTH WALL (Z=-d, normal +Z, inward)
        # From inside looking north: BL=(-w,bottom,-d), BR=(w,bottom,-d), TR=(w,top,-d), TL=(-w,top,-d)
        [(-w, floor_y, -d), ( w, floor_y, -d), ( w, ceiling_y, -d), (-w, ceiling_y, -d),
         (60, 100, 220, 255)],  # blue north wall

        # SOUTH WALL (Z=+d, normal -Z, inward)
        [( w, floor_y,  d), (-w, floor_y,  d), (-w, ceiling_y,  d), ( w, ceiling_y,  d),
         (220, 200, 60, 255)],  # yellow south wall

        # WEST WALL (X=-w, normal +X, inward)
        [(-w, floor_y,  d), (-w, floor_y, -d), (-w, ceiling_y, -d), (-w, ceiling_y,  d),
         (60, 200, 200, 255)],  # cyan west wall

        # EAST WALL (X=+w, normal -X, inward)
        [( w, floor_y, -d), ( w, floor_y,  d), ( w, ceiling_y,  d), ( w, ceiling_y, -d),
         (200, 60, 200, 255)],  # magenta east wall
    ]

    for v0, v1, v2, v3, col in face_data:
        verts.extend([v0, v1, v2, v3])
        colors.extend([col, col, col, col])

    return verts, colors


def build_box_faces():
    """12 triangles (6 quads × 2 tris). Each quad uses 4 dedicated vertices.

    Quad winding (v0, v1, v2, v3) is CCW from inside the room.
    Split into triangles: (v0, v1, v2) and (v0, v2, v3).
    """
    faces = []
    for face_idx in range(6):
        base = face_idx * 4
        v0, v1, v2, v3 = base, base + 1, base + 2, base + 3
        faces.append((v0, v1, v2))  # first triangle of quad
        faces.append((v0, v2, v3))  # second triangle of quad
    return faces


# ============================================================
# OVTX — Vertex Resource
# ============================================================

def build_vtx_resource(vertices, colors) -> bytes:
    """Build an OVTX vertex resource (header + uint32 count + N×16B vertex data).

    Vertex format (all LE):
        int16 x, y, z      — position
        uint16 flag         — unused (0)
        int16 tc_s, tc_t    — texture coords (0 for no texture)
        uint8 r, g, b, a    — vertex color
    """
    header = build_resource_header(RES_VERTEX)
    body = struct.pack('<I', len(vertices))  # vertex count
    for (x, y, z), (r, g, b, a) in zip(vertices, colors):
        body += struct.pack('<hhhH', x, y, z, 0)       # pos + flag
        body += struct.pack('<hh', 0, 0)                # tex coords
        body += struct.pack('BBBB', r, g, b, a)         # color
    return header + body


# ============================================================
# TLDO — Display List Resource with G_VTX_OTR_HASH
# ============================================================

def build_display_list(vtx_path: str, vtx_count: int, faces: list) -> bytes:
    """Build a TLDO display list that renders vertex-colored triangles.

    Uses G_VTX_OTR_HASH (0x32) to reference vertex data by CRC64 hash.
    """
    vtx_hash = crc64(vtx_path)

    cmds = bytearray()

    # 1. Pipeline sync
    cmds += gfx_le(G_RDPPIPESYNC << 24, 0)

    # 2. Set cycle type to 1-cycle
    #    gsSPSetOtherMode(G_SETOTHERMODE_H, sft=20, len=2, data=0)
    cmds += gfx_le(
        (G_SETOTHERMODE_H << 24) | ((32 - 20 - 2) << 8) | (2 - 1),
        0  # G_CYC_1CYCLE = 0
    )

    # 3. Set render mode: AA + Z-buffer + opaque surface (proper depth rendering)
    cmds += gfx_le(
        (G_SETOTHERMODE_L << 24) | ((32 - 3 - 29) << 8) | (29 - 1),
        RENDERMODE_AA_ZB_OPA
    )

    # 4. Load geometry mode: Z-buffer + smooth shaded vertex colors + cull back
    #    G_CULL_BACK in F3DEX2 = 0x00000400 (bit 10)
    G_CULL_BACK = 0x00000400
    geom_flags = G_ZBUFFER | G_SHADE | G_SHADING_SMOOTH | G_CULL_BACK
    cmds += gfx_le(G_GEOMETRYMODE << 24, geom_flags)

    # 5. Set combiner to G_CC_SHADE (use vertex colors)
    #    Formula: (0-0)*0+SHADE = SHADE for color, same for alpha
    #    GCCc0w1(0,4,0,4)=0x20800, GCCc1w1(0,4,0,0,0,4)=0x104 → w1=0x00020904
    cmds += gfx_le(0xFC000000, 0x00020904)

    # 6. G_VTX_OTR_HASH — load all vertices in single batch (works for ≤32 verts)
    buf_idx = 0
    w0_vtx = (G_VTX_OTR_HASH << 24) | (vtx_count << 12) | ((buf_idx + vtx_count) << 1)
    cmds += gfx_le(w0_vtx, 0)
    hash_hi = (vtx_hash >> 32) & 0xFFFFFFFF
    hash_lo = vtx_hash & 0xFFFFFFFF
    cmds += gfx_le(hash_hi, hash_lo)

    # 7. Triangles — G_TRI2 for pairs, G_TRI1 for leftover (indexed mesh)
    for i in range(0, len(faces), 2):
        f1 = faces[i]
        if i + 1 < len(faces):
            f2 = faces[i + 1]
            cmds += gfx_le(
                (G_TRI2 << 24) | (f1[0] * 2 << 16) | (f1[1] * 2 << 8) | (f1[2] * 2),
                (f2[0] * 2 << 16) | (f2[1] * 2 << 8) | (f2[2] * 2)
            )
        else:
            cmds += gfx_le(
                (G_TRI1 << 24) | (f1[0] * 2 << 16) | (f1[1] * 2 << 8) | (f1[2] * 2),
                0
            )

    # 8. End display list
    cmds += gfx_le(G_ENDDL << 24, 0)

    # Build TLDO resource
    header = build_resource_header(RES_DISPLAY_LIST)
    body = bytearray()
    body += struct.pack('B', 4)  # ucode = F3DEX2
    # Align to 8 bytes
    while (len(body) + 0x40) % 8 != 0:
        body += b'\x00'
    body += cmds

    return header + bytes(body)


# ============================================================
# Multi-batch DL builder for large unindexed meshes (e.g. .obj imports)
# ============================================================
# F3DEX2's vertex buffer has 32 slots. For meshes with >32 vertices,
# we split into batches of ≤30 vertices = ≤10 triangles each.
# Assumes flat-shaded layout: triangle i uses verts (3i, 3i+1, 3i+2).

def build_unindexed_dl(vtx_path: str, n_triangles: int, no_cull: bool = False) -> bytes:
    """Build a TLDO display list for a flat-shaded unindexed mesh.

    Each triangle uses 3 unique sequential vertices (3i, 3i+1, 3i+2).
    Loads vertices in batches of 30 to stay under the F3DEX2 buffer limit.
    """
    vtx_hash = crc64(vtx_path)
    cmds = bytearray()

    # State setup (same as build_display_list)
    cmds += gfx_le(G_RDPPIPESYNC << 24, 0)
    cmds += gfx_le(
        (G_SETOTHERMODE_H << 24) | ((32 - 20 - 2) << 8) | (2 - 1),
        0
    )
    cmds += gfx_le(
        (G_SETOTHERMODE_L << 24) | ((32 - 3 - 29) << 8) | (29 - 1),
        RENDERMODE_AA_ZB_OPA
    )
    G_CULL_BACK = 0x00000400
    geom_flags = G_ZBUFFER | G_SHADE | G_SHADING_SMOOTH
    if not no_cull:
        geom_flags |= G_CULL_BACK
    cmds += gfx_le(G_GEOMETRYMODE << 24, geom_flags)
    cmds += gfx_le(0xFC000000, 0x00020904)  # G_CC_SHADE

    hash_hi = (vtx_hash >> 32) & 0xFFFFFFFF
    hash_lo = vtx_hash & 0xFFFFFFFF
    TRIS_PER_BATCH = 10  # 30 vertices per batch (≤32 buffer limit)

    tri_idx = 0
    while tri_idx < n_triangles:
        tris_this = min(TRIS_PER_BATCH, n_triangles - tri_idx)
        verts_this = tris_this * 3

        # G_VTX_OTR_HASH — load `verts_this` vertices into buffer slot 0
        w0_vtx = (G_VTX_OTR_HASH << 24) | (verts_this << 12) | (verts_this << 1)
        cmds += gfx_le(w0_vtx, (tri_idx * 3) * 16)  # byte offset into vtx data
        cmds += gfx_le(hash_hi, hash_lo)

        # Draw triangles using local slot indices (0..verts_this-1)
        for i in range(0, tris_this, 2):
            i0_a, i1_a, i2_a = i * 3, i * 3 + 1, i * 3 + 2
            if i + 1 < tris_this:
                i0_b, i1_b, i2_b = (i + 1) * 3, (i + 1) * 3 + 1, (i + 1) * 3 + 2
                cmds += gfx_le(
                    (G_TRI2 << 24) | (i0_a * 2 << 16) | (i1_a * 2 << 8) | (i2_a * 2),
                    (i0_b * 2 << 16) | (i1_b * 2 << 8) | (i2_b * 2)
                )
            else:
                cmds += gfx_le(
                    (G_TRI1 << 24) | (i0_a * 2 << 16) | (i1_a * 2 << 8) | (i2_a * 2),
                    0
                )

        tri_idx += tris_this

    cmds += gfx_le(G_ENDDL << 24, 0)

    # Wrap in TLDO resource
    header = build_resource_header(RES_DISPLAY_LIST)
    body = bytearray()
    body += struct.pack('B', 4)  # F3DEX2 ucode
    while (len(body) + 0x40) % 8 != 0:
        body += b'\x00'
    body += cmds
    return header + bytes(body)


# ============================================================
# Actor Library — OoT actors we can place in custom rooms
# ============================================================
# Source: OoT Decompilation actor table + objects table.
# Each entry: (actor_id, default_params, required_objects)
# `required_objects` are added to the Room's ObjectList automatically.

GAMEPLAY_KEEP = 0x0001  # always loaded, contains common assets

# Object IDs (from oot/include/z64object.h)
# Object IDs verified against soh/include/tables/object_table.h
OBJ_GAMEPLAY_KEEP = 0x0001
OBJ_GAMEPLAY_DANGEON_KEEP = 0x0003   # contains pots, switches, common dungeon items
OBJ_OKUTA = 0x0007                   # octorok
OBJ_DODONGO = 0x000C                 # baby dodongo
OBJ_FIREFLY = 0x000D                 # keese
OBJ_BOX = 0x000E                     # treasure chest (FIXED: was 0x000A)
OBJ_DEKUBABA = 0x0039                # deku baba (FIXED: was 0x0008)
OBJ_DEKUNUTS = 0x004A                # deku scrub (FIXED: was 0x000B)
OBJ_IK = 0x0106                      # iron knuckle
OBJ_KUSA = 0x012B                    # bushes
OBJ_TSUBO = 0x012C                   # pot (FIXED: was 0x0111 — that's the actor id)
OBJ_SKB = 0x0184                     # stalfos / skull kid base (FIXED: was 0x0009)

# En_Box (chest) param layout (verified vs ovl_En_Box/z_en_box.c):
#   bits 0-4  (0x001F): treasureFlag — save flag tracking which chest
#   bits 5-11 (0x0FE0): getItemId — what's inside (0x29=Heart Piece, etc.)
#   bits 12-15 (0xF000): chestType
#                0=ENBOX_TYPE_BIG_DEFAULT (boss-key style)
#                5=ENBOX_TYPE_SMALL       (normal small chest, default!)
ENBOX_TYPE_SMALL = 5
ENBOX_TYPE_BIG_DEFAULT = 0


# GetItem IDs verified against soh/include/z64item.h
GI_NONE = 0x00
GI_BOMBS_5 = 0x01
GI_BOMBCHUS_10 = 0x03
GI_BOW = 0x04
GI_BOOMERANG = 0x06
GI_HOOKSHOT = 0x08
GI_HEART_CONTAINER = 0x3D
GI_HEART_PIECE = 0x3E
GI_KEY_BOSS = 0x3F
GI_COMPASS = 0x40
GI_MAP = 0x41
GI_KEY_SMALL = 0x42
GI_RUPEE_GREEN = 0x4C
GI_RUPEE_BLUE = 0x4D
GI_RUPEE_RED = 0x4E
GI_RUPEE_PURPLE = 0x55
GI_RUPEE_GOLD = 0x56

# LiveGen custom items — registered additively in LiveGenItemRegistry.cpp.
# Picked from the unused 0x7E–0x7F range (after GI_TEXT_0 / before GI_MAX),
# which still fits in En_Box's 7-bit chest-params getItemId field.
GI_LIVEGEN_MARIO = 0x7E


def chest_params(chest_type: int = ENBOX_TYPE_BIG_DEFAULT,
                 item_id: int = GI_HEART_PIECE,
                 treasure_flag: int = 1) -> int:
    """Build En_Box params from semantic fields.

    Default: big chest (kneel-and-open animation), Heart Piece, flag 1.
    Use chest_type=ENBOX_TYPE_SMALL for small chests (rupees, keys, minor items).
    """
    return ((chest_type & 0xF) << 12) | ((item_id & 0x7F) << 5) | (treasure_flag & 0x1F)


ACTOR_LIBRARY = {
    # name             actor_id  default_params      required_objects
    "pot":            (0x0111,  0x0000,              [OBJ_TSUBO]),
    "chest":          (0x000A,  chest_params(),      [OBJ_BOX]),     # default: BIG with Heart Piece
    "keese":          (0x0013,  0x0002,              [OBJ_FIREFLY]),
    "tektite":        (0x001B,  0x0000,              []),
    "deku_baba":      (0x0055,  0x0000,              [OBJ_DEKUBABA]),
    "bush":           (0x0125,  0x0000,              [OBJ_KUSA]),
    "octorok":        (0x000F,  0x0000,              [OBJ_OKUTA]),
    "baby_dodongo":   (0x0012,  0x0000,              [OBJ_DODONGO]),
    "iron_knuckle":   (0x0113,  0x0000,              [OBJ_IK]),
}


def build_actor_entry(actor_name: str, x: int, y: int, z: int,
                      rot_y: int = 0, params: int = None) -> bytes:
    """Build a single 16-byte ActorEntry. Returns binary bytes.

    rot_y is treated as a 16-bit angle (0x0000=N, 0x4000=E, 0x8000=S, 0xC000=W).
    Values >= 0x8000 are stored as their signed-int16 equivalent.
    """
    if actor_name not in ACTOR_LIBRARY:
        raise ValueError(f"Unknown actor: {actor_name}. Known: {list(ACTOR_LIBRARY)}")
    actor_id, default_params, _ = ACTOR_LIBRARY[actor_name]
    p = params if params is not None else default_params
    # Wrap rot_y into signed int16 range
    if rot_y >= 0x8000:
        rot_y -= 0x10000
    # Format: uint16 id, int16 posX,Y,Z, int16 rotX,Y,Z, uint16 params
    return struct.pack('<HhhhhhhH', actor_id, x, y, z, 0, rot_y, 0, p)


def collect_required_objects(actors: list[str]) -> list[int]:
    """Given a list of actor names, return unique objects needed.

    Always includes gameplay_keep AND gameplay_dangeon_keep — the latter
    contains common dungeon assets like switches, the small key icon, etc.
    """
    required = {GAMEPLAY_KEEP, OBJ_GAMEPLAY_DANGEON_KEEP}
    for name in actors:
        if name in ACTOR_LIBRARY:
            for obj in ACTOR_LIBRARY[name][2]:
                required.add(obj)
    return sorted(required)


# ============================================================
# Room Header (MORO) — SetMesh Type 0
# ============================================================

def write_cmd_id(cmd_id: int) -> bytes:
    return struct.pack('<i', cmd_id)


def write_str(s: str) -> bytes:
    """SoH string format: uint32 length (incl. null) + chars + null."""
    if not s:
        return struct.pack('<I', 0)
    b = s.encode('utf-8') + b'\x00'
    return struct.pack('<I', len(b)) + b


def build_scene_header(room_path: str, collision_path: str, room_size: int = 0x100) -> bytes:
    """Build a minimal Scene that has 1 room, no transition actors, our collision."""
    header = build_resource_header(RES_ROOM)  # Scene uses same MORO type

    cmds = bytearray()
    n = 0

    # SoundSettings (ID=21): reverb=3, nature=0x13, seq=0x1C (same as Deku Tree)
    cmds += write_cmd_id(21)
    cmds += bytes([3, 0x13, 0x1C])
    n += 1

    # RoomList (ID=4): just 1 room
    cmds += write_cmd_id(4)
    cmds += struct.pack('<I', 1)  # numRooms = 1
    cmds += write_str(room_path)  # room 0 path
    cmds += struct.pack('<II', 0, max(room_size, 0x100))  # vromStart, vromEnd
    n += 1

    # SpawnList (ID=0): 1 spawn point at center of room
    cmds += write_cmd_id(0)
    cmds += struct.pack('<I', 1)  # numSpawns
    # ActorEntry: id=0x0000 (ACTOR_PLAYER), pos=(0,0,0), rot=(0,0,0), params=0x0FFF
    # ActorEntry: uint16 id, int16 posX,Y,Z, int16 rotX,Y,Z, uint16 params
    cmds += struct.pack('<HhhhhhhH', 0x0000, 0, 0, 0, 0, 0, 0, 0x0FFF)
    n += 1

    # EntranceList (ID=6): 1 entrance → spawn 0, room 0
    cmds += write_cmd_id(6)
    cmds += struct.pack('<I', 1)  # numEntrances
    cmds += struct.pack('<bb', 0, 0)  # spawn=0, room=0
    n += 1

    # CollisionHeader (ID=3): path to our custom collision
    cmds += write_cmd_id(3)
    cmds += write_str(collision_path)
    n += 1

    # SpecialObjects (ID=7): elfMsg=0, globalObject=1 (gameplay_keep)
    cmds += write_cmd_id(7)
    cmds += bytes([0]) + struct.pack('<h', 1)
    n += 1

    # SkyboxSettings (ID=17): unk=0, skyboxId=0, weather=0, indoors=1 (4 bytes!)
    cmds += write_cmd_id(17)
    cmds += bytes([0, 0, 0, 1])
    n += 1

    # LightSettings (ID=15): 1 simple light setting
    cmds += write_cmd_id(15)
    cmds += struct.pack('<I', 1)  # count
    # 22 bytes per light setting: ambient RGB, light1 dir+color, light2 dir+color, fog color+near+far
    cmds += bytes([
        80, 80, 90,       # ambient RGB
        50, 50, 50,       # light1 dir
        180, 180, 200,    # light1 color
        -50 & 0xFF, -50 & 0xFF, -50 & 0xFF,  # light2 dir
        60, 60, 80,       # light2 color
        100, 90, 80,      # fog color
        0x03, 0xE0,       # fog near (992)
        0x10, 0x00,       # fog far (4096)
    ])
    n += 1

    # EndMarker (ID=20)
    cmds += write_cmd_id(20)
    n += 1

    return header + struct.pack('<I', n) + bytes(cmds)


def build_room_header(dl_path: str, actors: list = None,
                      extra_dl_paths: list[str] = None) -> bytes:
    """Build room header with SetMesh Type 0, ObjectList, and ActorList.

    `actors` is a list of dicts: {"name": str, "x": int, "y": int, "z": int,
                                   "rot_y": int (optional), "params": int (optional)}
    `extra_dl_paths` adds additional polygon DLs (rendered alongside main `dl_path`).
    Required objects are derived automatically from actor names.
    """
    actors = actors or []
    extra_dl_paths = extra_dl_paths or []
    actor_names = [a["name"] for a in actors]
    object_ids = collect_required_objects(actor_names)

    all_dls = [dl_path] + extra_dl_paths

    header = build_resource_header(RES_ROOM)

    cmds = bytearray()
    n = 0

    # EchoSettings (ID=22)
    cmds += write_cmd_id(22)
    cmds += bytes([0x07])
    n += 1

    # RoomBehavior (ID=8): int8 + int32 = 5 bytes
    cmds += write_cmd_id(8)
    cmds += struct.pack('<bI', 1, 0)
    n += 1

    # SkyboxModifier (ID=18): indoor
    cmds += write_cmd_id(18)
    cmds += bytes([1, 1])
    n += 1

    # TimeSettings (ID=16): frozen time
    cmds += write_cmd_id(16)
    cmds += bytes([0xFF, 0xFF, 0])
    n += 1

    # SetMesh (ID=10): Type 0, N polygons (one per DL path)
    cmds += write_cmd_id(10)
    cmds += struct.pack('b', 0)              # data (unused)
    cmds += struct.pack('b', 0)              # meshType = 0
    cmds += struct.pack('b', len(all_dls))   # polyNum
    for path in all_dls:
        cmds += struct.pack('b', 0)          # polyType (unused)
        cmds += write_str(path)              # opaque DL
        cmds += write_str("")                # no translucent DL
    n += 1

    # ObjectList (ID=11): all required objects
    cmds += write_cmd_id(11)
    cmds += struct.pack('<I', len(object_ids))
    for obj_id in object_ids:
        cmds += struct.pack('<H', obj_id)
    n += 1

    # ActorList (ID=1)
    cmds += write_cmd_id(1)
    cmds += struct.pack('<I', len(actors))
    for a in actors:
        cmds += build_actor_entry(
            a["name"], a["x"], a["y"], a["z"],
            rot_y=a.get("rot_y", 0),
            params=a.get("params")
        )
    n += 1

    # EndMarker (ID=20)
    cmds += write_cmd_id(20)
    n += 1

    return header + struct.pack('<I', n) + bytes(cmds)


# ============================================================
# Collision (LOCO) — simple flat floor
# ============================================================

def build_collision(w=600, h=600, d=600) -> bytes:
    """Complete box collision: floor + 4 walls + ceiling.

    Box matches the visual mesh dimensions (w/h/d match build_box_vertices).
    Floor at Y=-100 so Link can spawn at Y=0 and land softly.
    """
    header = build_resource_header(RES_COLLISION)

    floor_y = -100
    ceiling_y = floor_y + h

    body = bytearray()
    # Bounding box
    body += struct.pack('<hhh', -w, floor_y, -d)        # min
    body += struct.pack('<hhh', w, ceiling_y, d)        # max

    # 8 vertices: 4 floor corners + 4 ceiling corners
    # Floor (Y=floor_y):    0=(-w,-d), 1=(w,-d), 2=(w,d), 3=(-w,d)
    # Ceiling (Y=ceiling_y): 4=(-w,-d), 5=(w,-d), 6=(w,d), 7=(-w,d)
    verts = [
        (-w, floor_y,   -d),  # 0
        ( w, floor_y,   -d),  # 1
        ( w, floor_y,    d),  # 2
        (-w, floor_y,    d),  # 3
        (-w, ceiling_y, -d),  # 4
        ( w, ceiling_y, -d),  # 5
        ( w, ceiling_y,  d),  # 6
        (-w, ceiling_y,  d),  # 7
    ]
    body += struct.pack('<i', len(verts))
    for v in verts:
        body += struct.pack('<hhh', *v)

    # Polygons: 12 triangles (2 floor + 2 ceiling + 2 per wall × 4)
    # Format: (surface_type, vIA, vIB, vIC, normalX, normalY, normalZ, dist)
    # All normals as int16 with 0x7FFF = 1.0 in fixed point.
    NX_POS = 0x7FFF; NX_NEG = 0x8001  # ±1 in X
    NY_POS = 0x7FFF; NY_NEG = 0x8001  # ±1 in Y
    NZ_POS = 0x7FFF; NZ_NEG = 0x8001  # ±1 in Z

    # dist = -dot(normal, vertex_on_plane). For normal (0,1,0) and floor at Y=-100:
    # dist = -(-100) = 100 (the formula is normal · point + dist = 0)
    polys = [
        # FLOOR — normal +Y. CCW from above: 0,2,1 and 0,3,2
        (0, 0, 2, 1, 0, NY_POS, 0, -floor_y),
        (0, 0, 3, 2, 0, NY_POS, 0, -floor_y),

        # CEILING — normal -Y. CCW from below: 4,5,6 and 4,6,7
        (0, 4, 5, 6, 0, NY_NEG, 0, ceiling_y),
        (0, 4, 6, 7, 0, NY_NEG, 0, ceiling_y),

        # NORTH WALL Z=-d, normal +Z (inward). Floor verts 0,1; Ceiling 4,5
        # CCW from inside (south side, looking north): 0,1,5 and 0,5,4
        (0, 0, 1, 5, 0, 0, NZ_POS, d),
        (0, 0, 5, 4, 0, 0, NZ_POS, d),

        # SOUTH WALL Z=+d, normal -Z (inward). Floor 2,3; Ceiling 6,7
        (0, 2, 3, 7, 0, 0, NZ_NEG, d),
        (0, 2, 7, 6, 0, 0, NZ_NEG, d),

        # WEST WALL X=-w, normal +X (inward). Floor 0,3; Ceiling 4,7
        (0, 3, 0, 4, NX_POS, 0, 0, w),
        (0, 3, 4, 7, NX_POS, 0, 0, w),

        # EAST WALL X=+w, normal -X (inward). Floor 1,2; Ceiling 5,6
        (0, 1, 2, 6, NX_NEG, 0, 0, w),
        (0, 1, 6, 5, NX_NEG, 0, 0, w),
    ]
    body += struct.pack('<I', len(polys))
    for surf_type, a, b, c, nx, ny, nz, dist in polys:
        body += struct.pack('<HHHHHHHH',
                            surf_type, a, b, c,
                            nx & 0xFFFF, ny & 0xFFFF, nz & 0xFFFF,
                            dist & 0xFFFF)

    # Surface types
    body += struct.pack('<I', 1)
    body += struct.pack('<II', 0, 0)

    # Camera data (1 entry — Camera_Update crashes on NULL)
    body += struct.pack('<I', 1)
    body += struct.pack('<Hh', 0, 0)
    body += struct.pack('<i', 0)
    body += struct.pack('<i', 0)

    # Water boxes
    body += struct.pack('<i', 0)

    return header + bytes(body)


# ============================================================
# Main — build the .o2r
# ============================================================

def main():
    from obj_to_dl import parse_obj
    from mesh_to_dl import load_mesh

    TARGET = "scenes/nonmq/ydan_scene"
    VTX_PATH = f"{TARGET}/squadala_box_Vtx"
    DL_PATH = f"{TARGET}/squadala_box_DL"
    ROOM_PATH = f"{TARGET}/ydan_room_0"
    COLLISION_PATH = f"{TARGET}/ydan_sceneCollisionHeader_00B610"

    # Pipeline assets live under tooling/assets/3d/. _raw_data/ is the user's
    # drop-zone (raw deliveries) and must never be referenced from build code.
    ASSETS_3D = Path(__file__).parent / "assets" / "3d"

    # Mario stays in the .o2r as the chest's custom GetItem visual (rendered by
    # Player_DrawGetItemImpl via our LiveGen_DrawMarioItem drawFunc).
    MARIO_OBJ = ASSETS_3D / "super_mario" / "model.obj"
    MARIO_VTX_PATH = f"{TARGET}/squadala_mario_Vtx"
    MARIO_DL_PATH = f"{TARGET}/squadala_mario_DL"

    # Pizza is the spinning showcase decoration above the chest. GLB import via
    # trimesh; tilted ~30° from horizontal so it's visibly not flat as it rotates.
    PIZZA_GLB = ASSETS_3D / "pizza.glb"
    PIZZA_VTX_PATH = f"{TARGET}/squadala_pizza_Vtx"
    PIZZA_DL_PATH = f"{TARGET}/squadala_pizza_DL"

    vertices, colors = build_box_vertices()
    faces = build_box_faces()

    # Test actors: pots, chest with Heart Piece, deku babas (piranha plants)
    actors = [
        {"name": "pot", "x": -400, "y": -100, "z": -400},
        {"name": "pot", "x":  400, "y": -100, "z": -400},
        {"name": "pot", "x":  400, "y": -100, "z":  400},
        {"name": "pot", "x": -400, "y": -100, "z":  400},
        {"name": "chest", "x": 0, "y": -100, "z": 0, "rot_y": 0x8000,
         "params": chest_params(item_id=GI_LIVEGEN_MARIO, treasure_flag=1)},
        # Deku Babas — bite if Link gets close, but stay rooted
        {"name": "deku_baba", "x": -300, "y": -100, "z": -100},
        {"name": "deku_baba", "x":  300, "y": -100, "z": -100},
        {"name": "deku_baba", "x":    0, "y": -100, "z": -350},
    ]

    vtx_resource = build_vtx_resource(vertices, colors)
    dl_resource = build_display_list(VTX_PATH, len(vertices), faces)

    # Build Mario — scale=200 (~250 units high), origin centered for rotation.
    # Mario is NOT a standalone scene decoration anymore; the chest's custom
    # GetItem drawFunc (LiveGen_DrawMarioItem in soh) renders this DL above
    # Link's head when the chest is opened. Y-centering keeps the rotation
    # axis clean (Mario raw center Y ≈ -0.175 → scaled center -35 → offset +35).
    mario = parse_obj(MARIO_OBJ, scale=200.0, y_offset=35.0, rotation_y_degrees=0.0)
    mario_verts = [(v[0], v[1], v[2]) for v in mario.vertices]
    mario_colors = [(v[3], v[4], v[5], v[6]) for v in mario.vertices]
    mario_vtx = build_vtx_resource(mario_verts, mario_colors)
    mario_dl = build_unindexed_dl(MARIO_VTX_PATH, len(mario.triangles))
    print(f"Mario: {len(mario.vertices)} verts, {len(mario.triangles)} tris → "
          f"VTX {len(mario_vtx)}B, DL {len(mario_dl)}B")

    # Build Pizza — trimesh-based GLB import. Native size ~0.034 wide → scale
    # 14000 gives ~480 units (down 30% from the original 680). Tilt -60° around
    # X so the disc is visibly not flat as it spins, with the top side facing
    # up-forward (positive 60° put the top side facing down-forward).
    pizza = load_mesh(
        PIZZA_GLB,
        scale=14000.0,
        y_offset=0.0,
        rotation_deg=(-60.0, 0.0, 0.0),
    )
    pizza_verts = [(v[0], v[1], v[2]) for v in pizza.vertices]
    pizza_colors = [(v[3], v[4], v[5], v[6]) for v in pizza.vertices]
    pizza_vtx = build_vtx_resource(pizza_verts, pizza_colors)
    pizza_dl = build_unindexed_dl(PIZZA_VTX_PATH, len(pizza.triangles))
    print(f"Pizza: {len(pizza.vertices)} verts, {len(pizza.triangles)} tris → "
          f"VTX {len(pizza_vtx)}B, DL {len(pizza_dl)}B")

    # Neither Mario nor Pizza are in the Room SetMesh — they're drawn by C++
    # hooks that resolve __OTR__ paths and apply transforms at draw time.
    room_header = build_room_header(DL_PATH, actors=actors)
    collision = build_collision()
    scene_header = build_scene_header(ROOM_PATH, COLLISION_PATH, len(room_header))

    output = Path.home() / "workspace/SoH/soh-source/build-cmake/soh/debug_rooms/zzz_squadala_dungeon.o2r"
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(output), 'w', zipfile.ZIP_STORED) as oz:
        oz.writestr(VTX_PATH, vtx_resource)
        oz.writestr(MARIO_VTX_PATH, mario_vtx)
        oz.writestr(MARIO_DL_PATH, mario_dl)
        oz.writestr(PIZZA_VTX_PATH, pizza_vtx)
        oz.writestr(PIZZA_DL_PATH, pizza_dl)
        oz.writestr(DL_PATH, dl_resource)
        oz.writestr(ROOM_PATH, room_header)
        oz.writestr(COLLISION_PATH, collision)
        oz.writestr(f"{TARGET}/ydan_scene", scene_header)

        print(f"Scene: {len(scene_header)}B | Room: {len(room_header)}B | DL: {len(dl_resource)}B")
        print(f"VTX: {len(vtx_resource)}B | Collision: {len(collision)}B")

    print(f"Output: {output} ({output.stat().st_size} bytes)")
    print("Complete override: Scene + Room + DL + VTX + Collision")


if __name__ == "__main__":
    main()
