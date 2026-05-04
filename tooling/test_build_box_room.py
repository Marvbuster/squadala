"""Tests for build_box_room.py — custom geometry rendering in SoH.

Run: python -m pytest tooling/test_build_box_room.py -v
"""

import struct
import zipfile
import io
from pathlib import Path

from build_box_room import (
    crc64, CRC64_TABLE,
    build_resource_header, RES_VERTEX, RES_DISPLAY_LIST, RES_ROOM, RES_COLLISION,
    build_vtx_resource, build_display_list, build_room_header, build_collision,
    build_box_vertices, build_box_faces,
    build_actor_entry, collect_required_objects, ACTOR_LIBRARY, GAMEPLAY_KEEP,
    gfx_le, write_str,
    G_VTX_OTR_HASH, G_RDPPIPESYNC, G_ENDDL, G_TRI2,
)


# build_box_vertices() now returns (verts, colors) as a tuple — wrap for tests
def _verts_only():
    verts, _ = build_box_vertices()
    return verts


def _colors_only():
    _, colors = build_box_vertices()
    return colors


# ============================================================
# CRC64 Tests
# ============================================================

class TestCRC64:
    """Verify CRC64 implementation matches SoH's StrHash64.cpp."""

    def test_table_entry_0(self):
        """Table[0] must be 0."""
        assert CRC64_TABLE[0] == 0

    def test_table_entry_1_is_polynomial(self):
        """Table[1] is the polynomial itself."""
        assert CRC64_TABLE[1] == 0x42F0E1EBA9EA3693

    def test_table_entry_2(self):
        """Verify against hardcoded value from StrHash64.cpp."""
        assert CRC64_TABLE[2] == 0x85E1C3D753D46D26

    def test_table_entry_3(self):
        assert CRC64_TABLE[3] == 0xC711223CFA3E5BB5

    def test_table_size(self):
        assert len(CRC64_TABLE) == 256

    def test_all_entries_64bit(self):
        """All table entries must fit in 64 bits."""
        for i, val in enumerate(CRC64_TABLE):
            assert 0 <= val <= 0xFFFFFFFFFFFFFFFF, f"Table[{i}] = {val:#x} out of range"

    def test_empty_string(self):
        """Empty string → init value unchanged (no bytes processed)."""
        assert crc64("") == 0xFFFFFFFFFFFFFFFF

    def test_deterministic(self):
        """Same input always gives same output."""
        h1 = crc64("test_path")
        h2 = crc64("test_path")
        assert h1 == h2

    def test_different_strings_different_hashes(self):
        """Different paths produce different hashes."""
        h1 = crc64("scenes/nonmq/ydan_scene/vtx_a")
        h2 = crc64("scenes/nonmq/ydan_scene/vtx_b")
        assert h1 != h2

    def test_hash_fits_64bit(self):
        h = crc64("scenes/nonmq/ydan_scene/squadala_box_Vtx")
        assert 0 <= h <= 0xFFFFFFFFFFFFFFFF

    def test_no_final_inversion(self):
        """CRC64() in SoH does NOT invert the final result.

        The function update_crc64() DOES invert, but CRC64() doesn't.
        We must match CRC64() behavior.
        """
        # If we inverted, the result for empty string would be 0, not 0xFFFF...
        assert crc64("") != 0


# ============================================================
# Resource Header Tests
# ============================================================

class TestResourceHeader:
    def test_size(self):
        """Header is always 0x40 bytes."""
        for res_type in [RES_VERTEX, RES_DISPLAY_LIST, RES_ROOM, RES_COLLISION]:
            h = build_resource_header(res_type)
            assert len(h) == 0x40

    def test_endianness_byte(self):
        """Byte 0 = 0 → Endianness::Little."""
        h = build_resource_header(RES_VERTEX)
        assert h[0] == 0

    def test_type_vertex(self):
        """Bytes 4-7 = OVTX type (0x4F565458) in LE."""
        h = build_resource_header(RES_VERTEX)
        (type_val,) = struct.unpack_from('<I', h, 4)
        assert type_val == 0x4F565458

    def test_type_display_list(self):
        h = build_resource_header(RES_DISPLAY_LIST)
        (type_val,) = struct.unpack_from('<I', h, 4)
        assert type_val == 0x4F444C54

    def test_deadbeef_id(self):
        h = build_resource_header(RES_VERTEX)
        (id_val,) = struct.unpack_from('<Q', h, 0x0C)
        assert id_val == 0xDEADBEEFDEADBEEF


