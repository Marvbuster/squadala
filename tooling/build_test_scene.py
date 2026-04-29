"""Build a minimal test scene for SoH — one box room Link can stand in.

Creates a .o2r ZIP file with:
- Scene header (MORO) with minimal commands
- Room header (MORO) referencing a DL from the base game
- Collision header (LOCO) for a simple flat floor

Uses the Deku Tree entrance room's display lists as placeholder geometry.
"""

import struct
import zipfile
from pathlib import Path

SCENE_NAME = "livegen_test_scene"
SCENE_PATH = f"scenes/shared/{SCENE_NAME}"

# Source room to copy geometry from (Deku Tree room 0)
SOURCE_SCENE = "scenes/nonmq/ydan_scene"
SOURCE_ROOM = "ydan_room_0"


def write_resource_header(magic: bytes) -> bytes:
    """Write the 0x40 byte resource header."""
    header = bytearray(0x40)
    header[4:8] = magic
    struct.pack_into('<I', header, 0x0C, 0xDEADBEEF)
    struct.pack_into('<I', header, 0x10, 0xDEADBEEF)
    return bytes(header)


def write_string(s: str) -> bytes:
    """Write a length-prefixed null-terminated string."""
    encoded = s.encode('utf-8') + b'\x00'
    return struct.pack('<I', len(encoded)) + encoded


def build_scene_header() -> bytes:
    """Build the scene header with minimal commands."""
    header = write_resource_header(b'MORO')
    commands = bytearray()
    cmd_count = 0

    # Command 21: SoundSettings (reverb, nature, seq)
    commands += struct.pack('<i', 21)
    commands += struct.pack('bbb', 3, 0x13, 0x1C)
    cmd_count += 1

    # Command 4: RoomList (1 room)
    commands += struct.pack('<i', 4)
    commands += struct.pack('<I', 1)  # numRooms
    room_path = f"{SCENE_PATH}/{SCENE_NAME}_room_0"
    commands += write_string(room_path)
    commands += struct.pack('<II', 0, 0)  # vromStart, vromEnd
    cmd_count += 1

    # Command 14: TransitionActorList (0 doors for now)
    commands += struct.pack('<i', 14)
    commands += struct.pack('<I', 0)
    cmd_count += 1

    # Command 0: StartPositionList (1 spawn)
    commands += struct.pack('<i', 0)
    commands += struct.pack('<I', 1)  # numSpawns
    # ActorEntry: id=0x00FF (Link), pos=(0,0,0), rot=(0,0,0), params=0x0FFF
    commands += struct.pack('<hhhhhhhH', 0x00FF, 0, 0, 0, 0, 0, 0, 0x0FFF)
    cmd_count += 1

    # Command 6: EntranceList (1 entrance)
    commands += struct.pack('<i', 6)
    commands += struct.pack('<I', 1)
    commands += struct.pack('BB', 0, 0)  # spawn=0, room=0
    cmd_count += 1

    # Command 3: CollisionHeader (path to collision resource)
    commands += struct.pack('<i', 3)
    col_path = f"{SCENE_PATH}/{SCENE_NAME}_sceneCollisionHeader"
    commands += write_string(col_path)
    cmd_count += 1

    # Command 15: LightSettings (1 default light)
    commands += struct.pack('<i', 15)
    commands += struct.pack('<I', 1)
    # 22 bytes: ambientR,G,B, light1DirX,Y,Z, light1R,G,B, fogR,G,B, blendRate, fogNear, fogFar, pad
    commands += bytes([
        0x50, 0x50, 0x50,       # ambient RGB
        0x49, 0x49, 0x49,       # light1 dir
        0xFF, 0xFF, 0xFF,       # light1 RGB
        0x00, 0x00, 0x00,       # fog RGB
        0xFF, 0xFF, 0xFF,       # light2 dir
        0xFF, 0xFF, 0xFF,       # light2 RGB
        0x00, 0x00,             # fogNear, fogFar
        0xE8, 0x03,             # blendRate
    ])
    cmd_count += 1

    # Command 17: SkyboxSettings (indoor, no sky)
    commands += struct.pack('<i', 17)
    commands += struct.pack('BBB', 0, 0, 1)  # sky=0, weather=0, indoor=1
    cmd_count += 1

    # Command 20: EndMarker
    commands += struct.pack('<i', 20)
    cmd_count += 1

    # Assemble: header + cmd_count + commands
    return header + struct.pack('<I', cmd_count) + bytes(commands)


