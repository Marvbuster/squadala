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

def build_box_vertices(w=1500, h=1200, d=1500):
    """RADICAL TEST: just 3 vertices forming one HUGE pink triangle right above Link.

    If we don't see this, our DL isn't rendering at all.
    """
    # 4 triangles in 4 cardinal directions around origin — Link must see ONE of them
    # Each triangle is 800x600, distance 500 from origin in its direction
    verts = []
    colors = []

    # NORTH (-Z): RED
    verts += [(-400, 0, -500), (400, 0, -500), (0, 600, -500)]
    colors += [(255, 0, 0, 255)] * 3

    # SOUTH (+Z): GREEN
    verts += [(-400, 0, 500), (400, 0, 500), (0, 600, 500)]
    colors += [(0, 255, 0, 255)] * 3

    # EAST (+X): BLUE
    verts += [(500, 0, -400), (500, 0, 400), (500, 600, 0)]
    colors += [(0, 100, 255, 255)] * 3

    # WEST (-X): YELLOW
    verts += [(-500, 0, -400), (-500, 0, 400), (-500, 600, 0)]
    colors += [(255, 255, 0, 255)] * 3

    # Pad to 24 (have 12 unique)
    while len(verts) < 24:
        verts.append(verts[0])
        colors.append(colors[0])
    face_data = []

    for v0, v1, v2, v3, col in face_data:
        verts.extend([v0, v1, v2, v3])
        colors.extend([col, col, col, col])

    return verts, colors


def build_box_faces():
    """4 triangles in 4 directions — at least one should be visible from any spawn orientation."""
    return [
        (0, 1, 2),    # north  (red)
        (3, 4, 5),    # south  (green)
        (6, 7, 8),    # east   (blue)
        (9, 10, 11),  # west   (yellow)
    ]


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

    # 3. Set render mode: G_MDSFT_RENDERMODE=3, len=29 (correct shift!)
    cmds += gfx_le(
        (G_SETOTHERMODE_L << 24) | ((32 - 3 - 29) << 8) | (29 - 1),
        RENDERMODE_OPA_SURF_NO_Z
    )

    # 4. Load geometry mode: G_SHADE for vertex colors + smooth interpolation
    geom_flags = G_SHADE | G_SHADING_SMOOTH
    cmds += gfx_le(G_GEOMETRYMODE << 24, geom_flags)

    # 5. Set combiner to G_CC_SHADE (use vertex colors)
    #    Formula: (0-0)*0+SHADE = SHADE for color, same for alpha
    #    GCCc0w1(0,4,0,4)=0x20800, GCCc1w1(0,4,0,0,0,4)=0x104 → w1=0x00020904
    cmds += gfx_le(0xFC000000, 0x00020904)

    # 6. G_VTX_OTR_HASH — load vertices (EXPANDED: 16 bytes!)
    #    Command 1: w0 = opcode|count|bufEnd, w1 = offset
    #    Command 2: w0 = hash_hi, w1 = hash_lo
    buf_idx = 0
    w0_vtx = (G_VTX_OTR_HASH << 24) | (vtx_count << 12) | ((buf_idx + vtx_count) << 1)
    cmds += gfx_le(w0_vtx, 0)  # offset = 0

    hash_hi = (vtx_hash >> 32) & 0xFFFFFFFF
    hash_lo = vtx_hash & 0xFFFFFFFF
    cmds += gfx_le(hash_hi, hash_lo)

    # 7. Triangles — G_TRI2 for pairs, G_TRI1 for leftover
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