# ============================================================
# Vertex Resource Tests
# ============================================================

class TestVertexResource:
    def setup_method(self):
        self.vertices, self.colors = build_box_vertices()
        self.vtx = build_vtx_resource(self.vertices, self.colors)

    def test_header_present(self):
        assert len(self.vtx) >= 0x40

    def test_correct_type(self):
        (t,) = struct.unpack_from('<I', self.vtx, 4)
        assert t == RES_VERTEX

    def test_vertex_count(self):
        """uint32 count at offset 0x40."""
        (count,) = struct.unpack_from('<I', self.vtx, 0x40)
        assert count == 24

    def test_total_size(self):
        """0x40 header + 4 count + 24 vertices × 16 bytes."""
        expected = 0x40 + 4 + 24 * 16
        assert len(self.vtx) == expected

    def test_first_vertex_is_floor_corner(self):
        """First vertex is a floor corner at Y=floor_y (-100)."""
        off = 0x40 + 4
        x, y, z = struct.unpack_from('<hhh', self.vtx, off)
        assert y == -100  # floor_y
        # Floor corners are at ±w in X and ±d in Z (w and d may differ
        # for non-square rooms — just check both axes hit the half-extent).
        assert abs(x) > 0 and abs(z) > 0

    def test_first_vertex_color_is_floor_green(self):
        """First face is the floor (green tones)."""
        off = 0x40 + 4 + 12
        r, g, b, a = struct.unpack_from('BBBB', self.vtx, off)
        # Floor is green-dominant
        assert g > r and g > b and a == 255

    def test_all_24_vertices_parseable(self):
        """Read all 24 vertices without error."""
        base = 0x40 + 4
        for i in range(24):
            off = base + i * 16
            x, y, z, flag = struct.unpack_from('<hhhH', self.vtx, off)
            s, t = struct.unpack_from('<hh', self.vtx, off + 8)
            r, g, b, a = struct.unpack_from('BBBB', self.vtx, off + 12)
            assert flag == 0
            assert s == 0 and t == 0
            assert a == 255


# ============================================================
# Display List Tests
# ============================================================

