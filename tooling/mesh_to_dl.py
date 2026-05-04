"""Universal mesh loader → SoH OVTX + TLDO display list, via trimesh.

Handles any format trimesh supports (.glb, .gltf, .obj, .ply, .stl, ...).
Output is the same flat per-face-colored vertex format as obj_to_dl.py:
each triangle owns 3 unique vertices carrying the face color, giving sharp
N64-style flat shading.

Per-face colors come from the mesh's PBR material (baseColorFactor) when
present; otherwise the supplied default_color is used. Multi-mesh scenes
(e.g. a GLB with sub-primitives like Pizza/Pizza_1/Pizza_2) get merged
into a single (vertices, triangles) pair.
"""

from dataclasses import dataclass
from pathlib import Path
import math


@dataclass
class Mesh:
    """Flat per-face-colored mesh ready for OVTX + TLDO encoding."""
    vertices: list[tuple[int, int, int, int, int, int, int]]  # (x, y, z, r, g, b, a)
    triangles: list[tuple[int, int, int]]                     # (v0, v1, v2) into vertices


def _extract_color(visual, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Pull an RGBA color out of a trimesh visual.material.baseColorFactor."""
    mat = getattr(visual, "material", None)
    if mat is None:
        return default
    bcf = getattr(mat, "baseColorFactor", None)
    if bcf is None:
        bcf = getattr(mat, "main_color", None)
    if bcf is None:
        return default
    # baseColorFactor can be float[0..1] or uint8[0..255] depending on glTF version;
    # trimesh normalises to uint8 for main_color but PBRMaterial may keep floats.
    if hasattr(bcf, "__iter__"):
        seq = list(bcf)
        if seq and isinstance(seq[0], float) and max(seq[:3]) <= 1.0:
            seq = [int(round(c * 255)) for c in seq]
        else:
            seq = [int(c) for c in seq]
        while len(seq) < 4:
            seq.append(255)
        return (seq[0], seq[1], seq[2], seq[3])
    return default


def load_mesh(path: str | Path,
              *,
              scale: float = 100.0,
              y_offset: float = 0.0,
              rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
              default_color: tuple[int, int, int, int] = (200, 200, 200, 255)) -> Mesh:
    """Load any trimesh-supported file and convert to flat-shaded DL data.

    Args:
        path: mesh file path (.glb, .obj, .stl, .ply, ...)
        scale: multiplier applied to all coords (raw → OoT units)
        y_offset: world-Y translation applied after scaling
        rotation_deg: (rx, ry, rz) Euler degrees, applied X → Y → Z. Useful for
                      tilting/orienting models that aren't authored Y-up.
        default_color: RGBA fallback when a primitive lacks a material color
    """
    import trimesh

    rx, ry, rz = (math.radians(a) for a in rotation_deg)
    cos_x, sin_x = math.cos(rx), math.sin(rx)
    cos_y, sin_y = math.cos(ry), math.sin(ry)
    cos_z, sin_z = math.cos(rz), math.sin(rz)

    loaded = trimesh.load(str(path), force=None)

    # Normalise into a {name: Trimesh} dict so .obj/.stl single-mesh and
    # .glb multi-primitive cases share one code path.
    if isinstance(loaded, trimesh.Trimesh):
        primitives = {"mesh": loaded}
    else:
        primitives = dict(loaded.geometry)

    out_verts: list[tuple[int, int, int, int, int, int, int]] = []
    out_tris: list[tuple[int, int, int]] = []

    for name, prim in primitives.items():
        color = _extract_color(prim.visual, default_color)
        verts = prim.vertices  # (N, 3) numpy
        faces = prim.faces     # (M, 3) numpy

        for face in faces:
            base = len(out_verts)
            for v_idx in face:
                x, y, z = (float(c) for c in verts[v_idx])
                # X rotation
                ny = y * cos_x - z * sin_x
                nz = y * sin_x + z * cos_x
                y, z = ny, nz
                # Y rotation
                nx = x * cos_y + z * sin_y
                nz = -x * sin_y + z * cos_y
                x, z = nx, nz
                # Z rotation
                nx = x * cos_z - y * sin_z
                ny = x * sin_z + y * cos_z
                x, y = nx, ny

                out_verts.append((
                    int(x * scale),
                    int(y * scale + y_offset),
                    int(z * scale),
                    color[0], color[1], color[2], color[3],
                ))
            out_tris.append((base, base + 1, base + 2))

    return Mesh(vertices=out_verts, triangles=out_tris)


# ============================================================
# Quick CLI inspection
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: mesh_to_dl.py <model.glb|obj|...> [scale]", file=sys.stderr)
        sys.exit(1)
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    m = load_mesh(sys.argv[1], scale=scale)
    print(f"Vertices: {len(m.vertices)}")
    print(f"Triangles: {len(m.triangles)}")
    if m.vertices:
        xs = [v[0] for v in m.vertices]
        ys = [v[1] for v in m.vertices]
        zs = [v[2] for v in m.vertices]
        print(f"Bounds: X=[{min(xs)},{max(xs)}] Y=[{min(ys)},{max(ys)}] Z=[{min(zs)},{max(zs)}]")