def build_room_header(dl_path: str) -> bytes:
    """Build room header with SetMesh Type 0 pointing to our DL."""
    header = build_resource_header(RES_ROOM)

    cmds = bytearray()
    n = 0

    # EchoSettings (ID=22): 1 byte
    cmds += write_cmd_id(22)
    cmds += bytes([0x07])
    n += 1

    # RoomBehavior (ID=8): int8 + int32 = 5 bytes
    cmds += write_cmd_id(8)
    cmds += struct.pack('<bI', 1, 0)
    n += 1

    # SkyboxModifier (ID=18): 2 bytes — indoor (disable sky+sun)
    cmds += write_cmd_id(18)
    cmds += bytes([1, 1])
    n += 1

    # TimeSettings (ID=16): 3 bytes — frozen time
    cmds += write_cmd_id(16)
    cmds += bytes([0xFF, 0xFF, 0])
    n += 1

    # SetMesh (ID=10): Type 0, 1 polygon
    cmds += write_cmd_id(10)
    cmds += struct.pack('b', 0)    # data (unused)
    cmds += struct.pack('b', 0)    # meshType = 0
    cmds += struct.pack('b', 1)    # polyNum = 1
    # Per polygon: polyType + opaPath + xluPath
    cmds += struct.pack('b', 0)    # polyType (unused)
    cmds += write_str(dl_path)     # opaque DL
    cmds += write_str("")          # no translucent DL
    n += 1

    # ObjectList (ID=11): just gameplay_keep
    cmds += write_cmd_id(11)
    cmds += struct.pack('<I', 1)   # count
    cmds += struct.pack('<H', 0x0001)  # gameplay_keep
    n += 1

    # ActorList (ID=1): empty for now (stable test)
    cmds += write_cmd_id(1)
    cmds += struct.pack('<I', 0)
    n += 1

    # EndMarker (ID=20)
    cmds += write_cmd_id(20)
    n += 1

    return header + struct.pack('<I', n) + bytes(cmds)


# ============================================================
# Collision (LOCO) — simple flat floor
# ============================================================

def build_collision(w=4000, h=2000, d=4000) -> bytes:
    """Big flat floor — original Deku Tree spawn could be anywhere, we need wide coverage."""
    header = build_resource_header(RES_COLLISION)

    floor_y = -100  # Floor well below spawn so BgCheck definitely finds it

    body = bytearray()
    # Bounding box
    body += struct.pack('<hhh', -w, floor_y, -d)   # min
    body += struct.pack('<hhh', w, h, d)            # max

    # Vertices
    verts = [(-w, floor_y, -d), (w, floor_y, -d), (w, floor_y, d), (-w, floor_y, d)]
    body += struct.pack('<i', len(verts))
    for v in verts:
        body += struct.pack('<hhh', *v)

    # Polygons (2 triangles for floor)
    # Winding: CCW from above gives +Y normal (walkable floor)
    polys = [(0, 0, 2, 1), (0, 0, 3, 2)]
    body += struct.pack('<I', len(polys))
    for surf_type, a, b, c in polys:
        # type, vIA, vIB, vIC, normalX, normalY, normalZ, dist
        # normalY = 0x7FFF = +1.0 fixed point, dist = floor_y
        body += struct.pack('<HHHHHHHH',
                            surf_type, a, b, c,
                            0, 0x7FFF, 0,
                            (-floor_y) & 0xFFFF)

    # Surface types
    body += struct.pack('<I', 1)
    body += struct.pack('<II', 0, 0)  # one surface type entry

    # Camera data: 1 entry so the camera system doesn't crash on NULL
    body += struct.pack('<I', 1)      # camDataCount = 1
    body += struct.pack('<Hh', 0, 0)  # cameraSType=0, numCameras=0
    body += struct.pack('<i', 0)      # camPosDataIdx = 0

    # Camera position data: 0 entries (factory uses camPosDataZero fallback)
    body += struct.pack('<i', 0)      # camPosCount = 0

    # Water boxes
    body += struct.pack('<i', 0)      # waterBoxCount

    return header + bytes(body)


# ============================================================
# Main — build the .o2r
# ============================================================

def main():
    TARGET = "scenes/nonmq/ydan_scene"
    VTX_PATH = f"{TARGET}/squadala_box_Vtx"

    DL_PATH = f"{TARGET}/squadala_box_DL"
    ROOM_PATH = f"{TARGET}/ydan_room_0"
    COLLISION_PATH = f"{TARGET}/ydan_sceneCollisionHeader_00B610"

    vertices, colors = build_box_vertices()
    faces = build_box_faces()

    vtx_resource = build_vtx_resource(vertices, colors)
    dl_resource = build_display_list(VTX_PATH, len(vertices), faces)
    room_header = build_room_header(DL_PATH)
    collision = build_collision()
    scene_header = build_scene_header(ROOM_PATH, COLLISION_PATH, len(room_header))

    output = Path.home() / "workspace/SoH/soh-source/build-cmake/soh/debug_rooms/zzz_squadala_dungeon.o2r"
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(output), 'w', zipfile.ZIP_STORED) as oz:
        oz.writestr(VTX_PATH, vtx_resource)
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
