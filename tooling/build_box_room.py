"""Build a custom box room as .o2r and override Deku Tree Room 0.

This is the GEOMETRY TEST — proving we can render our own 3D mesh in SoH.
"""

import math
import struct
import zipfile
from pathlib import Path

# ============================================================
# N64 GBI opcodes (F3DEX2)
# ============================================================
G_VTX = 0x01
G_TRI2 = 0x06
G_TRI1 = 0x05
G_ENDDL = 0xDF
G_SETGEOMETRYMODE = 0xD9
G_CLEARGEOMETRYMODE = 0xD8
G_SETCOMBINE = 0xFC
G_RDPPIPESYNC = 0xE7
G_SETOTHERMODE_L = 0xE2
G_SETOTHERMODE_H = 0xE3
G_TEXTURE = 0xD7

# OTR extensions
G_VTX_OTR_FILEPATH = 0x01  # Custom opcode for OTR vertex loading
G_VTX_OTR_HASH = 0x01

# Geometry mode flags
G_ZBUFFER = 0x00000001
G_SHADE = 0x00000004
G_CULL_BACK = 0x00002000
G_LIGHTING = 0x00020000
G_SHADING_SMOOTH = 0x00200000


def gfx(w0, w1):
    return struct.pack('>II', w0, w1)


def build_box_vertices(w=500, h=600, d=500):
    """8 vertices for a box room."""
    return [
        (-w, 0, -d), (w, 0, -d), (w, 0, d), (-w, 0, d),
        (-w, h, -d), (w, h, -d), (w, h, d), (-w, h, d),
    ]


def build_box_faces():
    """12 triangles for 6 faces of a box."""
    return [
        (0, 2, 1), (0, 3, 2),  # floor
        (4, 5, 6), (4, 6, 7),  # ceiling
        (0, 1, 5), (0, 5, 4),  # front
        (2, 3, 7), (2, 7, 6),  # back
        (3, 0, 4), (3, 4, 7),  # left
        (1, 2, 6), (1, 6, 5),  # right
    ]


def build_vtx_resource(vertices):
    """Build vertex data as SoH OTEX resource with XETV magic."""
    # Actually, SoH vertex resources don't have their own magic —
    # they're loaded via the DL's OTR path system.
    # Let's build raw N64 Vtx data instead.
    data = bytearray()
    for i, (x, y, z) in enumerate(vertices):
        # Color based on which face group
        if i < 4:  # floor vertices
            r, g, b = 120, 180, 120  # green floor
        else:  # ceiling vertices
            r, g, b = 100, 100, 140  # blue ceiling
        data += struct.pack('>hhhH', x, y, z, 0)  # pos + flag
        data += struct.pack('>hh', 0, 0)  # tex coords (no texture)
        data += struct.pack('BBBB', r, g, b, 255)
    return bytes(data)


def build_display_list_inline(vertices, faces):
    """Build a self-contained F3DEX2 display list with inline vertices."""
    dl = bytearray()

    # PipeSync
    dl += gfx(G_RDPPIPESYNC << 24, 0)

    # SetGeometryMode
    mode = G_ZBUFFER | G_SHADE | G_SHADING_SMOOTH | G_CULL_BACK
    dl += gfx(G_CLEARGEOMETRYMODE << 24, 0xFFFFFFFF)
    dl += gfx(G_SETGEOMETRYMODE << 24, mode)

    # SetCombineMode — shade only (vertex colors, no texture)
    dl += gfx(0xFC127E03, 0xFFFFF3F8)

    # Vertex load — we need the OTR filepath approach
    # gSPVertex with OTR path: 2 commands (16 bytes)
    # Command 1: G_VTX_OTR_FILEPATH(0x01) << 24 | path pointer
    # Command 2: vtxCount | (bufferIndex << 16) | dataOffset
    # For inline, we'll try the standard vertex load
    n = len(vertices)
    dl += gfx(
        (G_VTX << 24) | (n << 12) | n,
        0  # This needs to be a valid address — problematic for custom geometry
    )

    # Triangles
    for i in range(0, len(faces), 2):
        f1 = faces[i]
        if i + 1 < len(faces):
            f2 = faces[i + 1]
            dl += gfx(
                (G_TRI2 << 24) | (f1[0] * 2 << 16) | (f1[1] * 2 << 8) | (f1[2] * 2),
                (f2[0] * 2 << 16) | (f2[1] * 2 << 8) | (f2[2] * 2)
            )
        else:
            dl += gfx(
                (G_TRI1 << 24) | (f1[0] * 2 << 16) | (f1[1] * 2 << 8) | (f1[2] * 2),
                0
            )

    # End
    dl += gfx(G_ENDDL << 24, 0)

    return bytes(dl)


def build_dl_resource(dl_data, ucode=4):
    """Wrap DL in TLDO resource."""
    header = bytearray(0x40)
    header[4:8] = b'TLDO'
    struct.pack_into('<I', header, 0x0C, 0xDEADBEEF)
    struct.pack_into('<I', header, 0x10, 0xDEADBEEF)

    body = bytearray()
    body += struct.pack('B', ucode)  # F3DEX2
    while (len(body) + 0x40) % 8 != 0:
        body += b'\x00'
    body += dl_data

    return bytes(header) + bytes(body)


