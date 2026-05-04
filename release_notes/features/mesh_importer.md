# Mesh Importer

Format-agnostischer 3D-Mesh-Loader für SoH-Display-Lists, basiert auf [trimesh](https://trimesh.org/).

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Code | `tooling/mesh_to_dl.py` |
| Legacy (OBJ-only) | `tooling/obj_to_dl.py` (bleibt für Mario-Asset) |
| Dependency | `trimesh>=4.5` |
| Output | `Mesh(vertices: list[(x,y,z, r,g,b,a)], triangles: list[(v0,v1,v2)])` — flat-shaded, per-face-color |

## Unterstützte Formate

trimesh's universal Loader: `.glb`, `.gltf`, `.obj`, `.stl`, `.ply`, `.dae`, `.off`, `.3mf`, etc.

## API

```python
from mesh_to_dl import load_mesh

mesh = load_mesh(
    "tooling/assets/3d/pizza.glb",
    scale=14000.0,                  # raw → OoT units multiplier
    y_offset=0.0,                   # post-scale Y translation
    rotation_deg=(-60.0, 0.0, 0.0), # Euler X→Y→Z (degrees)
    default_color=(200, 200, 200, 255),  # fallback wenn kein Material
)
```

## Material-Handling

PBR-Materials liefern Per-Mesh-Color via `baseColorFactor`:

```python
def _extract_color(visual, default):
    mat = getattr(visual, "material", None)
    bcf = getattr(mat, "baseColorFactor", None) or getattr(mat, "main_color", None)
    # uint8 oder float (0..1) — autodetect via max(seq[:3]) <= 1.0
    ...
```

Multi-Primitive-Scenes (z.B. Pizza = `Pizza` + `Pizza_1` + `Pizza_2`) werden zu einer Vertex/Triangle-Liste gemerged, jeder Primitive bringt seine eigene Material-Color in die Per-Vertex-Daten ein.

## Integration in build_box_room.py

```python
from mesh_to_dl import load_mesh

pizza = load_mesh(PIZZA_GLB, scale=14000.0, rotation_deg=(-60.0, 0.0, 0.0))
pizza_vtx = build_vtx_resource(
    [(v[0], v[1], v[2]) for v in pizza.vertices],
    [(v[3], v[4], v[5], v[6]) for v in pizza.vertices],
)
pizza_dl = build_unindexed_dl(PIZZA_VTX_PATH, len(pizza.triangles))
```

`build_unindexed_dl` handelt das F3DEX2-32-Slot-Vertex-Buffer-Limit per automatischer Multi-Batch-Loads.

## Asset-Standorte

**Pipeline-Quelle:** `tooling/assets/3d/`

Was hier liegt:
- `pizza.glb` — rotierende Showcase-Decoration
- `super_mario/model.obj` + `materials.mtl` — Custom-Truhen-Reward

**NICHT** Pipeline-Quelle:
- `_raw_data/` — User→Claude Drop-Zone, transient, nicht versioniert. Builds dürfen niemals daraus konsumieren.

## CLI-Inspektion

```bash
$ python3 tooling/mesh_to_dl.py tooling/assets/3d/pizza.glb 14000
Vertices: 3600
Triangles: 1200
Bounds: X=[-353,355] Y=[-353,355] Z=[-3,30]
```

## Limits / Bekanntes

- Per-Face-Color (one color per primitive) — keine per-vertex baseColor aus textures (M9)
- Keine UV / Normals exportiert (flat shading via vertex-duplication)
- Kein Skinning / Animation
