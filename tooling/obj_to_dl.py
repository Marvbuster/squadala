"""Wavefront .obj/.mtl → SoH OVTX + TLDO display list.

Parses an .obj file with associated .mtl materials, and produces:
- A flat list of (x, y, z, r, g, b, a) vertices — duplicated per-face for sharp edges
- A flat list of (v0, v1, v2) triangle indices

The caller (build_box_room.py) wraps these into OVTX + TLDO resources.

Limits:
- F3DEX2 vertex buffer: 32 entries max — we batch into 30-vertex chunks.
- Output is unindexed: each face has its own 3 vertices with the face's color
  (gives sharp per-face shading, matches Mario-style flat-shaded look).
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ObjMesh:
    """Parsed .obj data ready for DL conversion."""
    vertices: list[tuple[int, int, int, int, int, int, int]]  # (x,y,z, r,g,b,a)
    triangles: list[tuple[int, int, int]]                     # (v0, v1, v2) into vertices


# ============================================================
# .mtl parser
# ============================================================

def parse_mtl(path: Path) -> dict[str, tuple[float, float, float]]:
    """Parse Wavefront .mtl, return {material_name: (r, g, b)} from Kd (diffuse)."""
    materials: dict[str, tuple[float, float, float]] = {}
    current_name: str | None = None
    current_kd = (1.0, 1.0, 1.0)

    with open(path) as f:
        for line in f:
            tokens = line.strip().split()
            if not tokens or tokens[0].startswith("#"):
                continue
            if tokens[0] == "newmtl":
                if current_name:
                    materials[current_name] = current_kd
                current_name = tokens[1]
                current_kd = (1.0, 1.0, 1.0)
            elif tokens[0] == "Kd" and len(tokens) >= 4:
                current_kd = (float(tokens[1]), float(tokens[2]), float(tokens[3]))

        if current_name:
            materials[current_name] = current_kd

    return materials


# ============================================================
# .obj parser
# ============================================================

def parse_obj(obj_path: Path,
              scale: float = 100.0,
              y_offset: float = 0.0,
              rotation_y_degrees: float = 0.0,
              default_color: tuple[int, int, int, int] = (200, 200, 200, 255)) -> ObjMesh:
    """Parse Wavefront .obj file.

    Args:
        obj_path: Path to .obj file. Companion .mtl auto-loaded if `mtllib` directive present.
        scale: Multiplier for vertex coordinates (.obj units → OoT units, typical 100-1000).
        y_offset: Added to Y after scaling (lift the model off the floor).
        rotation_y_degrees: Rotate the model around Y axis by this many degrees
                             (90 = quarter turn clockwise viewed from above).
        default_color: RGBA tuple used when no material is active.

    Returns:
        ObjMesh with flat per-face-colored vertices ready for OVTX/TLDO.
    """
    import math
    rot_rad = math.radians(rotation_y_degrees)
    cos_y = math.cos(rot_rad)
    sin_y = math.sin(rot_rad)
    obj_path = Path(obj_path)
    raw_verts: list[tuple[float, float, float]] = []   # 1-indexed positions from .obj
    triangles: list[tuple[int, int, int, tuple[int, int, int, int]]] = []  # (v0, v1, v2, color)

    materials: dict[str, tuple[float, float, float]] = {}
    current_color = default_color

    with open(obj_path) as f:
        for line in f:
            tokens = line.strip().split()
            if not tokens or tokens[0].startswith("#"):
                continue

            kw = tokens[0]
            if kw == "mtllib":
                mtl = obj_path.parent / tokens[1]
                if mtl.exists():
                    materials = parse_mtl(mtl)
            elif kw == "usemtl":
                name = tokens[1]
                if name in materials:
                    r, g, b = materials[name]
                    current_color = (
                        int(r * 255), int(g * 255), int(b * 255), 255
                    )
                else:
                    current_color = default_color
            elif kw == "v" and len(tokens) >= 4:
                raw_verts.append((float(tokens[1]), float(tokens[2]), float(tokens[3])))
            elif kw == "f":
                # Face: tokens like "1/1/1" or "1//1" or just "1" — we only need v index
                idx = []
                for t in tokens[1:]:
                    parts = t.split("/")
                    idx.append(int(parts[0]) - 1)  # 1-indexed → 0-indexed
                # Triangulate fan: 0-1-2, 0-2-3, 0-3-4...
                for i in range(1, len(idx) - 1):
                    triangles.append((idx[0], idx[i], idx[i + 1], current_color))

    # Flatten: every triangle gets its own 3 unique vertices, each carrying the face color
    # (this gives flat per-face shading like the Mario reference image)
    verts: list[tuple[int, int, int, int, int, int, int]] = []
    out_tris: list[tuple[int, int, int]] = []

    for v0, v1, v2, color in triangles:
        base = len(verts)
        for v_idx in (v0, v1, v2):
            x, y, z = raw_verts[v_idx]
            # Rotate around Y axis: new_x = x*cos + z*sin, new_z = -x*sin + z*cos
            rx = x * cos_y + z * sin_y
            rz = -x * sin_y + z * cos_y
            verts.append((
                int(rx * scale),
                int(y * scale + y_offset),
                int(rz * scale),
                color[0], color[1], color[2], color[3],
            ))
        out_tris.append((base, base + 1, base + 2))

    return ObjMesh(vertices=verts, triangles=out_tris)


# ============================================================
# Quick CLI test
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        mesh = parse_obj(Path(sys.argv[1]), scale=400.0, y_offset=-100.0)
        print(f"Vertices: {len(mesh.vertices)}")
        print(f"Triangles: {len(mesh.triangles)}")
        # Show bounding box
        xs = [v[0] for v in mesh.vertices]
        ys = [v[1] for v in mesh.vertices]
        zs = [v[2] for v in mesh.vertices]
        print(f"Bounds: X=[{min(xs)},{max(xs)}] Y=[{min(ys)},{max(ys)}] Z=[{min(zs)},{max(zs)}]")
        # First 3 vertices
        for i in range(3):
            print(f"  v{i}: {mesh.vertices[i]}")