def build_room_header(base_z: zipfile.ZipFile) -> bytes:
    """Build room header that references DLs from the source room."""
    header = write_resource_header(b'MORO')
    commands = bytearray()
    cmd_count = 0

    # Command 22: EchoSettings
    commands += struct.pack('<i', 22)
    commands += struct.pack('B', 7)
    cmd_count += 1

    # Command 8: RoomBehavior (int8 flags + int32 flags2)
    commands += struct.pack('<i', 8)
    commands += struct.pack('<bI', 1, 0)
    cmd_count += 1

    # Command 18: SkyboxModifier (disable sky + sun for indoor)
    commands += struct.pack('<i', 18)
    commands += struct.pack('BB', 1, 1)
    cmd_count += 1

    # Command 16: TimeSettings (frozen)
    commands += struct.pack('<i', 16)
    commands += struct.pack('BBB', 0xFF, 0xFF, 0)
    cmd_count += 1

    # Command 10: SetMesh — reference ONE DL from the source room
    # Use the main opaque DL from Deku Tree room 0
    commands += struct.pack('<i', 10)
    commands += struct.pack('B', 0)   # data
    commands += struct.pack('B', 0)   # type 0 (simple)
    commands += struct.pack('B', 1)   # polyNum = 1

    # One DList entry: polyType + opaPath + xluPath
    commands += struct.pack('B', 0)  # polyType
    opa_path = f"{SOURCE_SCENE}/{SOURCE_ROOM}DL_0033F0"
    commands += write_string(opa_path)
    commands += write_string("")  # no translucent
    cmd_count += 1

    # Command 11: ObjectList (minimal — just doors)
    commands += struct.pack('<i', 11)
    commands += struct.pack('<I', 1)
    commands += struct.pack('<H', 0x0001)  # gameplay_keep
    cmd_count += 1

    # Command 1: ActorList (0 actors for now)
    commands += struct.pack('<i', 1)
    commands += struct.pack('<I', 0)
    cmd_count += 1

    # Command 20: EndMarker
    commands += struct.pack('<i', 20)
    cmd_count += 1

    return header + struct.pack('<I', cmd_count) + bytes(commands)


def build_collision_header() -> bytes:
    """Build a simple flat floor collision (10x10 square)."""
    header = write_resource_header(b'LOCO')
    body = bytearray()

    # Simple box: 500 units wide, 200 units tall
    SIZE = 500
    HEIGHT = 200

    # Bounds
    body += struct.pack('<hhh', -SIZE, 0, -SIZE)       # min
    body += struct.pack('<hhh', SIZE, HEIGHT, SIZE)     # max

    # Vertices: 4 corners of a floor quad + 4 ceiling corners
    vertices = [
        (-SIZE, 0, -SIZE),
        (SIZE, 0, -SIZE),
        (SIZE, 0, SIZE),
        (-SIZE, 0, SIZE),
    ]
    body += struct.pack('<i', len(vertices))
    for v in vertices:
        body += struct.pack('<hhh', *v)

    # Polygons: 2 triangles for the floor
    polygons = [
        (0, 0, 1, 2),  # type=0, vA=0, vB=1, vC=2
        (0, 0, 2, 3),  # type=0, vA=0, vB=2, vC=3
    ]
    body += struct.pack('<I', len(polygons))
    for ptype, vA, vB, vC in polygons:
        # Normal pointing up: (0, 0x7FFF, 0) = (0, 1, 0) in fixed point
        body += struct.pack('<H', ptype)       # type (surface type index)
        body += struct.pack('<H', vA)          # flags_vIA
        body += struct.pack('<H', vB)          # flags_vIB
        body += struct.pack('<H', vC)          # vIC
        body += struct.pack('<hhh', 0, 0x7FFF, 0)  # normal (0,1,0)
        body += struct.pack('<h', 0)           # dist

    # SurfaceTypes: 1 entry (walkable floor)
    body += struct.pack('<I', 1)
    body += struct.pack('<II', 0x00000000, 0x00000000)  # data[1], data[0]

    # CamData: 0 entries
    body += struct.pack('<I', 0)

    # CamPosData: 0 entries
    body += struct.pack('<i', 0)

    # WaterBoxes: 0
    body += struct.pack('<i', 0)

    return header + bytes(body)


def main():
    base_o2r = Path.home() / "Library/Application Support/com.shipofharkinian.soh/oot.o2r"
    output = Path("_raw_data/livegen_test.o2r")
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building test scene: {output}")

    with zipfile.ZipFile(str(base_o2r), 'r') as base_z:
        with zipfile.ZipFile(str(output), 'w', zipfile.ZIP_STORED) as out_z:
            # Scene header
            scene_data = build_scene_header()
            out_z.writestr(f"{SCENE_PATH}/{SCENE_NAME}_scene", scene_data)
            print(f"  Scene header: {len(scene_data)} bytes")

            # Room header
            room_data = build_room_header(base_z)
            out_z.writestr(f"{SCENE_PATH}/{SCENE_NAME}_room_0", room_data)
            print(f"  Room header: {len(room_data)} bytes")

            # Collision
            col_data = build_collision_header()
            out_z.writestr(f"{SCENE_PATH}/{SCENE_NAME}_sceneCollisionHeader", col_data)
            print(f"  Collision: {len(col_data)} bytes")

            # Copy the referenced DL + its vertices + textures from source
            dl_name = f"{SOURCE_SCENE}/{SOURCE_ROOM}DL_0033F0"
            for name in base_z.namelist():
                if name.startswith(f"{SOURCE_SCENE}/{SOURCE_ROOM}"):
                    data = base_z.read(name)
                    out_z.writestr(name, data)

            print(f"  Copied source room data from {SOURCE_ROOM}")

    print(f"\n✓ Output: {output} ({output.stat().st_size // 1024} KB)")
    print(f"\nTo test: copy to SoH mods folder and add entrance override")


if __name__ == "__main__":
    main()