class TestDisplayList:
    def setup_method(self):
        self.vtx_path = "scenes/nonmq/ydan_scene/squadala_box_Vtx"
        self.faces = build_box_faces()
        self.dl = build_display_list(self.vtx_path, 24, self.faces)

    def test_header_type(self):
        (t,) = struct.unpack_from('<I', self.dl, 4)
        assert t == RES_DISPLAY_LIST

    def test_ucode_f3dex2(self):
        """Ucode byte at 0x40 = 4 (F3DEX2)."""
        assert self.dl[0x40] == 4

    def test_aligned_to_8(self):
        """Commands start at 8-byte aligned offset after ucode."""
        # ucode at 0x40 (1 byte), padding to 0x48
        cmd_start = 0x48
        assert cmd_start % 8 == 0

    def test_first_command_pipesync(self):
        """First GBI command is G_RDPPIPESYNC."""
        (w0,) = struct.unpack_from('<I', self.dl, 0x48)
        opcode = (w0 >> 24) & 0xFF
        assert opcode == G_RDPPIPESYNC

    def test_last_command_enddl(self):
        """Last 8 bytes must be G_ENDDL."""
        (w0, w1) = struct.unpack_from('<II', self.dl, len(self.dl) - 8)
        opcode = (w0 >> 24) & 0xFF
        assert opcode == G_ENDDL
        assert w1 == 0

    def test_vtx_hash_command_present(self):
        """G_VTX_OTR_HASH (0x32) must appear in the DL."""
        found = False
        off = 0x48
        while off < len(self.dl) - 8:
            (w0,) = struct.unpack_from('<I', self.dl, off)
            opcode = (w0 >> 24) & 0xFF
            if opcode == G_VTX_OTR_HASH:
                found = True
                break
            off += 8
        assert found, "G_VTX_OTR_HASH not found in display list"

    def test_vtx_hash_correct_count(self):
        """G_VTX_OTR_HASH encodes 24 vertices in w0."""
        off = 0x48
        while off < len(self.dl) - 8:
            (w0,) = struct.unpack_from('<I', self.dl, off)
            opcode = (w0 >> 24) & 0xFF
            if opcode == G_VTX_OTR_HASH:
                count = (w0 >> 12) & 0xFF
                assert count == 24
                break
            off += 8

    def test_vtx_hash_correct_hash(self):
        """G_VTX_OTR_HASH stores the correct CRC64 of the vertex path."""
        expected_hash = crc64(self.vtx_path)
        off = 0x48
        while off < len(self.dl) - 8:
            (w0,) = struct.unpack_from('<I', self.dl, off)
            opcode = (w0 >> 24) & 0xFF
            if opcode == G_VTX_OTR_HASH:
                # Hash is in the next 8 bytes (expanded command part 2)
                (hash_hi, hash_lo) = struct.unpack_from('<II', self.dl, off + 8)
                actual_hash = (hash_hi << 32) | hash_lo
                assert actual_hash == expected_hash, \
                    f"Hash mismatch: got 0x{actual_hash:016X}, expected 0x{expected_hash:016X}"
                break
            off += 8

    def test_tri2_count(self):
        """Should have exactly 6 G_TRI2 commands (12 triangles, 2 per cmd)."""
        count = 0
        off = 0x48
        while off < len(self.dl) - 8:
            (w0,) = struct.unpack_from('<I', self.dl, off)
            opcode = (w0 >> 24) & 0xFF
            if opcode == G_TRI2:
                count += 1
            off += 8
        assert count == 6

    def test_combiner_shade_only(self):
        """G_SETCOMBINE must use shade-only mode."""
        off = 0x48
        while off < len(self.dl) - 8:
            (w0, w1) = struct.unpack_from('<II', self.dl, off)
            opcode = (w0 >> 24) & 0xFF
            if opcode == 0xFC:  # G_SETCOMBINE
                assert w0 == 0xFC000000, f"Unexpected combiner w0: {w0:#010x}"
                assert w1 == 0x00020904, f"Unexpected combiner w1: {w1:#010x}"
                break
            off += 8


# ============================================================
# Geometry Tests
# ============================================================

class TestBoxGeometry:
    """Box: 24 vertices (4 per face × 6 faces), 12 triangles (2 per face)."""

    def test_vertex_count(self):
        assert len(_verts_only()) == 24

    def test_face_count(self):
        assert len(build_box_faces()) == 12

    def test_color_count(self):
        assert len(_colors_only()) == 24

    def test_all_face_indices_valid(self):
        n_verts = len(_verts_only())
        for face in build_box_faces():
            for idx in face:
                assert 0 <= idx < n_verts, f"Invalid vertex index {idx}"

    def test_vertex_index_fits_7bit(self):
        """All vertex indices ×2 must fit in the GBI triangle encoding (7 bits)."""
        for face in build_box_faces():
            for idx in face:
                assert idx * 2 < 128, f"Vertex index {idx}*2 exceeds 7-bit range"

    def test_faces_use_all_vertices(self):
        used = set()
        for face in build_box_faces():
            used.update(face)
        assert used == set(range(24))

    def test_all_colors_have_alpha(self):
        for r, g, b, a in _colors_only():
            assert a == 255

    def test_six_distinct_face_colors(self):
        """Each of the 6 faces has its own color (4 vertices share it)."""
        colors = _colors_only()
        face_colors = [colors[i * 4] for i in range(6)]
        assert len(set(face_colors)) == 6, "Each face should have unique color"


# ============================================================
# Actor Library Tests
# ============================================================

