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

FACE_NAMES = ["floor", "ceiling", "north", "south", "west", "east"]


def _door_wall_panels(face: str, w: int, d: int, floor_y: int, ceiling_y: int,
                       door: dict) -> list[list[tuple[int, int, int]]]:
    """Three quads that replace the full east or west wall, leaving a centred
    door-shaped hole at z=0.

    `door` keys: half_width (z extent of the hole / 2), height (y extent of the
    hole, measured from floor_y).

    Each returned quad is a list of 4 vertices in the same CCW winding the
    full wall would use, so the inward-facing normal stays consistent.
    """
    half = door["half_width"]
    door_top = floor_y + door["height"]
    panels: list[list[tuple[int, int, int]]] = []
    # Pull the door panels 1 unit toward the room's interior so that the
    # adjacent room's panels don't share the exact same plane → no Z-fight
    # when both rooms render simultaneously during the room transition.
    SHRINK = 1

    if face == "east":
        x = w - SHRINK
        # Original east winding: (x, y_low, z_back) → (x, y_low, z_front) →
        #                        (x, y_high, z_front) → (x, y_high, z_back)
        # Above panel (top strip across the full width).
        panels.append([
            (x, door_top, -d), (x, door_top,  d),
            (x, ceiling_y,  d), (x, ceiling_y, -d),
        ])
        # Flank towards +Z (between hole and z=+d).
        panels.append([
            (x, floor_y, half), (x, floor_y, d),
            (x, door_top, d), (x, door_top, half),
        ])
        # Flank towards -Z (between z=-d and hole).
        panels.append([
            (x, floor_y, -d), (x, floor_y, -half),
            (x, door_top, -half), (x, door_top, -d),
        ])
    elif face == "west":
        x = -w + SHRINK
        # Original west winding: (x, y_low, z_front) → (x, y_low, z_back) →
        #                        (x, y_high, z_back) → (x, y_high, z_front)
        panels.append([
            (x, door_top,  d), (x, door_top, -d),
            (x, ceiling_y, -d), (x, ceiling_y,  d),
        ])
        panels.append([
            (x, floor_y, d), (x, floor_y, half),
            (x, door_top, half), (x, door_top, d),
        ])
        panels.append([
            (x, floor_y, -half), (x, floor_y, -d),
            (x, door_top, -d), (x, door_top, -half),
        ])
    else:
        raise ValueError(f"door panels only supported for east/west walls, got {face!r}")

    return panels


def build_box_vertices(w=600, h=600, d=1500, offset=(0, 0, 0), skip_walls=None,
                        doors=None):
    """Vertices for a box room — 4 per face, each face has its own color.

    Player is INSIDE the box. Normals point inward (CCW winding from inside view).
    With G_CULL_BACK enabled, only inward-facing triangles render.

    Args:
        w, h, d: half-extents in X, Y, Z. Box spans (-w..w, floor..floor+h, -d..d).
        offset: (ox, oy, oz) world translation applied to every vertex.
        skip_walls: optional set of face names to omit (e.g. {"east"} for an
                    open shared boundary in multi-room layouts).
        doors: optional dict {face: {"half_width": int, "height": int}} —
                replaces the named east/west wall with three panel quads
                (above + two flanks) leaving a centred door-shaped hole.
                Takes precedence over skip_walls for the same face.

    Returns:
        (verts, colors, n_faces) — n_faces is the number of emitted face quads
        (used by build_box_faces to know how many tri-pairs to generate).
    """
    skip_walls = skip_walls or set()
    doors = doors or {}
    ox, oy, oz = offset
    floor_y = -100 + oy
    ceiling_y = floor_y + h

    # Local-space face quads (CCW from inside) and their colors.
    face_quads = {
        "floor":   [(-w, floor_y,  d), ( w, floor_y,  d), ( w, floor_y, -d), (-w, floor_y, -d)],
        "ceiling": [(-w, ceiling_y, -d), ( w, ceiling_y, -d), ( w, ceiling_y,  d), (-w, ceiling_y,  d)],
        "north":   [(-w, floor_y, -d), ( w, floor_y, -d), ( w, ceiling_y, -d), (-w, ceiling_y, -d)],
        "south":   [( w, floor_y,  d), (-w, floor_y,  d), (-w, ceiling_y,  d), ( w, ceiling_y,  d)],
        "west":    [(-w, floor_y,  d), (-w, floor_y, -d), (-w, ceiling_y, -d), (-w, ceiling_y,  d)],
        "east":    [( w, floor_y, -d), ( w, floor_y,  d), ( w, ceiling_y,  d), ( w, ceiling_y, -d)],
    }
    palette = {
        "floor":   (60, 180, 60, 255),
        "ceiling": (180, 60, 60, 255),
        "north":   (60, 100, 220, 255),
        "south":   (220, 200, 60, 255),
        "west":    (60, 200, 200, 255),
        "east":    (200, 60, 200, 255),
    }

    verts: list[tuple[int, int, int]] = []
    colors: list[tuple[int, int, int, int]] = []
    n_faces = 0
    for name in FACE_NAMES:
        col = palette[name]

        # Door panels (3 quads with a centred hole) replace the full wall when
        # the face is in `doors`. This wins over skip_walls so callers can pass
        # both — the door spec is more specific.
        if name in doors and name in ("east", "west"):
            for panel in _door_wall_panels(name, w, d, floor_y, ceiling_y, doors[name]):
                for vx, vy, vz in panel:
                    verts.append((vx + ox, vy, vz + oz))
                    colors.append(col)
                n_faces += 1
            continue

        if name in skip_walls:
            continue

        for vx, vy, vz in face_quads[name]:
            verts.append((vx + ox, vy, vz + oz))
            colors.append(col)
        n_faces += 1

    return verts, colors, n_faces


