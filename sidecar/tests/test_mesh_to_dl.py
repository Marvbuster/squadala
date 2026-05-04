"""Smoke tests for the trimesh-based mesh importer.

The full flow (GLB → flat-shaded vertex/triangle list with material colours
baked in per face) is exercised against the pizza asset shipped under
tooling/assets/3d/. Tests skip gracefully when trimesh isn't installed in
the active environment so this file works in lean CI setups too.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLING = Path(__file__).resolve().parents[2] / "tooling"
if str(_TOOLING) not in sys.path:
    sys.path.insert(0, str(_TOOLING))


def _trimesh_available() -> bool:
    try:
        import trimesh  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _trimesh_available(), reason="trimesh not installed")

PIZZA = _TOOLING / "assets" / "3d" / "pizza.glb"


@pytest.fixture
def pizza_path() -> Path:
    if not PIZZA.exists():
        pytest.skip(f"pizza.glb missing at {PIZZA}")
    return PIZZA


def test_load_pizza_returns_mesh_with_geometry(pizza_path: Path) -> None:
    from mesh_to_dl import Mesh, load_mesh

    mesh = load_mesh(pizza_path, scale=14000.0, rotation_deg=(-60.0, 0.0, 0.0))
    assert isinstance(mesh, Mesh)
    assert len(mesh.vertices) == 3 * len(mesh.triangles), \
        "flat-shaded output has 3 unique vertices per triangle"
    assert len(mesh.triangles) > 1000, "pizza has many primitives merged together"


def test_pizza_pbr_colors_are_extracted(pizza_path: Path) -> None:
    """Pizza GLB has three primitives with distinct PBR baseColorFactors
    (crust, cheese, toppings). After flat-shading, every triangle's three
    vertices share one colour, and we should see all three palette entries."""
    from mesh_to_dl import load_mesh

    mesh = load_mesh(pizza_path, scale=14000.0)
    seen_colors = {tuple(v[3:7]) for v in mesh.vertices}
    # Default colour fallback would yield exactly one (200,200,200,255).
    # PBR-aware extraction must produce three distinct primitive colours.
    assert len(seen_colors) >= 3, f"expected ≥3 PBR colours, got {seen_colors}"
    # Each colour is opaque (alpha 255) and within uint8 range.
    for r, g, b, a in seen_colors:
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255
        assert a == 255


def test_x_rotation_lifts_pizza_off_xy_plane(pizza_path: Path) -> None:
    """Native pizza is in the XY plane (Z is the disc-thickness axis).
    A non-zero X rotation should give the rotated mesh visible Z extent."""
    from mesh_to_dl import load_mesh

    flat = load_mesh(pizza_path, scale=14000.0, rotation_deg=(0.0, 0.0, 0.0))
    tilted = load_mesh(pizza_path, scale=14000.0, rotation_deg=(-60.0, 0.0, 0.0))

    flat_z_range = max(v[2] for v in flat.vertices) - min(v[2] for v in flat.vertices)
    tilted_z_range = max(v[2] for v in tilted.vertices) - min(v[2] for v in tilted.vertices)

    assert tilted_z_range > flat_z_range, "tilt should expand the Z extent"


def test_default_color_used_when_no_material(tmp_path: Path) -> None:
    """A mesh without PBR materials falls back to default_color."""
    import trimesh
    from mesh_to_dl import load_mesh

    # Author a tiny untextured cube on disk.
    cube = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    obj_path = tmp_path / "cube.obj"
    cube.export(obj_path)

    custom = (10, 20, 30, 255)
    mesh = load_mesh(obj_path, scale=100.0, default_color=custom)
    seen = {tuple(v[3:7]) for v in mesh.vertices}
    assert seen == {custom}