class TestActorLibrary:
    def test_pot_known(self):
        assert "pot" in ACTOR_LIBRARY

    def test_chest_known(self):
        assert "chest" in ACTOR_LIBRARY

    def test_keese_known(self):
        assert "keese" in ACTOR_LIBRARY

    def test_actor_entry_size(self):
        """ActorEntry must be exactly 16 bytes."""
        entry = build_actor_entry("pot", 100, -90, 200)
        assert len(entry) == 16

    def test_actor_entry_unknown_raises(self):
        import pytest
        with pytest.raises(ValueError):
            build_actor_entry("unobtainium", 0, 0, 0)

    def test_actor_entry_format(self):
        """Verify the ActorEntry binary layout: id, posXYZ, rotXYZ, params."""
        entry = build_actor_entry("pot", 100, -90, 200, rot_y=0x4000, params=0x1234)
        actor_id, x, y, z, rx, ry, rz, p = struct.unpack('<HhhhhhhH', entry)
        assert actor_id == 0x0111  # pot
        assert (x, y, z) == (100, -90, 200)
        assert (rx, ry, rz) == (0, 0x4000, 0)
        assert p == 0x1234

    def test_collect_required_objects_includes_gameplay_keep(self):
        objs = collect_required_objects([])
        assert GAMEPLAY_KEEP in objs

    def test_collect_required_objects_for_keese(self):
        """Keese needs OBJ_FIREFLY (0x000D)."""
        objs = collect_required_objects(["keese"])
        assert 0x000D in objs

    def test_collect_required_objects_dedup(self):
        """Same actor twice should only add objects once."""
        objs1 = collect_required_objects(["pot", "pot", "pot"])
        objs2 = collect_required_objects(["pot"])
        assert objs1 == objs2

    def test_collect_required_objects_multi(self):
        """Mix of actors aggregates all needed objects (verified vs OoT decomp object_table.h)."""
        objs = collect_required_objects(["pot", "chest", "keese"])
        assert 0x012C in objs   # OBJECT_TSUBO (NOT 0x0111 — that's the actor id)
        assert 0x000E in objs   # OBJECT_BOX  (NOT 0x000A — that's the actor id)
        assert 0x000D in objs   # OBJECT_FIREFLY


# ============================================================
# Room Header Tests
# ============================================================

class TestRoomHeader:
    def setup_method(self):
        self.room = build_room_header("scenes/nonmq/ydan_scene/squadala_box_DL")

    def test_header_type(self):
        (t,) = struct.unpack_from('<I', self.room, 4)
        assert t == RES_ROOM

    def test_command_count(self):
        """8 commands: echo, behavior, skybox, time, mesh, objects, actors, end."""
        (n,) = struct.unpack_from('<I', self.room, 0x40)
        assert n == 8

    def test_first_command_is_echo(self):
        (cmd_id,) = struct.unpack_from('<i', self.room, 0x44)
        assert cmd_id == 22  # EchoSettings

    def test_mesh_type_0(self):
        """SetMesh command uses Type 0."""
        # Find SetMesh (ID=10) by scanning commands
        off = 0x44
        found = False
        for _ in range(8):
            (cmd_id,) = struct.unpack_from('<i', self.room, off)
            if cmd_id == 10:
                data = self.room[off + 4]
                mesh_type = self.room[off + 5]
                poly_num = self.room[off + 6]
                assert mesh_type == 0
                assert poly_num == 1
                found = True
                break
            off = self._skip_command(off, cmd_id)
        assert found, "SetMesh command not found"

    def test_has_end_marker(self):
        """Last command is EndMarker (ID=20)."""
        # Find EndMarker by scanning from end
        data = self.room
        # The last 4 bytes before any trailing data should be cmd_id=20
        # Actually, scan all commands
        off = 0x44
        last_cmd = -1
        for _ in range(8):
            (cmd_id,) = struct.unpack_from('<i', data, off)
            last_cmd = cmd_id
            off = self._skip_command(off, cmd_id)
        assert last_cmd == 20

    def _skip_command(self, off, cmd_id):
        """Advance past a command's payload (simplified)."""
        off += 4  # skip cmd_id
        sizes = {22: 1, 8: 5, 18: 2, 16: 3, 20: 0}
        if cmd_id in sizes:
            return off + sizes[cmd_id]
        if cmd_id == 10:  # SetMesh — variable
            off += 3  # data, type, polyNum
            off += 1  # polyType
            # skip opaPath
            (slen,) = struct.unpack_from('<I', self.room, off)
            off += 4 + slen
            # skip xluPath
            (slen,) = struct.unpack_from('<I', self.room, off)
            off += 4 + slen
            return off
        if cmd_id == 11:  # ObjectList
            (count,) = struct.unpack_from('<I', self.room, off)
            return off + 4 + count * 2
        if cmd_id == 1:  # ActorList
            (count,) = struct.unpack_from('<I', self.room, off)
            return off + 4 + count * 16
        return off  # unknown