def build_box_faces(n_faces: int = 6):
    """2 triangles per face quad. Quad winding (v0, v1, v2, v3) is CCW from inside.

    Splits each quad into (v0, v1, v2) and (v0, v2, v3).
    """
    faces = []
    for face_idx in range(n_faces):
        base = face_idx * 4
        v0, v1, v2, v3 = base, base + 1, base + 2, base + 3
        faces.append((v0, v1, v2))
        faces.append((v0, v2, v3))
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
    Splits the load into batches of ≤64 verts (F3DEX2's MAX_VERTICES) so
    meshes larger than the vertex buffer still render correctly. Assumes a
    QUAD-ALIGNED face layout: faces[2q] and faces[2q+1] are the two tris of
    quad q, which uses sequential verts (4q, 4q+1, 4q+2, 4q+3) — same shape
    build_box_faces produces. Each batch loads up to 16 quads (64 verts).
    """
    vtx_hash = crc64(vtx_path)

    cmds = bytearray()

    # 1. Pipeline sync
    cmds += gfx_le(G_RDPPIPESYNC << 24, 0)

    # 2. Set cycle type to 1-cycle
    cmds += gfx_le(
        (G_SETOTHERMODE_H << 24) | ((32 - 20 - 2) << 8) | (2 - 1),
        0  # G_CYC_1CYCLE = 0
    )

    # 3. Set render mode: AA + Z-buffer + opaque surface
    cmds += gfx_le(
        (G_SETOTHERMODE_L << 24) | ((32 - 3 - 29) << 8) | (29 - 1),
        RENDERMODE_AA_ZB_OPA
    )

    # 4. Geometry mode: Z-buffer + smooth shaded vertex colors + cull back
    G_CULL_BACK = 0x00000400
    geom_flags = G_ZBUFFER | G_SHADE | G_SHADING_SMOOTH | G_CULL_BACK
    cmds += gfx_le(G_GEOMETRYMODE << 24, geom_flags)

    # 5. Combiner: G_CC_SHADE (use vertex colors only)
    cmds += gfx_le(0xFC000000, 0x00020904)

    hash_hi = (vtx_hash >> 32) & 0xFFFFFFFF
    hash_lo = vtx_hash & 0xFFFFFFFF

    # 6. Batched vertex loads + triangles. Each batch:
    #   - G_VTX_OTR_HASH with w1 = byte offset into the resource (each vert
    #     is 16 bytes), so subsequent batches load later chunks of the same
    #     VTX resource into buffer slots 0..n. The engine masks `end` to
    #     7 bits and computes dst=end-n, so n must stay ≤ MAX_VERTICES=64
    #     OR end would wrap and write garbage memory.
    #   - TRI1/TRI2 commands reference BUFFER-LOCAL indices (0..n-1) which
    #     map to resource verts (vert_start..vert_start+n-1).
    n_quads = len(faces) // 2
    QUADS_PER_BATCH = 16  # 64 verts ÷ 4 verts/quad
    for batch_start_q in range(0, max(n_quads, 1), QUADS_PER_BATCH):
        batch_end_q = min(batch_start_q + QUADS_PER_BATCH, n_quads)
        quads_in_batch = batch_end_q - batch_start_q
        if quads_in_batch == 0:
            break
        verts_in_batch = quads_in_batch * 4
        vert_start = batch_start_q * 4
        byte_offset = vert_start * 16   # F3DVtx is 16 bytes

        w0_vtx = (G_VTX_OTR_HASH << 24) | (verts_in_batch << 12) | (verts_in_batch << 1)
        cmds += gfx_le(w0_vtx, byte_offset)
        cmds += gfx_le(hash_hi, hash_lo)

        # Emit two tris per quad (TRI2), remapping global vert indices into
        # buffer-local indices (0..63) by subtracting vert_start.
        for q_local in range(quads_in_batch):
            q_global = batch_start_q + q_local
            t1 = faces[q_global * 2]
            t2 = faces[q_global * 2 + 1]
            l1 = (t1[0] - vert_start, t1[1] - vert_start, t1[2] - vert_start)
            l2 = (t2[0] - vert_start, t2[1] - vert_start, t2[2] - vert_start)
            cmds += gfx_le(
                (G_TRI2 << 24) | (l1[0] * 2 << 16) | (l1[1] * 2 << 8) | (l1[2] * 2),
                (l2[0] * 2 << 16) | (l2[1] * 2 << 8) | (l2[2] * 2)
            )

    # 7. End display list
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
GI_LIVEGEN_MARIO   = 0x7E
GI_LIVEGEN_SONIC   = 0x7F
# Chest params encode the item ID in 7 bits (0–0x7F), so we can't put new
# items at 0x80+ without losing the high bit. The Hydrant takes over 0x7D
# (vanilla GI_TEXT_0 — a "show text 0, no model" placeholder we don't use
# anywhere in the Squadala dungeon).
GI_LIVEGEN_HYDRANT = 0x7D

# Object IDs needed by transition actors with their own visual mesh.
OBJECT_GAMEPLAY_FIELD_KEEP = 0x0002


def chest_params(chest_type: int = ENBOX_TYPE_BIG_DEFAULT,
                 item_id: int = GI_HEART_PIECE,
                 treasure_flag: int = 1) -> int:
    """Build En_Box params from semantic fields.

    Default: big chest (kneel-and-open animation), Heart Piece, flag 1.
    Use chest_type=ENBOX_TYPE_SMALL for small chests (rupees, keys, minor items).
    """
    return ((chest_type & 0xF) << 12) | ((item_id & 0x7F) << 5) | (treasure_flag & 0x1F)


# Item00 drop variants (En_Item00 params low byte) — see soh/include/z64actor.h::Item00Type
# These are the items that can lie around on the floor in OoT.
ITEM00_RUPEE_GREEN     = 0x00
ITEM00_RUPEE_BLUE      = 0x01
ITEM00_RUPEE_RED       = 0x02
ITEM00_HEART           = 0x03
ITEM00_BOMBS_A         = 0x04
ITEM00_ARROWS_SINGLE   = 0x05
ITEM00_HEART_PIECE     = 0x06
ITEM00_HEART_CONTAINER = 0x07
ITEM00_ARROWS_SMALL    = 0x08
ITEM00_ARROWS_MEDIUM   = 0x09
ITEM00_ARROWS_LARGE    = 0x0A
ITEM00_BOMBS_B         = 0x0B
ITEM00_NUTS            = 0x0C
ITEM00_STICK           = 0x0D
ITEM00_MAGIC_LARGE     = 0x0E
ITEM00_MAGIC_SMALL     = 0x0F
ITEM00_SEEDS           = 0x10
ITEM00_SMALL_KEY       = 0x11
ITEM00_FLEXIBLE        = 0x12  # random based on enemy that drops it — unstable for static placement
ITEM00_RUPEE_ORANGE    = 0x13
ITEM00_RUPEE_PURPLE    = 0x14
ITEM00_SHIELD_DEKU     = 0x15
ITEM00_SHIELD_HYLIAN   = 0x16
ITEM00_TUNIC_ZORA      = 0x17
ITEM00_TUNIC_GORON     = 0x18
ITEM00_BOMBS_SPECIAL   = 0x19
ITEM00_BOMBCHU         = 0x1A

# Object IDs used by extra actor mappings (sourced from scene_builder.py, not all
# verified against object_table.h yet — uncertainty marked with "TODO: verify").
OBJ_ST_GOLD_SKULLTULA = 0x0024  # OBJECT_ST
OBJ_DODONGO_LIZALFOS   = 0x0054  # OBJECT_DNS / lizalfos? TODO: verify
OBJ_TITE              = 0x0016  # OBJECT_TITE (tektite/wolfos placeholder?)
OBJ_FZ                = 0x0157  # OBJECT_FZ (freezard)
OBJ_RD                = 0x0098  # OBJECT_RD (gibdo/redead)
OBJ_WALLMASTER        = 0x000B  # OBJECT_WALLMASTER (also floormaster)
OBJ_RR                = 0x00D4  # OBJECT_RR (like_like)
OBJ_BB                = 0x005D  # OBJECT_BB (bubble)
OBJ_AHG               = 0x0107  # OBJECT_AHG (torch_slug? TODO: verify)


ACTOR_LIBRARY = {
    # name              actor_id  default_params  required_objects
    # — Verified in build_box_room work —
    "pot":             (0x0111,  0x0000,          [OBJ_TSUBO]),
    "chest":           (0x000A,  chest_params(),  [OBJ_BOX]),     # default: BIG with Heart Piece
    "keese":           (0x0013,  0x0002,          [OBJ_FIREFLY]),
    "tektite":         (0x001B,  0x0000,          [OBJ_TITE]),
    "deku_baba":       (0x0055,  0x0000,          [OBJ_DEKUBABA]),
    "bush":            (0x0125,  0x0000,          [OBJ_KUSA]),
    "octorok":         (0x000F,  0x0000,          [OBJ_OKUTA]),
    "baby_dodongo":    (0x0012,  0x0000,          [OBJ_DODONGO]),
    "iron_knuckle":    (0x0113,  0x0000,          [OBJ_IK]),
    # — Item00 drops (En_Item00, ACTOR id 0x0015) — uses gameplay_keep, no extra obj —
    "item00":          (0x0015,  0x0000,          []),
    # — Schema-driven enemy mappings ported from scene_builder.py. Object IDs
    #   are best-effort from the OoT decomp; uncertain ones flagged inline.
    "skulltula":       (0x0095,  0x0000,          [OBJ_ST_GOLD_SKULLTULA]),
    "stalfos":         (0x0002,  0x0000,          []),               # gameplay_keep
    "lizalfos":        (0x0031,  0x0000,          [OBJ_DODONGO_LIZALFOS]),
    "wolfos":          (0x001B,  0x0000,          [OBJ_TITE]),       # TODO: real wolfos id
    "white_wolfos":    (0x001B,  0x0001,          [OBJ_TITE]),       # TODO: real wolfos id
    "freezard":        (0x011A,  0x0000,          [OBJ_FZ]),
    "dinolfos":        (0x0031,  0x0002,          [OBJ_DODONGO_LIZALFOS]),
    "gibdo":           (0x0090,  0x0000,          [OBJ_RD]),
    "redead":          (0x0090,  0x7F01,          [OBJ_RD]),
    "poe":             (0x000D,  0x0000,          [OBJ_FIREFLY]),    # TODO: verify obj
    "floormaster":     (0x008E,  0x0000,          [OBJ_WALLMASTER]),
    "wallmaster":      (0x0011,  0x0000,          [OBJ_WALLMASTER]),
    "armos":           (0x0054,  0x0000,          []),               # En_Am — was mislabelled as 0x0023 (En_Holl) in earlier code
    # — Transition actors. These belong in the scene-level TransitionActorList,
    #   never in an actor-list — but registering them here gives them a single
    #   source of actor IDs / object requirements like everything else. —
    "en_holl":         (0x0023,  0x0000,          []),               # invisible plane trigger between rooms
    "en_door":         (0x0009,  0x0000,          [OBJECT_GAMEPLAY_FIELD_KEEP]),  # visible wood door
    "beamos":          (0x0087,  0x0000,          []),               # gameplay_dangeon_keep
    "like_like":       (0x00DD,  0x0000,          [OBJ_RR]),
    "bubble":          (0x0069,  0x0000,          [OBJ_BB]),
    "torch_slug":      (0x0037,  0x0000,          [OBJ_AHG]),
    "dodongo":         (0x0012,  0x0000,          [OBJ_DODONGO]),
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


def build_transition_actor_entry(actor_name: str, front_room: int, back_room: int,
                                  x: int, y: int, z: int,
                                  rot_y: int = 0, params: int = 0,
                                  front_fx: int = 0, back_fx: int = 0) -> bytes:
    """Build a single 16-byte TransitionActorEntry.

    Format: <bbbbhhhhhH> — front_room, front_fx, back_room, back_fx,
                            actor_id, posX, posY, posZ, rotY, params.
    Used by Scene's TransitionActorList (cmd 0x0E). En_Holl/En_Door belong
    here, not in a per-room ActorList.
    """
    if actor_name not in ACTOR_LIBRARY:
        raise ValueError(f"Unknown transition actor: {actor_name}")
    actor_id, _, _ = ACTOR_LIBRARY[actor_name]
    if rot_y >= 0x8000:
        rot_y -= 0x10000
    return struct.pack('<bbbbhhhhhH',
                       front_room, front_fx, back_room, back_fx,
                       actor_id, x, y, z, rot_y, params)


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


def build_scene_header(room_path, collision_path: str, room_size: int = 0x100,
                       transition_actors: list[dict] | None = None,
                       spawn_pos: tuple[int, int, int] = (0, 0, 0),
                       spawn_rot_y: int = 0) -> bytes:
    """Build a Scene that references one or more rooms.

    Args:
        room_path: a single string (single-room scene) OR a list of strings
                   (multi-room scene). RoomList emits one entry per path.
        transition_actors: optional list of dicts forwarded to
                            build_transition_actor_entry — emitted as the
                            scene's TransitionActorList (cmd 0x0E).
        spawn_pos: (x, y, z) world position for Link's SpawnList entry.
        spawn_rot_y: 16-bit Y rotation Link faces on spawn.
    """
    header = build_resource_header(RES_ROOM)  # Scene uses same MORO type

    rooms = [room_path] if isinstance(room_path, str) else list(room_path)
    if not rooms:
        raise ValueError("scene must reference at least one room")

    cmds = bytearray()
    n = 0

    # Command order mirrors vanilla Deku Tree (scene 0x0). The order itself
    # doesn't matter to most commands, but EntranceList (6) MUST come before
    # SpawnList (0) — Scene_CommandSpawnList reads
    # play->setupEntranceList[curSpawn] which is populated by the EntranceList
    # command. Including MiscSettings (25) and ExitList (19) to match what
    # vanilla scenes provide; without MiscSettings the camera initialises with
    # garbage cameraMovement, which can leave the world unrenderable.

    # SoundSettings (ID=21): reverb=3, nature=0x13, seq=0x1C (same as Deku Tree)
    cmds += write_cmd_id(21)
    cmds += bytes([3, 0x13, 0x1C])
    n += 1

    # RoomList (ID=4): one RomFile entry per room
    cmds += write_cmd_id(4)
    cmds += struct.pack('<I', len(rooms))
    for path in rooms:
        cmds += write_str(path)
        cmds += struct.pack('<II', 0, max(room_size, 0x100))  # vromStart, vromEnd
    n += 1

    # TransitionActorList (ID=14): one TransitionActorEntry per transition
    # (En_Holl, En_Door, …). Vanilla scenes always emit this command, and
    # SoH's Scene_CommandTransitionActorList writes play->transiActorCtx
    # from it — so even an empty list keeps the engine in a known state.
    transition_actors = transition_actors or []
    cmds += write_cmd_id(14)
    cmds += struct.pack('<I', len(transition_actors))
    for ta in transition_actors:
        cmds += build_transition_actor_entry(**ta)
    n += 1

    # MiscSettings (ID=25): cameraMovement + worldMapArea (matches vanilla)
    cmds += write_cmd_id(25)
    cmds += struct.pack('<bI', 0, 0)
    n += 1

    # CollisionHeader (ID=3): path to our custom collision
    cmds += write_cmd_id(3)
    cmds += write_str(collision_path)
    n += 1

    # EntranceList (ID=6) — must come before SpawnList. Provide N identical
    # slots so any vanilla curSpawn (>0) resolves to {spawn=0, room=0}.
    ENTRANCE_LIST_SLOTS = 16
    cmds += write_cmd_id(6)
    cmds += struct.pack('<I', ENTRANCE_LIST_SLOTS)
    for _ in range(ENTRANCE_LIST_SLOTS):
        cmds += struct.pack('<bb', 0, 0)  # spawn=0, room=0
    n += 1

    # SpecialFiles (ID=7): elfMsg=0, globalObject=1 (gameplay_keep)
    cmds += write_cmd_id(7)
    cmds += bytes([0]) + struct.pack('<h', 1)
    n += 1

    # SpawnList (ID=0): 1 spawn point at room centre.
    cmds += write_cmd_id(0)
    cmds += struct.pack('<I', 1)  # numSpawns
    sx, sy, sz = spawn_pos
    sry = spawn_rot_y - 0x10000 if spawn_rot_y >= 0x8000 else spawn_rot_y
    cmds += struct.pack('<HhhhhhhH', 0x0000, sx, sy, sz, 0, sry, 0, 0x0FFF)
    n += 1

    # SkyboxSettings (ID=17): unk=0, skyboxId=0, weather=0, indoors=1 (4 bytes!)
    cmds += write_cmd_id(17)
    cmds += bytes([0, 0, 0, 1])
    n += 1

    # ExitList (ID=19): zero exits. Vanilla provides one even when none are
    # used; some downstream code may iterate the list assuming the command
    # has run.
    cmds += write_cmd_id(19)
    cmds += struct.pack('<I', 0)
    n += 1

    # LightSettings (ID=15): 1 simple light setting (22 bytes per entry).
    # Layout: 3×u8 ambient, 3×s8 light1 dir, 3×u8 light1 color,
    # 3×s8 light2 dir, 3×u8 light2 color, 3×u8 fog color, s16 fogNear, s16 zFar.
    # SoH reads s16 fields as little-endian — earlier hard-coded byte literals
    # were big-endian (0x03,0xE0 == 0x03E0 BE == 992 BE; SoH read this as
    # 0xE003 LE = -8189). zFar bytes (0x10,0x00) parsed to LE 0x0010 = 16,
    # which makes the camera fog out everything beyond 16 units → black world.
    # Use struct.pack('<h', ...) to write the fields in the right endianness.
    cmds += write_cmd_id(15)
    cmds += struct.pack('<I', 1)  # count
    cmds += bytes([
        80, 80, 90,       # ambient RGB
        50, 50, 50,       # light1 dir
        180, 180, 200,    # light1 color
        -50 & 0xFF, -50 & 0xFF, -50 & 0xFF,  # light2 dir
        60, 60, 80,       # light2 color
        100, 90, 80,      # fog color
    ])
    cmds += struct.pack('<hh', 996, 12800)  # fogNear, zFar (LE s16, matches vanilla scale)
    n += 1

    # EndMarker (ID=20)
    cmds += write_cmd_id(20)
    n += 1

    return header + struct.pack('<I', n) + bytes(cmds)


def build_room_header(dl_path: str, actors: list = None,
                      extra_dl_paths: list[str] = None,
                      extra_object_ids: list[int] | None = None) -> bytes:
    """Build room header with SetMesh Type 0, ObjectList, and ActorList.

    `actors` is a list of dicts: {"name": str, "x": int, "y": int, "z": int,
                                   "rot_y": int (optional), "params": int (optional)}
    `extra_dl_paths` adds additional polygon DLs (rendered alongside main `dl_path`).
    `extra_object_ids` extends the auto-derived ObjectList with object IDs
    needed by transition actors (En_Door etc.) that aren't part of the
    room's actor list.
    Required objects are derived automatically from actor names.
    """
    actors = actors or []
    extra_dl_paths = extra_dl_paths or []
    actor_names = [a["name"] for a in actors]
    object_ids = collect_required_objects(actor_names)
    if extra_object_ids:
        object_ids = sorted(set(object_ids) | set(extra_object_ids))

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

def build_collision(min_x: int = -600, max_x: int = 600,
                     floor_y: int = -100, h: int = 600,
                     min_z: int = -1500, max_z: int = 1500,
                     inner_walls: list[dict] | None = None) -> bytes:
    """Complete box collision: floor + 4 outer walls + ceiling, plus optional
    inner walls with door cutouts.

    Outer box spans (min_x..max_x, floor_y..floor_y+h, min_z..max_z) —
    defaults match the v0.6 single-room layout.

    `inner_walls` is a list of dicts describing X-aligned shared walls
    between rooms. Each dict has keys:
        - "x":         world x-plane the wall sits on
        - "z_range":   (z_min, z_max) extent of the wall
        - "door":      {"half_width", "height"} centred door cutout at z=0,
                        y=[floor_y, floor_y+height]
    Each inner wall emits three quad panels (above + two flanks) and
    bidirectional collision polys so Link is blocked from both sides
    except where the door hole sits.
    """
    inner_walls = inner_walls or []
    header = build_resource_header(RES_COLLISION)
    ceiling_y = floor_y + h

    body = bytearray()
    body += struct.pack('<hhh', min_x, floor_y,   min_z)  # min
    body += struct.pack('<hhh', max_x, ceiling_y, max_z)  # max

    # Outer-box corners: 4 floor + 4 ceiling.
    verts: list[tuple[int, int, int]] = [
        (min_x, floor_y,   min_z),  # 0
        (max_x, floor_y,   min_z),  # 1
        (max_x, floor_y,   max_z),  # 2
        (min_x, floor_y,   max_z),  # 3
        (min_x, ceiling_y, min_z),  # 4
        (max_x, ceiling_y, min_z),  # 5
        (max_x, ceiling_y, max_z),  # 6
        (min_x, ceiling_y, max_z),  # 7
    ]

    # Format: (surface_type, vIA, vIB, vIC, normalX, normalY, normalZ, dist)
    # All normals are int16 with 0x7FFF = 1.0 in Q1.15 fixed point.
    NX_POS = 0x7FFF; NX_NEG = 0x8001
    NY_POS = 0x7FFF; NY_NEG = 0x8001
    NZ_POS = 0x7FFF; NZ_NEG = 0x8001

    # dist = -dot(normal, point_on_plane).
    polys: list[tuple] = [
        # FLOOR — normal +Y.
        (0, 0, 2, 1, 0, NY_POS, 0, -floor_y),
        (0, 0, 3, 2, 0, NY_POS, 0, -floor_y),
        # CEILING — normal -Y.
        (0, 4, 5, 6, 0, NY_NEG, 0, ceiling_y),
        (0, 4, 6, 7, 0, NY_NEG, 0, ceiling_y),
        # NORTH WALL z=min_z, normal +Z.
        (0, 0, 1, 5, 0, 0, NZ_POS, -min_z),
        (0, 0, 5, 4, 0, 0, NZ_POS, -min_z),
        # SOUTH WALL z=max_z, normal -Z.
        (0, 2, 3, 7, 0, 0, NZ_NEG, max_z),
        (0, 2, 7, 6, 0, 0, NZ_NEG, max_z),
        # WEST WALL x=min_x, normal +X.
        (0, 3, 0, 4, NX_POS, 0, 0, -min_x),
        (0, 3, 4, 7, NX_POS, 0, 0, -min_x),
        # EAST WALL x=max_x, normal -X.
        (0, 1, 2, 6, NX_NEG, 0, 0, max_x),
        (0, 1, 6, 5, NX_NEG, 0, 0, max_x),
    ]

    base_idx = len(verts)
    for iw in inner_walls:
        x = iw["x"]
        zmin, zmax = iw["z_range"]
        door = iw.get("door")

        if door is None:
            # Solid wall — single full-height quad spanning the whole z range.
            panels = [
                ((x, floor_y, zmin),   (x, floor_y, zmax),
                 (x, ceiling_y, zmax), (x, ceiling_y, zmin)),
            ]
        else:
            door_top = floor_y + door["height"]
            door_half = door["half_width"]
            # Three panel quads with a centred door cutout. Winding picks
            # the +X normal; the loop below emits a second poly with
            # reversed winding for -X so the wall blocks both sides.
            panels = [
                # Above the door — full width, top strip from door_top to ceiling.
                ((x, door_top, zmin),  (x, door_top, zmax),
                 (x, ceiling_y, zmax), (x, ceiling_y, zmin)),
                # Flank toward +Z (between door and zmax).
                ((x, floor_y, door_half), (x, floor_y, zmax),
                 (x, door_top, zmax),     (x, door_top, door_half)),
                # Flank toward -Z (between zmin and door).
                ((x, floor_y, zmin),   (x, floor_y, -door_half),
                 (x, door_top, -door_half), (x, door_top, zmin)),
            ]
        for v0, v1, v2, v3 in panels:
            verts.extend([v0, v1, v2, v3])
            a, b, c, d = base_idx, base_idx + 1, base_idx + 2, base_idx + 3
            # Normal +X (block from -X side)
            polys.append((0, a, b, c, NX_POS, 0, 0, -x))
            polys.append((0, a, c, d, NX_POS, 0, 0, -x))
            # Normal -X (block from +X side) — reversed winding.
            polys.append((0, c, b, a, NX_NEG, 0, 0,  x))
            polys.append((0, d, c, a, NX_NEG, 0, 0,  x))
            base_idx += 4

    body += struct.pack('<i', len(verts))
    for v in verts:
        body += struct.pack('<hhh', *v)

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

# All En_Item00 drop variants that can lie around in OoT — paired with their
# label for diagnostic logging. ITEM00_FLEXIBLE (0x12) is excluded: it picks a
# random drop based on the killing enemy and is unstable for static placement.
ITEM00_SHOWCASE = [
    (ITEM00_RUPEE_GREEN,     "rupee_green"),
    (ITEM00_RUPEE_BLUE,      "rupee_blue"),
    (ITEM00_RUPEE_RED,       "rupee_red"),
    (ITEM00_RUPEE_ORANGE,    "rupee_orange"),
    (ITEM00_RUPEE_PURPLE,    "rupee_purple"),
    (ITEM00_HEART,           "heart"),
    (ITEM00_HEART_PIECE,     "heart_piece"),
    (ITEM00_HEART_CONTAINER, "heart_container"),
    (ITEM00_BOMBS_A,         "bombs_a"),
    (ITEM00_BOMBS_B,         "bombs_b"),
    (ITEM00_BOMBS_SPECIAL,   "bombs_special"),
    (ITEM00_BOMBCHU,         "bombchu"),
    (ITEM00_ARROWS_SINGLE,   "arrows_single"),
    (ITEM00_ARROWS_SMALL,    "arrows_small"),
    (ITEM00_ARROWS_MEDIUM,   "arrows_medium"),
    (ITEM00_ARROWS_LARGE,    "arrows_large"),
    (ITEM00_NUTS,            "nuts"),
    (ITEM00_STICK,           "stick"),
    (ITEM00_SEEDS,           "seeds"),
    (ITEM00_MAGIC_LARGE,     "magic_large"),
    (ITEM00_MAGIC_SMALL,     "magic_small"),
    (ITEM00_SMALL_KEY,       "small_key"),
    (ITEM00_SHIELD_DEKU,     "shield_deku"),
    (ITEM00_SHIELD_HYLIAN,   "shield_hylian"),
    (ITEM00_TUNIC_GORON,     "tunic_goron"),
    (ITEM00_TUNIC_ZORA,      "tunic_zora"),
]


def _build_item_row(x: int, z_min: int, z_max: int, y: int = -100) -> list[dict]:
    """Spread ITEM00_SHOWCASE evenly along Z at the given X line."""
    n = len(ITEM00_SHOWCASE)
    out = []
    if n == 1:
        out.append({"name": "item00", "x": x, "y": y, "z": (z_min + z_max) // 2,
                    "params": ITEM00_SHOWCASE[0][0]})
        return out
    step = (z_max - z_min) / (n - 1)
    for i, (variant, _label) in enumerate(ITEM00_SHOWCASE):
        z = int(z_min + i * step)
        out.append({"name": "item00", "x": x, "y": y, "z": z, "params": variant})
    return out


# DEFAULT_ACTORS — the standalone debug-room layout the tooling/ CLI emits.
# Box dimensions are 1200 (X) × 600 (Y) × 3000 (Z) with Z as the long axis,
# so we keep the existing chest+pots+deku-babas in the original cluster
# and add a row of En_Item00 showcase drops along the new long Z axis.
DEFAULT_ACTORS = [
    # 4 pots at the corners of the original 800×800 footprint.
    {"name": "pot", "x": -400, "y": -100, "z": -400},
    {"name": "pot", "x":  400, "y": -100, "z": -400},
    {"name": "pot", "x":  400, "y": -100, "z":  400},
    {"name": "pot", "x": -400, "y": -100, "z":  400},
    # Big chest with Mario reward at the centre — params filled at runtime.
    {"name": "chest", "x": 0, "y": -100, "z": 0, "rot_y": 0x8000, "params": None},
    # Three Deku Babas south-of-centre.
    {"name": "deku_baba", "x": -300, "y": -100, "z": -100},
    {"name": "deku_baba", "x":  300, "y": -100, "z": -100},
    {"name": "deku_baba", "x":    0, "y": -100, "z": -350},
]


def _resolve_default_actors() -> list[dict]:
    """Materialise DEFAULT_ACTORS — fills in chest params, appends item showcase row."""
    out: list[dict] = []
    for a in DEFAULT_ACTORS:
        a = dict(a)
        if a.get("name") == "chest" and a.get("params") is None:
            a["params"] = chest_params(item_id=GI_LIVEGEN_MARIO, treasure_flag=1)
        out.append(a)
    # Showcase row on the west side (x=-300), spread along the long Z axis.
    out.extend(_build_item_row(x=-300, z_min=-1300, z_max=1300))
    return out


def build_dungeon_o2r(
    output_path: Path | str,
    actors: list[dict] | None = None,
    *,
    include_mario_dl: bool = True,
    include_pizza_dl: bool = True,
    include_sonic_dl: bool = True,
    include_hydrant_dl: bool = True,
    include_cupcake_dl: bool = True,
    include_mouse_dl: bool = True,
    rooms: list[dict] | None = None,
    inner_walls: list[dict] | None = None,
    transition_actors: list[dict] | None = None,
    spawn_pos: tuple[int, int, int] = (0, 0, 0),
    spawn_rot_y: int = 0,
) -> Path:
    """Build a custom box-room .o2r.

    Single-room mode (v0.6 baseline): pass `actors` (or None for defaults).
    Multi-room mode (M7+): pass `rooms` — a list of dicts with keys:
        - "actors":     list of actor dicts (defaults to []) — populated only
                         in the room they're authored in.
        - "offset":     (ox, oy, oz) world translation for the box geometry.
        - "skip_walls": optional set of face names ("east"/"west"/...) that
                         this room should NOT render — used for the shared
                         boundary between adjacent rooms.
        - "doors":      optional dict {face: {"half_width", "height"}} — wall
                         renders with a centred door-shaped hole instead of
                         being skipped or fully solid.

    `actors` is ignored when `rooms` is provided.

    Args:
        output_path: where to write the .o2r
        include_mario_dl: pack Mario VTX/DL (resolved by chest drawFunc)
        include_pizza_dl: pack Pizza VTX/DL (resolved by decoration hook)
    """
    from obj_to_dl import parse_obj
    from mesh_to_dl import load_mesh

    # All Squadala assets live under their own namespace — no overlap with
    # vanilla resource paths. This means LoadResource never collides with
    # cached vanilla data, so we don't need to evict anything to load fresh.
    TARGET = "scenes/squadala"
    SCENE_PATH = f"{TARGET}/dungeon_scene"
    COLLISION_PATH = f"{TARGET}/collision"

    # Pipeline assets live under tooling/assets/3d/. _raw_data/ is the user's
    # drop-zone (raw deliveries) and must never be referenced from build code.
    ASSETS_3D = Path(__file__).parent / "assets" / "3d"

    MARIO_OBJ = ASSETS_3D / "super_mario" / "model.obj"
    MARIO_VTX_PATH = f"{TARGET}/mario_Vtx"
    MARIO_DL_PATH = f"{TARGET}/mario_DL"

    SONIC_OBJ = ASSETS_3D / "Pixel Sonic" / "model.obj"
    SONIC_VTX_PATH = f"{TARGET}/sonic_Vtx"
    SONIC_DL_PATH = f"{TARGET}/sonic_DL"

    HYDRANT_GLB = ASSETS_3D / "Fire Hydrant.glb"
    HYDRANT_VTX_PATH = f"{TARGET}/hydrant_Vtx"
    HYDRANT_DL_PATH = f"{TARGET}/hydrant_DL"

    PIZZA_GLB = ASSETS_3D / "pizza.glb"
    PIZZA_VTX_PATH = f"{TARGET}/pizza_Vtx"
    PIZZA_DL_PATH = f"{TARGET}/pizza_DL"

    CUPCAKE_GLB = ASSETS_3D / "cupcake.glb"
    CUPCAKE_VTX_PATH = f"{TARGET}/cupcake_Vtx"
    CUPCAKE_DL_PATH = f"{TARGET}/cupcake_DL"

    MOUSE_GLB = ASSETS_3D / "mouse.glb"
    MOUSE_VTX_PATH = f"{TARGET}/mouse_Vtx"
    MOUSE_DL_PATH = f"{TARGET}/mouse_DL"

    # Normalise to multi-room shape so the rest of the function has a single
    # code path. Single-room scenes are just a 1-element rooms list.
    if rooms is None:
        if actors is None:
            actors = _resolve_default_actors()
        rooms = [{"actors": actors, "offset": (0, 0, 0), "skip_walls": set()}]

    # Shared decoration / chest-content assets (Mario, Sonic, Hydrant,
    # Pizza, Cupcake) — packed once, referenced by all rooms via __OTR__ paths.
    mario_vtx = mario_dl = None
    sonic_vtx = sonic_dl = None
    hydrant_vtx = hydrant_dl = None
    pizza_vtx = pizza_dl = None
    cupcake_vtx = cupcake_dl = None
    mouse_vtx = mouse_dl = None
    if include_mario_dl:
        mario = parse_obj(MARIO_OBJ, scale=200.0, y_offset=35.0, rotation_y_degrees=0.0)
        mario_verts = [(v[0], v[1], v[2]) for v in mario.vertices]
        mario_colors = [(v[3], v[4], v[5], v[6]) for v in mario.vertices]
        mario_vtx = build_vtx_resource(mario_verts, mario_colors)
        mario_dl = build_unindexed_dl(MARIO_VTX_PATH, len(mario.triangles))
        print(f"Mario: {len(mario.vertices)} verts, {len(mario.triangles)} tris → "
              f"VTX {len(mario_vtx)}B, DL {len(mario_dl)}B")

    if include_sonic_dl:
        sonic = parse_obj(SONIC_OBJ, scale=200.0, y_offset=35.0, rotation_y_degrees=0.0)
        sonic_verts = [(v[0], v[1], v[2]) for v in sonic.vertices]
        sonic_colors = [(v[3], v[4], v[5], v[6]) for v in sonic.vertices]
        sonic_vtx = build_vtx_resource(sonic_verts, sonic_colors)
        sonic_dl = build_unindexed_dl(SONIC_VTX_PATH, len(sonic.triangles))
        print(f"Sonic: {len(sonic.vertices)} verts, {len(sonic.triangles)} tris → "
              f"VTX {len(sonic_vtx)}B, DL {len(sonic_dl)}B")

    if include_hydrant_dl:
        # scale 14000 brings the hydrant to a usable size (the GLB normalises
        # into a -1..+1 cube). Source is Z-up (Blender default export), so
        # rotate -90° on X to make it stand upright in OoT's Y-up world.
        # The GLB ships an image texture rather than a baseColorFactor, so
        # trimesh falls back to default_color — fire-engine red here.
        hydrant = load_mesh(
            HYDRANT_GLB,
            scale=14000.0,
            y_offset=0.0,
            rotation_deg=(-90.0, 0.0, 0.0),
            color_override=(220, 30, 30, 255),  # fire-engine red
            # SoH's room rendering doesn't run real-time lighting on our DL
            # (G_CC_SHADE uses vertex colours directly). Bake a fake-light
            # shade per face into the vertex colours so the hydrant reads
            # as a 3D shape instead of a flat red silhouette.
            shade_strength=0.6,
        )
        hydrant_verts = [(v[0], v[1], v[2]) for v in hydrant.vertices]
        hydrant_colors = [(v[3], v[4], v[5], v[6]) for v in hydrant.vertices]
        hydrant_vtx = build_vtx_resource(hydrant_verts, hydrant_colors)
        hydrant_dl = build_unindexed_dl(HYDRANT_VTX_PATH, len(hydrant.triangles))
        print(f"Hydrant: {len(hydrant.vertices)} verts, {len(hydrant.triangles)} tris → "
              f"VTX {len(hydrant_vtx)}B, DL {len(hydrant_dl)}B")

    if include_pizza_dl:
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

    if include_cupcake_dl:
        # Same scale as pizza — GLB normalised mesh, ~100-unit on-screen size.
        # Source is Z-up (Blender default export); rotate -90° on X to bring
        # the cupcake upright in OoT's Y-up world.
        cupcake = load_mesh(
            CUPCAKE_GLB,
            scale=14000.0,
            y_offset=0.0,
            rotation_deg=(-90.0, 0.0, 0.0),
        )
        cupcake_verts = [(v[0], v[1], v[2]) for v in cupcake.vertices]
        cupcake_colors = [(v[3], v[4], v[5], v[6]) for v in cupcake.vertices]
        cupcake_vtx = build_vtx_resource(cupcake_verts, cupcake_colors)
        cupcake_dl = build_unindexed_dl(CUPCAKE_VTX_PATH, len(cupcake.triangles))
        print(f"Cupcake: {len(cupcake.vertices)} verts, {len(cupcake.triangles)} tris → "
              f"VTX {len(cupcake_vtx)}B, DL {len(cupcake_dl)}B")

    if include_mouse_dl:
        # GLB carries 3 PNG textures + a skinned skeleton with idle/run/jump
        # animations. None of that is supported by our static-DL path yet
        # (texture sampling = M9, skeletal animation = M11 / future). We bake
        # the rest pose into a flat-shaded DL with the diffuse texture's
        # average colour as a stand-in. Scale picked empirically against the
        # other decorations — 4.91-unit-long mesh stays visible without
        # dwarfing the room.
        mouse = load_mesh(
            MOUSE_GLB,
            scale=167.0,
            y_offset=0.0,
            rotation_deg=(0.0, 0.0, 0.0),
            color_override=(198, 172, 169, 255),  # diffuse-texture average
            shade_strength=0.6,
        )
        mouse_verts = [(v[0], v[1], v[2]) for v in mouse.vertices]
        mouse_colors = [(v[3], v[4], v[5], v[6]) for v in mouse.vertices]
        mouse_vtx = build_vtx_resource(mouse_verts, mouse_colors)
        mouse_dl = build_unindexed_dl(MOUSE_VTX_PATH, len(mouse.triangles))
        print(f"Mouse: {len(mouse.vertices)} verts, {len(mouse.triangles)} tris → "
              f"VTX {len(mouse_vtx)}B, DL {len(mouse_dl)}B")

    # `func_80031A28` (the actor cleanup pass triggered by every Room's
    # ObjectList command) Actor_Kills any actor whose required object
    # isn't in the new room's ObjectList. That breaks two things in
    # multi-room scenes:
    #   1. Transition actors (En_Door, En_Holl) crossing rooms.
    #   2. Room-N actors that briefly co-exist with a different room
    #      becoming "loaded" — e.g. a Deku Baba in Room 0 dies the moment
    #      Link approaches the En_Holl trigger to Room 1 because Room 1's
    #      ObjectList lacks the Deku Baba object.
    # Sidestep both by giving every room the union of every transition
    # actor's *and* every room actor's required objects. Memory hit is
    # negligible for the debug scene; vanilla scenes pay this cost too
    # via the always-loaded gameplay_keep / gameplay_dangeon_keep set.
    shared_objects: set[int] = set()
    for ta in (transition_actors or []):
        ta_name = ta["actor_name"]
        if ta_name in ACTOR_LIBRARY:
            shared_objects.update(ACTOR_LIBRARY[ta_name][2])
    for r in rooms:
        for a in r.get("actors", []):
            if a["name"] in ACTOR_LIBRARY:
                shared_objects.update(ACTOR_LIBRARY[a["name"]][2])

    # Per-room: build dedicated VTX, DL and room-header resource.
    room_paths: list[str] = []
    room_assets: list[tuple[str, bytes, str, bytes, str, bytes]] = []
    total_actors = 0
    for i, room_cfg in enumerate(rooms):
        room_actors = room_cfg.get("actors", [])
        offset = room_cfg.get("offset", (0, 0, 0))
        skip_walls = room_cfg.get("skip_walls", set())
        doors = room_cfg.get("doors", {})
        total_actors += len(room_actors)

        vtx_path = f"{TARGET}/room{i}_Vtx"
        dl_path = f"{TARGET}/room{i}_DL"
        room_path = f"{TARGET}/room_{i}"
        room_paths.append(room_path)

        verts, cols, n_faces = build_box_vertices(
            offset=offset, skip_walls=skip_walls, doors=doors,
        )
        faces = build_box_faces(n_faces)
        vtx_res = build_vtx_resource(verts, cols)
        dl_res = build_display_list(vtx_path, len(verts), faces)
        room_res = build_room_header(
            dl_path, actors=room_actors,
            extra_object_ids=sorted(shared_objects),
        )
        room_assets.append((vtx_path, vtx_res, dl_path, dl_res, room_path, room_res))

    # Collision bounds = union of all rooms' visual extents. With no shared
    # inner walls, Link can walk freely across the boundary — visual door
    # panels (cosmetic) plus En_Holl/En_Door (M7-3b+) gate the actual room
    # transition.
    room_w, room_h, room_d = 600, 600, 1500  # match build_box_vertices defaults
    floor_y = -100
    if len(rooms) == 1:
        ox, oy, oz = rooms[0].get("offset", (0, 0, 0))
        collision = build_collision(
            min_x=ox - room_w, max_x=ox + room_w,
            floor_y=floor_y + oy, h=room_h,
            min_z=oz - room_d, max_z=oz + room_d,
            inner_walls=inner_walls,
        )
    else:
        offsets = [r.get("offset", (0, 0, 0)) for r in rooms]
        min_x = min(ox - room_w for ox, _, _ in offsets)
        max_x = max(ox + room_w for ox, _, _ in offsets)
        min_z = min(oz - room_d for _, _, oz in offsets)
        max_z = max(oz + room_d for _, _, oz in offsets)
        collision = build_collision(
            min_x=min_x, max_x=max_x,
            floor_y=floor_y, h=room_h,
            min_z=min_z, max_z=max_z,
            inner_walls=inner_walls,
        )
    scene_header = build_scene_header(
        room_paths if len(room_paths) > 1 else room_paths[0],
        COLLISION_PATH,
        max(len(r[5]) for r in room_assets),
        transition_actors=transition_actors,
        spawn_pos=spawn_pos,
        spawn_rot_y=spawn_rot_y,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(output), 'w', zipfile.ZIP_STORED) as oz:
        for vtx_path, vtx_res, dl_path, dl_res, room_path, room_res in room_assets:
            oz.writestr(vtx_path, vtx_res)
            oz.writestr(dl_path, dl_res)
            oz.writestr(room_path, room_res)
        if mario_vtx is not None:
            oz.writestr(MARIO_VTX_PATH, mario_vtx)
            oz.writestr(MARIO_DL_PATH, mario_dl)
        if sonic_vtx is not None:
            oz.writestr(SONIC_VTX_PATH, sonic_vtx)
            oz.writestr(SONIC_DL_PATH, sonic_dl)
        if hydrant_vtx is not None:
            oz.writestr(HYDRANT_VTX_PATH, hydrant_vtx)
            oz.writestr(HYDRANT_DL_PATH, hydrant_dl)
        if pizza_vtx is not None:
            oz.writestr(PIZZA_VTX_PATH, pizza_vtx)
            oz.writestr(PIZZA_DL_PATH, pizza_dl)
        if cupcake_vtx is not None:
            oz.writestr(CUPCAKE_VTX_PATH, cupcake_vtx)
            oz.writestr(CUPCAKE_DL_PATH, cupcake_dl)
        if mouse_vtx is not None:
            oz.writestr(MOUSE_VTX_PATH, mouse_vtx)
            oz.writestr(MOUSE_DL_PATH, mouse_dl)
        oz.writestr(COLLISION_PATH, collision)
        oz.writestr(SCENE_PATH, scene_header)

        print(f"Scene: {len(scene_header)}B | Rooms: {len(room_assets)} | Collision: {len(collision)}B")

    print(f"Output: {output} ({output.stat().st_size} bytes)")
    print(f"Actors: {total_actors} | Mario DL: {include_mario_dl} | Pizza DL: {include_pizza_dl}")
    return output


def _build_l_shape_geometry(arm_a, arm_b, floor_y, h):
    """Emit visual mesh + collision data for an L-shape room.

    Arm A is the south arm (player spawns at its south end facing north).
    Arm B sticks east from the NORTH end of Arm A so the "corner" is in
    front of the player. Walking conventions:
        +X = east, -X = west, +Z = south, -Z = north (matches OoT spawn
        convention where rot_y=0x8000 looks toward -Z).

    Args:
        arm_a: {"x_range": (min, max), "z_range": (min, max)} — south arm.
        arm_b: same shape — east extension at the north end of Arm A.
    Returns:
        (verts, colors, n_faces, floor_rects, perimeter)
        - verts/colors/n_faces: feed into build_box_faces + build_vtx_resource
          + build_display_list.
        - floor_rects: [(x_min, x_max, z_min, z_max)] decomposition for
          floor/ceiling collision.
        - perimeter: list of (p_start, p_end) outer-wall segments wound CCW
          from above with interior on the right — same convention the box
          builder uses for the four cardinal walls.
    """
    ax_min, ax_max = arm_a["x_range"]
    az_min, az_max = arm_a["z_range"]
    bx_min, bx_max = arm_b["x_range"]
    bz_min, bz_max = arm_b["z_range"]
    assert bx_min == ax_max, "Arm B's west edge must align with Arm A's east"
    assert bz_min == az_min, "Arms must share the north edge"
    assert bz_max < az_max, "Arm B's south edge must be inside Arm A's z range"
    ceiling_y = floor_y + h

    # Per-face fake-light shading so adjacent walls don't blend into one
    # flat blob. Same idea as mesh_to_dl.shade_strength: dot the surface
    # normal with a fixed light direction, modulate the base colour. Light
    # comes from above + slightly NE, so the west/south walls read lighter
    # than the east/north ones and corners become visible.
    LIGHT_DIR  = (0.4, 0.8, -0.4)
    SHADE_STRENGTH = 0.55
    _lmag = math.sqrt(sum(c * c for c in LIGHT_DIR)) or 1.0
    _lx, _ly, _lz = (c / _lmag for c in LIGHT_DIR)

    def shade(base_color, normal):
        nx, ny, nz = normal
        nmag = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / nmag, ny / nmag, nz / nmag
        dot = nx * _lx + ny * _ly + nz * _lz
        s = 1.0 - SHADE_STRENGTH * (1.0 - 0.5 * (dot + 1.0))
        s = max(0.0, min(1.0, s))
        return (int(base_color[0] * s), int(base_color[1] * s),
                int(base_color[2] * s), base_color[3])

    floor_base   = (130, 200, 120, 255)  # warm green
    ceiling_base = (110, 110, 140, 255)  # cool blue-gray
    floor_color   = shade(floor_base,   normal=(0,  1, 0))
    ceiling_color = shade(ceiling_base, normal=(0, -1, 0))

    # Per-segment wall palette — vivid scheme like build_box_vertices so
    # adjacent walls along the same compass direction (W and S, or E1 and
    # E2) don't collapse into one tone. Shading still applies on top so
    # corners read as distinct planes. Order matches the perimeter list
    # below: W, N, E1, S1, E2, S.
    wall_palette = [
        ( 60, 200, 200, 255),  # W   — cyan
        ( 60, 100, 220, 255),  # N   — blue
        (200,  60, 200, 255),  # E1  — magenta
        (220, 200,  60, 255),  # S1  — yellow (reflex inner south)
        (200, 120,  60, 255),  # E2  — orange (south arm east)
        (160, 220,  60, 255),  # S   — lime
    ]

    # Outer-wall perimeter, CCW from above with interior on the RIGHT —
    # matches the build_box_vertices west-wall convention so the existing
    # start_floor / end_floor / end_ceil / start_ceil winding renders the
    # inside face. With +Z=south, walking south→north means going -Z.
    perimeter = [
        ((ax_min, az_max), (ax_min, az_min)),  # W:  SW → NW (going -Z)
        ((ax_min, az_min), (bx_max, az_min)),  # N:  NW → NE (going +X)
        ((bx_max, az_min), (bx_max, bz_max)),  # E1: NE → SE-of-B (going +Z)
        ((bx_max, bz_max), (ax_max, bz_max)),  # S1: reflex turn (going -X)
        ((ax_max, bz_max), (ax_max, az_max)),  # E2: south arm east (going +Z)
        ((ax_max, az_max), (ax_min, az_max)),  # S:  SE → SW (going -X)
    ]

    # Floor/ceiling rectangles. Decompose the L into two non-overlapping
    # rects so we can reuse the box floor/ceiling winding directly.
    floor_rects = [
        (ax_min, ax_max, az_min, az_max),  # full south arm
        (ax_max, bx_max, bz_min, bz_max),  # east-arm extension
    ]

    verts: list[tuple[int, int, int]] = []
    colors: list[tuple[int, int, int, int]] = []
    n_faces = 0

    def push_quad(quad, color):
        nonlocal n_faces
        for v in quad:
            verts.append(v)
            colors.append(color)
        n_faces += 1

    for x0, x1, z0, z1 in floor_rects:
        # Floor (normal +Y). Same winding as the box-room floor:
        # (x0, fy, z1) (x1, fy, z1) (x1, fy, z0) (x0, fy, z0) — CCW from above.
        push_quad([
            (x0, floor_y, z1), (x1, floor_y, z1),
            (x1, floor_y, z0), (x0, floor_y, z0),
        ], floor_color)
        # Ceiling (normal -Y). Mirror winding.
        push_quad([
            (x0, ceiling_y, z0), (x1, ceiling_y, z0),
            (x1, ceiling_y, z1), (x0, ceiling_y, z1),
        ], ceiling_color)

    # Walls: for each perimeter segment (s → e, interior on the right), emit
    # the inward-facing quad as (s_floor, e_floor, e_ceil, s_ceil) — same
    # pattern as the west wall in build_box_vertices. Per-wall normal feeds
    # the shader so corners between adjacent walls read as distinct planes
    # instead of one flat surface.
    for idx, ((sx, sz), (ex, ez)) in enumerate(perimeter):
        dx, dz = ex - sx, ez - sz
        # Inward normal: walking start→end with interior on the right, the
        # normal is the segment direction rotated 90° clockwise in the XZ
        # plane (top-down view, +X east, +Z south).
        if dx == 0:
            n = (1, 0, 0) if dz < 0 else (-1, 0, 0)
        else:
            n = (0, 0, 1) if dx > 0 else (0, 0, -1)
        push_quad([
            (sx, floor_y,   sz),
            (ex, floor_y,   ez),
            (ex, ceiling_y, ez),
            (sx, ceiling_y, sz),
        ], shade(wall_palette[idx], n))

    return verts, colors, n_faces, floor_rects, perimeter


def _build_l_shape_collision(floor_rects, perimeter, floor_y, h,
                             interior_walls=None) -> bytes:
    """Collision body for a room with N floor rects + outer perimeter walls +
    optional interior walls (two-sided partitions).

    Args:
        floor_rects:    list of (x_min, x_max, z_min, z_max) for floor/ceiling.
        perimeter:      outer-wall segments, CCW from above, interior on right.
        interior_walls: optional list of (start, end) segments. Each emits
                        TWO polys with opposite normals so it blocks from
                        both sides (no implicit "interior" direction).
    """
    interior_walls = interior_walls or []
    ceiling_y = floor_y + h
    header = build_resource_header(RES_COLLISION)

    NX_POS = 0x7FFF; NX_NEG = 0x8001
    NY_POS = 0x7FFF; NY_NEG = 0x8001
    NZ_POS = 0x7FFF; NZ_NEG = 0x8001

    # Bounds for the AABB header.
    all_x = [p for r in floor_rects for p in (r[0], r[1])]
    all_z = [p for r in floor_rects for p in (r[2], r[3])]
    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)

    body = bytearray()
    body += struct.pack('<hhh', min_x, floor_y,   min_z)
    body += struct.pack('<hhh', max_x, ceiling_y, max_z)

    verts: list[tuple[int, int, int]] = []
    polys: list[tuple] = []

    def add_v(v: tuple[int, int, int]) -> int:
        verts.append(v)
        return len(verts) - 1

    # Floor + ceiling polys (2 tris per rect each).
    for x0, x1, z0, z1 in floor_rects:
        v_f = [
            add_v((x0, floor_y, z0)),
            add_v((x1, floor_y, z0)),
            add_v((x1, floor_y, z1)),
            add_v((x0, floor_y, z1)),
        ]
        polys.append((0, v_f[0], v_f[2], v_f[1], 0, NY_POS, 0, -floor_y))
        polys.append((0, v_f[0], v_f[3], v_f[2], 0, NY_POS, 0, -floor_y))
        v_c = [
            add_v((x0, ceiling_y, z0)),
            add_v((x1, ceiling_y, z0)),
            add_v((x1, ceiling_y, z1)),
            add_v((x0, ceiling_y, z1)),
        ]
        polys.append((0, v_c[0], v_c[1], v_c[2], 0, NY_NEG, 0, ceiling_y))
        polys.append((0, v_c[0], v_c[2], v_c[3], 0, NY_NEG, 0, ceiling_y))

    # Wall polys — one quad per perimeter segment, split into 2 tris.
    # Perimeter walks CCW from above (interior on the right), so the inward
    # normal for each axis-aligned segment is determined by walking direction:
    #   going north (dz<0) → interior is east → nx=+X
    #   going south (dz>0) → interior is west → nx=-X
    #   going east  (dx>0) → interior is south → nz=+Z
    #   going west  (dx<0) → interior is north → nz=-Z
    # dist follows the standard "dist = -dot(normal, point_on_plane)" formula.
    for (sx, sz), (ex, ez) in perimeter:
        v_sf = add_v((sx, floor_y,   sz))
        v_ef = add_v((ex, floor_y,   ez))
        v_ec = add_v((ex, ceiling_y, ez))
        v_sc = add_v((sx, ceiling_y, sz))
        dx = ex - sx
        dz = ez - sz
        if dx == 0:
            if dz < 0:
                nx, nz, dist = NX_POS, 0, -sx
            else:
                nx, nz, dist = NX_NEG, 0,  sx
        elif dz == 0:
            if dx > 0:
                nx, nz, dist = 0, NZ_POS, -sz
            else:
                nx, nz, dist = 0, NZ_NEG,  sz
        else:
            raise ValueError(
                f"L-shape walls must be axis-aligned, got dx={dx} dz={dz}")
        polys.append((0, v_sf, v_ef, v_ec, nx, 0, nz, dist))
        polys.append((0, v_sf, v_ec, v_sc, nx, 0, nz, dist))

    # Interior wall polys — two-sided. Each segment blocks from BOTH sides
    # so we emit the same quad twice with opposite normals + reversed
    # winding. The "natural" normal/dist comes from the segment direction
    # using the same right-hand convention as outer walls; the second poly
    # just flips everything.
    for (sx, sz), (ex, ez) in interior_walls:
        v_sf = add_v((sx, floor_y,   sz))
        v_ef = add_v((ex, floor_y,   ez))
        v_ec = add_v((ex, ceiling_y, ez))
        v_sc = add_v((sx, ceiling_y, sz))
        dx, dz = ex - sx, ez - sz
        if dx == 0:
            nx_a, nz_a, dist_a = (
                (NX_POS, 0, -sx) if dz < 0 else (NX_NEG, 0, sx)
            )
        elif dz == 0:
            nx_a, nz_a, dist_a = (
                (0, NZ_POS, -sz) if dx > 0 else (0, NZ_NEG, sz)
            )
        else:
            raise ValueError(
                f"Interior walls must be axis-aligned, got dx={dx} dz={dz}")
        # Side A
        polys.append((0, v_sf, v_ef, v_ec, nx_a, 0, nz_a, dist_a))
        polys.append((0, v_sf, v_ec, v_sc, nx_a, 0, nz_a, dist_a))
        # Side B — flipped normal, reversed winding, opposite dist.
        nx_b = (-nx_a) & 0xFFFF
        nz_b = (-nz_a) & 0xFFFF
        dist_b = -dist_a
        polys.append((0, v_sf, v_ec, v_ef, nx_b, 0, nz_b, dist_b))
        polys.append((0, v_sf, v_sc, v_ec, nx_b, 0, nz_b, dist_b))

    body += struct.pack('<i', len(verts))
    for v in verts:
        body += struct.pack('<hhh', *v)

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


def _build_maze_geometry(bounds, interior_walls, floor_y, h):
    """Outer rectangle + axis-aligned interior partitions, two-sided.

    Args:
        bounds: {"x_range": (min, max), "z_range": (min, max)}.
        interior_walls: list of dicts.
            {"start": (sx, sz), "end": (ex, ez)}                  full wall
            {"start": ..., "end": ...,
             "door": {"x": cx, "half_width": w, "height": h}}     wall with
                a door-shaped visual hole around (cx, ?, sz). Only Z-axis
                walls (sz == ez) carry doors today; the collision builder
                gets the full wall regardless so the door panel sits in a
                solid-collision frame and En_Door's open cutscene moves
                Link through.
    Returns:
        (verts, colors, n_faces, floor_rects, outer_perimeter)
    """
    x_min, x_max = bounds["x_range"]
    z_min, z_max = bounds["z_range"]
    ceiling_y = floor_y + h

    LIGHT_DIR  = (0.4, 0.8, -0.4)
    SHADE_STRENGTH = 0.55
    _lmag = math.sqrt(sum(c * c for c in LIGHT_DIR)) or 1.0
    _lx, _ly, _lz = (c / _lmag for c in LIGHT_DIR)

    def shade(base_color, normal):
        nx, ny, nz = normal
        nmag = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / nmag, ny / nmag, nz / nmag
        dot = nx * _lx + ny * _ly + nz * _lz
        s = 1.0 - SHADE_STRENGTH * (1.0 - 0.5 * (dot + 1.0))
        s = max(0.0, min(1.0, s))
        return (int(base_color[0] * s), int(base_color[1] * s),
                int(base_color[2] * s), base_color[3])

    floor_color   = shade((130, 200, 120, 255), (0,  1, 0))
    ceiling_color = shade((110, 110, 140, 255), (0, -1, 0))

    outer_palette = [
        ( 60, 200, 200, 255),  # W   — cyan
        ( 60, 100, 220, 255),  # N   — blue
        (200,  60, 200, 255),  # E   — magenta
        (220, 200,  60, 255),  # S   — yellow
    ]
    interior_palette = [
        (200, 120,  60, 255),  # interior 1 — orange
        (160, 220,  60, 255),  # interior 2 — lime
    ]

    outer_perimeter = [
        ((x_min, z_max), (x_min, z_min)),  # W
        ((x_min, z_min), (x_max, z_min)),  # N
        ((x_max, z_min), (x_max, z_max)),  # E
        ((x_max, z_max), (x_min, z_max)),  # S
    ]

    verts: list[tuple[int, int, int]] = []
    colors: list[tuple[int, int, int, int]] = []
    n_faces = 0

    def push_quad(quad, color):
        nonlocal n_faces
        for v in quad:
            verts.append(v)
            colors.append(color)
        n_faces += 1

    # Floor + ceiling — single rectangle, same winding as build_box_vertices.
    push_quad([
        (x_min, floor_y, z_max), (x_max, floor_y, z_max),
        (x_max, floor_y, z_min), (x_min, floor_y, z_min),
    ], floor_color)
    push_quad([
        (x_min, ceiling_y, z_min), (x_max, ceiling_y, z_min),
        (x_max, ceiling_y, z_max), (x_min, ceiling_y, z_max),
    ], ceiling_color)

    # Outer walls — single-sided (interior on the right).
    for idx, ((sx, sz), (ex, ez)) in enumerate(outer_perimeter):
        dx, dz = ex - sx, ez - sz
        if dx == 0:
            n = (1, 0, 0) if dz < 0 else (-1, 0, 0)
        else:
            n = (0, 0, 1) if dx > 0 else (0, 0, -1)
        push_quad([
            (sx, floor_y,   sz),
            (ex, floor_y,   ez),
            (ex, ceiling_y, ez),
            (sx, ceiling_y, sz),
        ], shade(outer_palette[idx], n))

    # Helper: emit a two-sided wall panel from (sx, sz) to (ex, ez), spanning
    # y_min..y_max. Same base colour both sides; shading flips so adjacent
    # panels at corners read as distinct planes.
    def push_two_sided_wall(p_start, p_end, y_min, y_max, base_color):
        sx, sz = p_start
        ex, ez = p_end
        dx, dz = ex - sx, ez - sz
        if dx == 0:
            n_a = (1, 0, 0) if dz < 0 else (-1, 0, 0)
        else:
            n_a = (0, 0, 1) if dx > 0 else (0, 0, -1)
        n_b = tuple(-c for c in n_a)
        push_quad([
            (sx, y_min, sz), (ex, y_min, ez),
            (ex, y_max, ez), (sx, y_max, sz),
        ], shade(base_color, n_a))
        push_quad([
            (ex, y_min, ez), (sx, y_min, sz),
            (sx, y_max, sz), (ex, y_max, ez),
        ], shade(base_color, n_b))

    # Interior walls — full-height by default; with a "door" entry, emit
    # left/right panels around the hole + a "lintel" panel above it so the
    # wall over the door doesn't show through to the next section.
    for idx, wall_cfg in enumerate(interior_walls):
        sx, sz = wall_cfg["start"]
        ex, ez = wall_cfg["end"]
        col = interior_palette[idx % len(interior_palette)]
        door = wall_cfg.get("door")

        if door is None:
            push_two_sided_wall((sx, sz), (ex, ez), floor_y, ceiling_y, col)
            continue

        # Door cutout (Z-axis wall only — sz == ez).
        assert sz == ez, "door cutouts only supported on Z-axis walls"
        cx = door["x"]
        hw = door["half_width"]
        door_top = floor_y + door["height"]
        x_lo, x_hi = sorted((sx, ex))
        d_lo, d_hi = cx - hw, cx + hw

        # Left panel (x_lo → door start), full height.
        if x_lo < d_lo:
            push_two_sided_wall((x_lo, sz), (d_lo, sz), floor_y, ceiling_y, col)
        # Right panel (door end → x_hi), full height.
        if d_hi < x_hi:
            push_two_sided_wall((d_hi, sz), (x_hi, sz), floor_y, ceiling_y, col)
        # Lintel panel above the door — closes the view-through gap.
        push_two_sided_wall((d_lo, sz), (d_hi, sz), door_top, ceiling_y, col)

    floor_rects = [(x_min, x_max, z_min, z_max)]
    return verts, colors, n_faces, floor_rects, outer_perimeter


def _build_thick_maze(bounds, wall_blocks, floor_y, h, thin_walls=None):
    """Maze with mixed thick wall blocks + optional thin wall planes.

    Thick blocks have 4 outward-facing visible faces (N, S, E, W) so their
    endpoints never expose a "spitze" plane edge — use them for partitions
    that end in open corridor space.

    Thin walls are single planes (rendered two-sided), used for walls whose
    endpoints reach the outer perimeter — extend them slightly past x=±max
    and the endpoints are hidden behind the outer walls. The door panel
    can sit FLUSH with a thin wall, which is what we want for En_Door.

    Args:
        bounds: outer box.
        wall_blocks: list of {"rect": (x0,x1,z0,z1)[, "door": {...}]}.
        thin_walls: list of {"start": (sx,sz), "end": (ex,ez)
                              [, "door": {"x": cx, "half_width": w,
                                          "height": h}]}.
                    Only Z-axis (sz==ez) walls with X-axis door cutouts
                    are supported.
    Returns:
        (verts, colors, n_faces, floor_rects, outer_perimeter,
         block_perimeters, thin_collision_segments)
    """
    thin_walls = thin_walls or []
    x_min, x_max = bounds["x_range"]
    z_min, z_max = bounds["z_range"]
    ceiling_y = floor_y + h

    LIGHT_DIR = (0.4, 0.8, -0.4)
    SHADE_STRENGTH = 0.55
    _lmag = math.sqrt(sum(c * c for c in LIGHT_DIR)) or 1.0
    _lx, _ly, _lz = (c / _lmag for c in LIGHT_DIR)

    def shade(base_color, normal):
        nx, ny, nz = normal
        nmag = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / nmag, ny / nmag, nz / nmag
        dot = nx * _lx + ny * _ly + nz * _lz
        s = 1.0 - SHADE_STRENGTH * (1.0 - 0.5 * (dot + 1.0))
        s = max(0.0, min(1.0, s))
        return (int(base_color[0] * s), int(base_color[1] * s),
                int(base_color[2] * s), base_color[3])

    floor_color   = shade((130, 200, 120, 255), (0,  1, 0))
    ceiling_color = shade((110, 110, 140, 255), (0, -1, 0))

    outer_palette = [
        ( 60, 200, 200, 255),  # W   — cyan
        ( 60, 100, 220, 255),  # N   — blue
        (200,  60, 200, 255),  # E   — magenta
        (220, 200,  60, 255),  # S   — yellow
    ]
    block_palette = [
        (200, 120,  60, 255),  # orange
        (160, 220,  60, 255),  # lime
        (220, 100, 140, 255),  # pink
        (120, 180, 220, 255),  # sky
        (220, 180,  80, 255),  # gold
    ]

    outer_perimeter = [
        ((x_min, z_max), (x_min, z_min)),  # W
        ((x_min, z_min), (x_max, z_min)),  # N
        ((x_max, z_min), (x_max, z_max)),  # E
        ((x_max, z_max), (x_min, z_max)),  # S
    ]

    verts: list[tuple[int, int, int]] = []
    colors: list[tuple[int, int, int, int]] = []
    n_faces = 0

    def push_quad(quad, color):
        nonlocal n_faces
        for v in quad:
            verts.append(v)
            colors.append(color)
        n_faces += 1

    # ── Floor / ceiling (single rect) ──────────────────────────────────
    push_quad([
        (x_min, floor_y, z_max), (x_max, floor_y, z_max),
        (x_max, floor_y, z_min), (x_min, floor_y, z_min),
    ], floor_color)
    push_quad([
        (x_min, ceiling_y, z_min), (x_max, ceiling_y, z_min),
        (x_max, ceiling_y, z_max), (x_min, ceiling_y, z_max),
    ], ceiling_color)

    # ── Outer perimeter walls ──────────────────────────────────────────
    for idx, ((sx, sz), (ex, ez)) in enumerate(outer_perimeter):
        dx, dz = ex - sx, ez - sz
        if dx == 0:
            n = (1, 0, 0) if dz < 0 else (-1, 0, 0)
        else:
            n = (0, 0, 1) if dx > 0 else (0, 0, -1)
        push_quad([
            (sx, floor_y,   sz),
            (ex, floor_y,   ez),
            (ex, ceiling_y, ez),
            (sx, ceiling_y, sz),
        ], shade(outer_palette[idx], n))

    # ── Thick wall blocks ──────────────────────────────────────────────
    # Block faces walked CW from above with OUTSIDE on the right — feeds
    # the existing wall-quad winding (start_floor/end_floor/end_ceil/
    # start_ceil) which produces an outward-visible face.
    block_perimeters: list[list[tuple]] = []

    def emit_face_quad(p_start, p_end, y_min, y_max, color):
        sx, sz = p_start
        ex, ez = p_end
        dx, dz = ex - sx, ez - sz
        if dx == 0:
            n = (1, 0, 0) if dz < 0 else (-1, 0, 0)
        else:
            n = (0, 0, 1) if dx > 0 else (0, 0, -1)
        push_quad([
            (sx, y_min, sz), (ex, y_min, ez),
            (ex, y_max, ez), (sx, y_max, sz),
        ], shade(color, n))

    def emit_face_with_door(p_start, p_end, door, y_min, y_max, color):
        """One long face with a door-shaped hole + lintel."""
        sx, sz = p_start
        ex, ez = p_end
        axis = door["axis"]
        center = door["position"]
        half_w = door["half_width"]
        door_top = y_min + door["height"]

        if axis == "x":
            assert sz == ez, "x-axis door cutout requires a Z-aligned face"
            lo, hi = sorted((sx, ex))
            d_lo, d_hi = center - half_w, center + half_w
            # Walk direction (sx→ex) decides left/right semantics; emit
            # using the SAME walk direction so the normal stays correct.
            #   step 1: from start to door-near-edge
            #   step 2: lintel above the gap
            #   step 3: from door-far-edge to end
            step = 1 if ex > sx else -1
            near = d_hi if step < 0 else d_lo
            far  = d_lo if step < 0 else d_hi
            if (step > 0 and near > sx) or (step < 0 and near < sx):
                emit_face_quad((sx, sz), (near, sz), y_min, y_max, color)
            emit_face_quad((near, sz), (far, sz), door_top, y_max, color)
            if (step > 0 and far < ex) or (step < 0 and far > ex):
                emit_face_quad((far, sz), (ex, sz), y_min, y_max, color)
        else:
            assert sx == ex, "z-axis door cutout requires an X-aligned face"
            d_lo, d_hi = center - half_w, center + half_w
            step = 1 if ez > sz else -1
            near = d_hi if step < 0 else d_lo
            far  = d_lo if step < 0 else d_hi
            if (step > 0 and near > sz) or (step < 0 and near < sz):
                emit_face_quad((sx, sz), (sx, near), y_min, y_max, color)
            emit_face_quad((sx, near), (sx, far), door_top, y_max, color)
            if (step > 0 and far < ez) or (step < 0 and far > ez):
                emit_face_quad((sx, far), (ex, ez), y_min, y_max, color)

    for idx, cfg in enumerate(wall_blocks):
        x0, x1, z0, z1 = cfg["rect"]
        col = block_palette[idx % len(block_palette)]
        door = cfg.get("door")

        # Block perimeter walked CW from above (outside on the right). Each
        # segment becomes one outward-facing face. Long X-axis faces (north
        # and south of the block, z=z0 and z=z1) carry the door cutout when
        # door.axis == "x"; long Z-axis faces (x=x0, x=x1) carry it when
        # door.axis == "z".
        perim_segments = [
            ((x1, z0), (x0, z0), "x", z0),  # north face (z=z0)
            ((x0, z0), (x0, z1), "z", x0),  # west  face (x=x0)
            ((x0, z1), (x1, z1), "x", z1),  # south face (z=z1)
            ((x1, z1), (x1, z0), "z", x1),  # east  face (x=x1)
        ]

        for start, end, face_axis, _ in perim_segments:
            if door and door["axis"] == face_axis:
                emit_face_with_door(start, end, door, floor_y, ceiling_y, col)
            else:
                emit_face_quad(start, end, floor_y, ceiling_y, col)

        # Block perimeter (start, end) tuples for collision.
        block_perimeters.append([(s, e) for s, e, _, _ in perim_segments])

    # ── Thin walls (single-plane, two-sided render, flush door support) ─
    # Each thin wall emits its visual panels TWICE (once with each normal)
    # so it reads from both sides. For collision, we emit each panel as
    # a single two-sided segment via the existing interior_walls path —
    # so the door panel sits flush with the wall plane (no thickness gap).
    thin_collision_segments = []
    for idx, wall_cfg in enumerate(thin_walls):
        sx, sz = wall_cfg["start"]
        ex, ez = wall_cfg["end"]
        col = block_palette[(len(wall_blocks) + idx) % len(block_palette)]
        door = wall_cfg.get("door")
        assert sz == ez, "thin walls must be Z-axis (sz == ez)"

        # Inward normals — for two-sided we render both and shade them
        # differently so the wall reads from either side.
        dx = ex - sx
        n_a = (0, 0, 1) if dx > 0 else (0, 0, -1)
        n_b = tuple(-c for c in n_a)

        def emit_side(p_start, p_end, y_min, y_max, normal):
            sx_, sz_ = p_start
            ex_, ez_ = p_end
            push_quad([
                (sx_, y_min, sz_), (ex_, y_min, ez_),
                (ex_, y_max, ez_), (sx_, y_max, sz_),
            ], shade(col, normal))

        if door is None:
            emit_side((sx, sz), (ex, ez), floor_y, ceiling_y, n_a)
            emit_side((ex, ez), (sx, sz), floor_y, ceiling_y, n_b)
        else:
            # Door cutout: split into left/lintel/right, emit each side.
            cx = door["x"]
            hw = door["half_width"]
            door_top = floor_y + door["height"]
            x_lo, x_hi = sorted((sx, ex))
            d_lo, d_hi = cx - hw, cx + hw
            panels = [
                ((x_lo, sz),  (d_lo, sz),  floor_y, ceiling_y),  # left, full height
                ((d_lo, sz),  (d_hi, sz),  door_top, ceiling_y), # lintel
                ((d_hi, sz),  (x_hi, sz),  floor_y, ceiling_y),  # right, full height
            ]
            for p_start, p_end, y0, y1 in panels:
                if p_start == p_end:
                    continue
                emit_side(p_start, p_end, y0, y1, n_a)
                # Other side: reverse start/end for opposite winding.
                emit_side(p_end, p_start, y0, y1, n_b)

        # Collision: thin wall blocks from both sides — feed the existing
        # interior_walls path which emits two-sided polys per segment.
        thin_collision_segments.append(((sx, sz), (ex, ez)))

    floor_rects = [(x_min, x_max, z_min, z_max)]
    return (verts, colors, n_faces, floor_rects, outer_perimeter,
            block_perimeters, thin_collision_segments)


def build_mesh_lab_o2r(output_path: Path | str, layout: str = "empty") -> Path:
    """Build a Mesh Lab .o2r — a single-room sandbox for custom geometry.

    Lives in its own `scenes/squadala_mesh_lab/` namespace so swapping
    experiments only evicts the lab's resources, never the full dungeon's.
    No actors (only Link's spawn), no transition actors, no decorations —
    just the room geometry. Pick the shape with `layout`.

    Layouts:
        - "empty":   single rectangular box, 2000 × 800 × 3000.
        - "l_shape": L-shape with a right-angle turn at the north end. South
                      arm is 600×600×1000, east arm sticks out 600×600×400.
        - "maze":    Z-zigzag maze, 800×600×1000, with a small chest
                      (small-key reward) and a big chest behind a locked
                      door. Switch-flag tracks the unlock so the door stays
                      open after first use.
    """
    import zipfile

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    TARGET = "scenes/squadala_mesh_lab"
    SCENE_PATH = f"{TARGET}/dungeon_scene"
    COLLISION_PATH = f"{TARGET}/collision"
    ROOM_PATH = f"{TARGET}/room_0"
    ROOM_VTX_PATH = f"{TARGET}/room0_Vtx"
    ROOM_DL_PATH = f"{TARGET}/room0_DL"

    actors: list[dict] = []
    transition_actors: list[dict] = []
    spawn_rot_y = 0x8000  # default: facing -Z (north)

    if layout == "empty":
        HALF_W, FULL_H, HALF_D = 1000, 800, 1500
        verts, cols, n_faces = build_box_vertices(w=HALF_W, h=FULL_H, d=HALF_D)
        collision = build_collision(
            min_x=-HALF_W, max_x=HALF_W, floor_y=-100, h=FULL_H,
            min_z=-HALF_D, max_z=HALF_D,
        )
        spawn = (0, 0, HALF_D - 200)
        shape_desc = f"empty {2 * HALF_W}×{FULL_H}×{2 * HALF_D}"
    elif layout == "l_shape":
        FLOOR_Y, ROOM_H = -100, 600
        # Arm A south, Arm B east at the NORTH end so the corner is in
        # front of the player on entry (spawn faces -Z = north).
        arm_a = {"x_range": (-300,  300), "z_range": (-500,  500)}  # south arm
        arm_b = {"x_range": ( 300,  900), "z_range": (-500, -100)}  # east arm (north)
        verts, cols, n_faces, floor_rects, perimeter = _build_l_shape_geometry(
            arm_a, arm_b, floor_y=FLOOR_Y, h=ROOM_H,
        )
        collision = _build_l_shape_collision(floor_rects, perimeter, FLOOR_Y, ROOM_H)
        spawn = (0, 0, 400)  # south arm, near the south wall, facing -Z (north)
        shape_desc = "L-shape (south arm 600×600×1000 + east arm 600×600×400 at north)"
    elif layout == "maze":
        # v1 maze — thin partition walls, simple Z-zigzag with locked door.
        # User confirmed this layout works; keeping it as the baseline.
        FLOOR_Y, ROOM_H = -100, 600
        bounds = {"x_range": (-400, 400), "z_range": (-500, 500)}
        DOOR_X, DOOR_Z = 200, -100
        DOOR_HALF_W, DOOR_HEIGHT = 30, 100
        interior_walls = [
            {"start": (-100,  100), "end": ( 400,  100)},
            {"start": (-400, DOOR_Z), "end": ( 400, DOOR_Z),
             "door": {"x": DOOR_X, "half_width": DOOR_HALF_W,
                       "height": DOOR_HEIGHT}},
        ]
        verts, cols, n_faces, floor_rects, outer_perim = _build_maze_geometry(
            bounds, interior_walls, floor_y=FLOOR_Y, h=ROOM_H,
        )
        collision_walls = [(w["start"], w["end"]) for w in interior_walls]
        collision = _build_l_shape_collision(
            floor_rects, outer_perim, FLOOR_Y, ROOM_H,
            interior_walls=collision_walls,
        )
        spawn = (0, 0, 400)
        LOCKED_DOOR_PARAMS = (1 << 7) | 0x3F
        transition_actors = [
            {"actor_name": "en_door",
             "front_room": 0, "back_room": 0,
             "x": DOOR_X, "y": FLOOR_Y, "z": DOOR_Z,
             "rot_y": 0x0000,
             "params": LOCKED_DOOR_PARAMS},
        ]
        actors = [
            {"name": "chest", "x":    0, "y": FLOOR_Y, "z":    0,
             "rot_y": 0x0000,
             "params": chest_params(chest_type=ENBOX_TYPE_SMALL,
                                     item_id=GI_KEY_SMALL,
                                     treasure_flag=10)},
            {"name": "chest", "x":    0, "y": FLOOR_Y, "z": -300,
             "rot_y": 0x0000,
             "params": chest_params(chest_type=ENBOX_TYPE_BIG_DEFAULT,
                                     item_id=GI_HEART_PIECE,
                                     treasure_flag=11)},
        ]
        shape_desc = ("maze v1 — 800×600×1000, thin partitions, small chest "
                      "(key) → locked door → big chest")
    elif layout == "maze_complex":
        # v2 maze — thick-walled blocks (no spitze plane edges), more
        # branching corridors. Pulled in 1 unit from the outer walls so
        # the block faces don't coincide with the maze perimeter (which
        # would generate stacked collision polys at the same plane).
        FLOOR_Y, ROOM_H = -100, 600
        bounds = {"x_range": (-500, 500), "z_range": (-500, 500)}
        T = 30          # thickness for partitions ending in open corridor
        DOOR_X = 250
        DOOR_HALF_W = 30
        DOOR_HEIGHT = 100
        DOOR_Z = -250

        # Partitions that END in open corridor space are THICK blocks so
        # their endpoints don't expose a thin-plane edge.
        wall_blocks = [
            # W1 — barrier at z≈335, gap on east (x > +200)
            {"rect": (-499, 200, 335, 335 + T)},
            # W2 — barrier at z≈155, gap on west (x < -200)
            {"rect": (-200, 499, 155, 155 + T)},
            # W3 — barrier at z≈-65, gap on east (x > +200)
            {"rect": (-499, 200, -65, -65 + T)},
            # Stub A — dead-end pocket in the south corridor
            {"rect": (-100, -100 + T, 365 + T, 499)},
            # Stub B — vertical wall forcing a detour in middle-mid section
            {"rect": (100, 100 + T, -240 + 1, -100)},
        ]
        # W4 is THIN single plane so En_Door's panel sits flush (no
        # thickness gap). Endpoints extend ±10 past the outer perimeter
        # so the thin-plane edges hide behind the outer west/east walls.
        thin_walls = [
            {"start": (-510, DOOR_Z), "end": (510, DOOR_Z),
             "door": {"x": DOOR_X, "half_width": DOOR_HALF_W,
                       "height": DOOR_HEIGHT}},
        ]

        (verts, cols, n_faces, floor_rects, outer_perim, block_perims,
         thin_segs) = _build_thick_maze(
            bounds, wall_blocks, FLOOR_Y, ROOM_H, thin_walls=thin_walls,
        )

        # Thick block perimeters use the same right-hand convention as the
        # outer perimeter (single-sided poly, normal toward maze interior)
        # → concatenate with outer_perim. Thin walls are two-sided → feed
        # the interior_walls path.
        combined_outer = outer_perim + [
            seg for bp in block_perims for seg in bp
        ]
        collision = _build_l_shape_collision(
            floor_rects, combined_outer, FLOOR_Y, ROOM_H,
            interior_walls=thin_segs,
        )
        spawn = (0, 0, 450)
        LOCKED_DOOR_PARAMS = (1 << 7) | 0x3E   # different switch flag from v1
        transition_actors = [
            {"actor_name": "en_door",
             "front_room": 0, "back_room": 0,
             "x": DOOR_X, "y": FLOOR_Y, "z": DOOR_Z,
             "rot_y": 0x0000,
             "params": LOCKED_DOOR_PARAMS},
        ]
        actors = [
            {"name": "chest", "x": -350, "y": FLOOR_Y, "z":   60,
             "rot_y": 0x0000,
             "params": chest_params(chest_type=ENBOX_TYPE_SMALL,
                                     item_id=GI_KEY_SMALL,
                                     treasure_flag=12)},
            {"name": "chest", "x":    0, "y": FLOOR_Y, "z": -400,
             "rot_y": 0x0000,
             "params": chest_params(chest_type=ENBOX_TYPE_BIG_DEFAULT,
                                     item_id=GI_HEART_PIECE,
                                     treasure_flag=13)},
        ]
        shape_desc = ("maze v2 complex — 1000×600×1000 thick-walled, 4 "
                      "barriers + 2 dead-end stubs, small chest (key) → "
                      "locked door → big chest")
    else:
        raise ValueError(f"Unknown mesh-lab layout: {layout!r}")

    # Union of object IDs required by every actor + transition actor — keeps
    # En_Door and chests rendering even though the lab is a single-room
    # scene (so func_80031A28 doesn't sweep them at load).
    shared_objects: set[int] = set()
    for ta in transition_actors:
        if ta["actor_name"] in ACTOR_LIBRARY:
            shared_objects.update(ACTOR_LIBRARY[ta["actor_name"]][2])
    for a in actors:
        if a["name"] in ACTOR_LIBRARY:
            shared_objects.update(ACTOR_LIBRARY[a["name"]][2])

    faces = build_box_faces(n_faces)
    vtx_res = build_vtx_resource(verts, cols)
    dl_res = build_display_list(ROOM_VTX_PATH, len(verts), faces)
    room_res = build_room_header(
        ROOM_DL_PATH, actors=actors,
        extra_object_ids=sorted(shared_objects),
    )

    scene_header = build_scene_header(
        ROOM_PATH, COLLISION_PATH,
        room_size=len(room_res),
        transition_actors=transition_actors,
        spawn_pos=spawn,
        spawn_rot_y=spawn_rot_y,
    )

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as oz:
        oz.writestr(ROOM_VTX_PATH, vtx_res)
        oz.writestr(ROOM_DL_PATH, dl_res)
        oz.writestr(ROOM_PATH, room_res)
        oz.writestr(COLLISION_PATH, collision)
        oz.writestr(SCENE_PATH, scene_header)

    size = output.stat().st_size
    print(f"Mesh Lab [{layout}]: {shape_desc} → {output} ({size}B)")
    return output


def build_custom_dungeon_o2r(output_path: Path | str) -> Path:
    """Build a "simple custom dungeon" .o2r — single empty box in its own
    `scenes/squadala_custom/` namespace, used as the default landing scene
    for the Door_Warp1 entry-portal flow. Independent of both the 3-room
    debug dungeon (`scenes/squadala/`) and the mesh-lab experiments
    (`scenes/squadala_mesh_lab/`) so loading any of them never evicts the
    others. No actors, no decorations, no auto-exit-portal — just a clean
    room you can walk around in to verify the warp-in landing works.
    """
    import zipfile

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    TARGET = "scenes/squadala_custom"
    SCENE_PATH = f"{TARGET}/dungeon_scene"
    COLLISION_PATH = f"{TARGET}/collision"
    ROOM_PATH = f"{TARGET}/room_0"
    ROOM_VTX_PATH = f"{TARGET}/room0_Vtx"
    ROOM_DL_PATH = f"{TARGET}/room0_DL"

    # Match the empty mesh-lab dimensions — a reasonable "dungeon antechamber"
    # for now. Easy to swap with LLM-compiled content later.
    HALF_W, FULL_H, HALF_D = 1000, 800, 1500
    verts, cols, n_faces = build_box_vertices(w=HALF_W, h=FULL_H, d=HALF_D)
    collision = build_collision(
        min_x=-HALF_W, max_x=HALF_W, floor_y=-100, h=FULL_H,
        min_z=-HALF_D, max_z=HALF_D,
    )
    faces = build_box_faces(n_faces)
    vtx_res = build_vtx_resource(verts, cols)
    dl_res = build_display_list(ROOM_VTX_PATH, len(verts), faces)
    room_res = build_room_header(ROOM_DL_PATH, actors=[])

    scene_header = build_scene_header(
        ROOM_PATH, COLLISION_PATH,
        room_size=len(room_res),
        spawn_pos=(0, 0, HALF_D - 200),
        spawn_rot_y=0x8000,
    )

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as oz:
        oz.writestr(ROOM_VTX_PATH, vtx_res)
        oz.writestr(ROOM_DL_PATH, dl_res)
        oz.writestr(ROOM_PATH, room_res)
        oz.writestr(COLLISION_PATH, collision)
        oz.writestr(SCENE_PATH, scene_header)

    size = output.stat().st_size
    print(f"Custom Dungeon: empty {2 * HALF_W}×{FULL_H}×{2 * HALF_D} under "
          f"{TARGET}/ → {output} ({size}B)")
    return output


def main():
    """Standalone CLI — builds the M7 step-1 test layout: 2 rooms side-by-side
    with the shared east/west wall removed (open passage). No transition actor
    yet, so the room transition isn't fired — but you should be able to see
    Room 1 through the gap and walk into it on the vanilla collision floor.

    Pass `--single` to build the v0.6 single-room baseline instead.
    Pass `--mesh-lab` to build the empty Mesh Lab sandbox .o2r alongside.
    """
    import sys
    output = Path.home() / "workspace/SoH/soh-source/build-cmake/soh/debug_rooms/zzz_squadala_dungeon.o2r"

    # `--mesh-lab` builds every lab layout into its own .o2r so the panel's
    # experiment dropdown can switch between them without rebuilding. The
    # layout name is embedded in the output filename and matched against
    # LiveGenPanel's experiment table.
    if "--mesh-lab" in sys.argv:
        for layout in ("empty", "l_shape", "maze", "maze_complex"):
            lab_output = output.with_name(f"zzz_mesh_lab_{layout}.o2r")
            build_mesh_lab_o2r(lab_output, layout=layout)
        return

    if "--custom-dungeon" in sys.argv:
        cd_output = output.with_name("zzz_squadala_custom_dungeon.o2r")
        build_custom_dungeon_o2r(cd_output)
        return

    if "--single" in sys.argv:
        build_dungeon_o2r(output, actors=None)
        print("Complete override: Scene + Room + DL + VTX + Collision (single)")
        return

    # M7 step-3a: two rooms with door-cutout collision. Visual mesh has a
    # door hole in the shared wall (M7-2); collision matches it — Link is
    # blocked from walking through the wall except through the door
    # opening. Still no transition actor, so room culling won't switch
    # between rooms yet.
    # En_Holl side stays at the wider 120×200 opening — the invisible plane
    # triggers fade-curtain at that size and the user has confirmed it reads
    # correctly. En_Door side is much smaller because the visible door panel
    # (gDoorLeftDL ≈ 60 wide × 100 tall) needs to fully cover the wall hole;
    # otherwise you see a black frame around the door before the open
    # cutscene starts and can peek into the next room as soon as the panel
    # begins swinging.
    DOOR_SPEC_HOLL = {"half_width": 60, "height": 200}
    DOOR_SPEC_DOOR = {"half_width": 30, "height": 100}
    # Room 1 actors (offset +1200 X, world coords). Sonic chest reward.
    room1_actors = [
        {"name": "pot", "x":  800, "y": -100, "z": -400},
        {"name": "pot", "x": 1600, "y": -100, "z": -400},
        {"name": "pot", "x": 1600, "y": -100, "z":  400},
        {"name": "pot", "x":  800, "y": -100, "z":  400},
        {"name": "chest", "x": 1500, "y": -100, "z": 0,
         "rot_y": 0x4000,  # rotated 180° from 0xC000 — chest faces +X now
         "params": chest_params(item_id=GI_LIVEGEN_SONIC, treasure_flag=2)},
        {"name": "keese", "x": 1300, "y":   50, "z": -200},
        {"name": "keese", "x": 1500, "y":   50, "z":  300},
    ]
    # Room 2 actors (offset -1200 X). Saber chest reward.
    room2_actors = [
        {"name": "pot",   "x": -1600, "y": -100, "z": -400},
        {"name": "pot",   "x":  -800, "y": -100, "z": -400},
        {"name": "pot",   "x":  -800, "y": -100, "z":  400},
        {"name": "pot",   "x": -1600, "y": -100, "z":  400},
        {"name": "chest", "x": -1500, "y": -100, "z": 0,
         "rot_y": 0xC000,  # facing -X (away from door) — same convention as Sonic
         "params": chest_params(item_id=GI_LIVEGEN_HYDRANT, treasure_flag=5)},
        {"name": "keese", "x": -1300, "y":   50, "z":  300},
        {"name": "keese", "x": -1500, "y":   50, "z": -200},
    ]
    rooms = [
        {
            "actors": _resolve_default_actors(),
            "offset": (0, 0, 0),
            # East = En_Holl (Room 1), West = En_Door (Room 2) — different
            # opening sizes per side so each transition's visual fits.
            "doors": {"east": DOOR_SPEC_HOLL, "west": DOOR_SPEC_DOOR},
        },
        {
            "actors": room1_actors,
            "offset": (1200, 0, 0),         # 2*w east of room 0 → walls coincide at x=+600
            "doors": {"west": DOOR_SPEC_HOLL},
        },
        {
            "actors": room2_actors,
            "offset": (-1200, 0, 0),        # 2*w west of room 0 → walls coincide at x=-600
            "doors": {"east": DOOR_SPEC_DOOR},
        },
    ]
    # Inner walls — collision treatment differs by transition actor:
    #   - En_Holl: invisible plane trigger, Link walks through the hole.
    #     The collision needs a matching cutout so he can pass.
    #   - En_Door: visible door + cutscene-driven transition. The actor has
    #     no collision of its own; the wall around the door does the
    #     blocking, the cutscene + transition handle the actual move. So
    #     this wall stays solid (no door cutout).
    inner_walls = [
        {"x":  600, "z_range": (-1500, 1500), "door": DOOR_SPEC_HOLL},  # En_Holl side
        {"x": -600, "z_range": (-1500, 1500)},                          # En_Door side (solid)
    ]
    # Two transition actors: En_Holl (invisible) for R0↔R1, En_Door (visible
    # wood door, A-press cutscene) for R0↔R2. Both placed at floor level so
    # Link's actor-local Y stays in the trigger range (PLANE_Y_MIN=-50,
    # PLANE_Y_MAX=200 are checked against link.y - actor.y).
    transition_actors = [
        {"actor_name": "en_holl", "front_room": 0, "back_room": 1,
         "x":  600, "y": -100, "z": 0,
         "rot_y": 0x4000,
         "params": 0x0000},
        {"actor_name": "en_door", "front_room": 0, "back_room": 2,
         "x": -600, "y": -100, "z": 0,
         "rot_y": 0xC000,  # facing -X — door opens away from Room 0
         # params=0 → door type 0, normal openable wood door. Loads
         # gameplay_keep (auto-included for every scene) for the mesh; the
         # OBJECT_GAMEPLAY_FIELD_KEEP we declare in the room ObjectList
         # exists for door types that explicitly need it (5, 6, …) but
         # those turned out to spawn talking signs in our setup.
         "params": 0x0000},
    ]
    # Spawn Link near the south end of Room 0 facing north — same "front of
    # the room" position v0.x had before the multi-room rework moved him
    # to centre. With chest at the centre this gives a nicer first view.
    build_dungeon_o2r(output, rooms=rooms, inner_walls=inner_walls,
                      transition_actors=transition_actors,
                      spawn_pos=(0, 0, 1300), spawn_rot_y=0x8000)
    print(f"Complete override: Scene + {len(rooms)} Rooms + DLs + VTXs "
          f"+ Collision + {len(transition_actors)} TransitionActors")


if __name__ == "__main__":
    main()