def build_room_header(dl_path, vtx_path):
    """Build room header that references our custom DL."""

    def write_str(s):
        b = s.encode('utf-8') + b'\x00'
        return struct.pack('<I', len(b)) + b

    header = bytearray(0x40)
    header[4:8] = b'MORO'
    struct.pack_into('<I', header, 0x0C, 0xDEADBEEF)
    struct.pack_into('<I', header, 0x10, 0xDEADBEEF)

    cmds = bytearray()
    n = 0

    # EchoSettings
    cmds += struct.pack('<i', 22); cmds += bytes([0x07]); n += 1
    # RoomBehavior
    cmds += struct.pack('<i', 8); cmds += struct.pack('<bI', 1, 0); n += 1
    # SkyboxModifier (indoor)
    cmds += struct.pack('<i', 18); cmds += bytes([1, 1]); n += 1
    # TimeSettings (frozen)
    cmds += struct.pack('<i', 16); cmds += bytes([0xFF, 0xFF, 0]); n += 1

    # SetMesh Type 0 — our custom DL
    cmds += struct.pack('<i', 10)
    cmds += bytes([0, 0, 1, 0])  # data=0, type=0, polyNum=1, polyType=0
    cmds += write_str(dl_path)
    cmds += write_str("")  # no translucent
    n += 1

    # ObjectList
    cmds += struct.pack('<i', 11)
    cmds += struct.pack('<I', 1)
    cmds += struct.pack('<H', 0x0001)  # gameplay_keep
    n += 1

    # ActorList — a few pots to prove it works
    cmds += struct.pack('<i', 1)
    cmds += struct.pack('<I', 3)
    for angle_idx in range(3):
        angle = (2 * math.pi * angle_idx) / 3
        x = int(300 * math.cos(angle))
        z = int(300 * math.sin(angle))
        cmds += struct.pack('<hhhhhhhH', 0x0111, x, 0, z, 0, 0, 0, 0)
    n += 1

    # EndMarker
    cmds += struct.pack('<i', 20); n += 1

    return bytes(header) + struct.pack('<I', n) + bytes(cmds)


def build_collision(w=500, h=600, d=500):
    """Simple flat floor collision."""
    header = bytearray(0x40)
    header[4:8] = b'LOCO'
    struct.pack_into('<I', header, 0x0C, 0xDEADBEEF)
    struct.pack_into('<I', header, 0x10, 0xDEADBEEF)

    body = bytearray()
    body += struct.pack('<hhh', -w, 0, -d)  # min
    body += struct.pack('<hhh', w, h, d)     # max

    verts = [(-w, 0, -d), (w, 0, -d), (w, 0, d), (-w, 0, d)]
    body += struct.pack('<i', len(verts))
    for v in verts:
        body += struct.pack('<hhh', *v)

    polys = [(0, 0, 1, 2), (0, 0, 2, 3)]
    body += struct.pack('<I', len(polys))
    for t, a, b, c in polys:
        body += struct.pack('<HHHHhhhh', t, a, b, c, 0, 0x7FFF, 0, 0)

    body += struct.pack('<I', 1); body += struct.pack('<II', 0, 0)  # surface type
    body += struct.pack('<I', 0)  # camData
    body += struct.pack('<i', 0)  # camPosData
    body += struct.pack('<i', 0)  # waterBoxes

    return bytes(header) + bytes(body)


def main():
    TARGET = "scenes/nonmq/ydan_scene"
    DL_NAME = f"{TARGET}/squadala_box_DL"
    VTX_NAME = f"{TARGET}/squadala_box_Vtx"

    vertices = build_box_vertices()
    faces = build_box_faces()

    # Build resources
    vtx_data = build_vtx_resource(vertices)
    dl_data = build_display_list_inline(vertices, faces)
    dl_resource = build_dl_resource(dl_data)
    collision = build_collision()

    # Build room that references our DL
    room = build_room_header(DL_NAME, VTX_NAME)

    output = Path.home() / "workspace/SoH/soh-source/build-cmake/soh/mods/zzz_squadala_dungeon.o2r"

    with zipfile.ZipFile(str(output), 'w', zipfile.ZIP_STORED) as oz:
        # Our custom DL
        oz.writestr(DL_NAME, dl_resource)
        print(f"DL: {len(dl_resource)} bytes → {DL_NAME}")

        # Room header pointing to our DL
        oz.writestr(f"{TARGET}/ydan_room_0", room)
        print(f"Room: {len(room)} bytes")

        # Collision
        oz.writestr(f"{TARGET}/ydan_sceneCollisionHeader_00B610", collision)
        print(f"Collision: {len(collision)} bytes")

    print(f"\nOutput: {output} ({output.stat().st_size} bytes)")
    print("Restart SoH → Enter Deku Tree → custom box room!")


if __name__ == "__main__":
    main()