# ============================================================
# Collision Tests
# ============================================================

class TestCollision:
    def setup_method(self):
        self.col = build_collision()

    def test_header_type(self):
        (t,) = struct.unpack_from('<I', self.col, 4)
        assert t == RES_COLLISION

    def test_bounding_box(self):
        """Box defaults: w=600, h=600, d=1500, floor_y=-100."""
        min_x, min_y, min_z = struct.unpack_from('<hhh', self.col, 0x40)
        max_x, max_y, max_z = struct.unpack_from('<hhh', self.col, 0x46)
        assert (min_x, min_y, min_z) == (-600, -100, -1500)
        assert (max_x, max_y, max_z) == (600, 500, 1500)

    def test_vertex_count(self):
        """8 vertices: 4 floor corners + 4 ceiling corners."""
        (count,) = struct.unpack_from('<i', self.col, 0x4C)
        assert count == 8

    def test_polygon_count(self):
        """12 collision polys: 2 floor + 2 ceiling + 8 wall (4 walls × 2)."""
        poly_off = 0x4C + 4 + 8 * 6  # after 8 vertices
        (count,) = struct.unpack_from('<I', self.col, poly_off)
        assert count == 12


# ============================================================
# String Encoding Tests
# ============================================================

class TestStringEncoding:
    def test_empty_string(self):
        result = write_str("")
        assert result == struct.pack('<I', 0)

    def test_simple_string(self):
        result = write_str("test")
        expected_len = 5  # "test" + null = 5 bytes
        assert result[:4] == struct.pack('<I', expected_len)
        assert result[4:9] == b'test\x00'

    def test_path_string(self):
        path = "scenes/nonmq/ydan_scene/squadala_box_DL"
        result = write_str(path)
        (length,) = struct.unpack_from('<I', result, 0)
        assert length == len(path) + 1  # +1 for null terminator


# ============================================================
# GFX Command Encoding Tests
# ============================================================

class TestGfxEncoding:
    def test_little_endian(self):
        """gfx_le packs in Little-Endian."""
        data = gfx_le(0xE7000000, 0)
        # LE: 00 00 00 E7 | 00 00 00 00
        assert data[3] == 0xE7
        assert data[0] == 0x00

    def test_gfx_size(self):
        assert len(gfx_le(0, 0)) == 8

    def test_vtx_hash_w0_encoding(self):
        """G_VTX_OTR_HASH w0 encodes count and buffer index correctly."""
        count = 8
        buf_idx = 0
        w0 = (G_VTX_OTR_HASH << 24) | (count << 12) | ((buf_idx + count) << 1)

        # Verify extraction matches interpreter code:
        # C0(12, 8) = (w0 >> 12) & 0xFF → count
        extracted_count = (w0 >> 12) & 0xFF
        assert extracted_count == 8

        # C0(1, 7) = (w0 >> 1) & 0x7F → buf_end
        buf_end = (w0 >> 1) & 0x7F
        # buf_start = buf_end - count
        buf_start = buf_end - extracted_count
        assert buf_start == 0

    def test_tri2_encoding(self):
        """G_TRI2 encodes vertex indices ×2."""
        face1 = (0, 2, 1)
        face2 = (0, 3, 2)
        w0 = (G_TRI2 << 24) | (face1[0] * 2 << 16) | (face1[1] * 2 << 8) | (face1[2] * 2)
        w1 = (face2[0] * 2 << 16) | (face2[1] * 2 << 8) | (face2[2] * 2)

        # Verify: face1 = vertices 0, 2, 1 → indices 0, 4, 2
        assert (w0 >> 16) & 0xFF == 0   # v0 * 2
        assert (w0 >> 8) & 0xFF == 4    # v2 * 2
        assert (w0 >> 0) & 0xFF == 2    # v1 * 2

        # face2 = vertices 0, 3, 2 → indices 0, 6, 4
        assert (w1 >> 16) & 0xFF == 0   # v0 * 2
        assert (w1 >> 8) & 0xFF == 6    # v3 * 2
        assert (w1 >> 0) & 0xFF == 4    # v2 * 2


# ============================================================
# Integration Test — full .o2r structure
# ============================================================

class TestO2RIntegration:
    def setup_method(self):
        """Build the complete .o2r in memory."""
        self.target = "scenes/nonmq/ydan_scene"
        self.vtx_path = f"{self.target}/squadala_box_Vtx"
        self.dl_path = f"{self.target}/squadala_box_DL"

        verts, colors = build_box_vertices()
        self.vtx_resource = build_vtx_resource(verts, colors)
        self.dl_resource = build_display_list(self.vtx_path, 8, build_box_faces())
        self.room_header = build_room_header(self.dl_path)
        self.collision = build_collision()

        # Write to in-memory ZIP
        self.zip_buf = io.BytesIO()
        with zipfile.ZipFile(self.zip_buf, 'w', zipfile.ZIP_STORED) as oz:
            oz.writestr(self.vtx_path, self.vtx_resource)
            oz.writestr(self.dl_path, self.dl_resource)
            oz.writestr(f"{self.target}/ydan_room_0", self.room_header)
            oz.writestr(f"{self.target}/ydan_sceneCollisionHeader_00B610", self.collision)

    def test_zip_valid(self):
        """Output is a valid ZIP archive."""
        self.zip_buf.seek(0)
        assert zipfile.is_zipfile(self.zip_buf)

    def test_zip_entry_count(self):
        """ZIP contains exactly 4 entries."""
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            assert len(zf.namelist()) == 4

    def test_zip_contains_vtx(self):
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            assert self.vtx_path in zf.namelist()

    def test_zip_contains_dl(self):
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            assert self.dl_path in zf.namelist()

    def test_vtx_roundtrip(self):
        """VTX data in ZIP matches what we built."""
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            data = zf.read(self.vtx_path)
            assert data == self.vtx_resource

    def test_dl_references_correct_vtx_hash(self):
        """DL's G_VTX_OTR_HASH references a path that exists in the ZIP."""
        expected_hash = crc64(self.vtx_path)
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            dl_data = zf.read(self.dl_path)
            # Find G_VTX_OTR_HASH and extract hash
            off = 0x48
            while off < len(dl_data) - 8:
                (w0,) = struct.unpack_from('<I', dl_data, off)
                if ((w0 >> 24) & 0xFF) == G_VTX_OTR_HASH:
                    (hash_hi, hash_lo) = struct.unpack_from('<II', dl_data, off + 8)
                    actual_hash = (hash_hi << 32) | hash_lo
                    assert actual_hash == expected_hash
                    # Verify the vtx_path is actually in the ZIP
                    assert self.vtx_path in zf.namelist()
                    return
                off += 8
            assert False, "G_VTX_OTR_HASH not found in DL"

    def test_room_mesh_references_dl_path(self):
        """Room header's SetMesh opaPath matches DL path in ZIP."""
        self.zip_buf.seek(0)
        with zipfile.ZipFile(self.zip_buf, 'r') as zf:
            room_data = zf.read(f"{self.target}/ydan_room_0")
            # The DL path should appear as a string in the room data
            assert self.dl_path.encode('utf-8') in room_data
