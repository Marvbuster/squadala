# OoT Live Dungeon Sidecar v0.5.0 Build 1

**Datum:** 04.05.2026 | **Status:** Abgeschlossen | **Milestone:** M5++ + M6 (in Arbeit)

## Zusammenfassung

Der Custom-Raum-Generator wurde von "4 Triangles" auf einen vollständigen begehbaren Boxraum mit echten Aktoren erweitert: 6 Wände, Boden, Decke, Z-Buffer, korrekte Normals. Plus ein neuer trimesh-basierter Mesh-Importer, der GLB/OBJ/STL/PLY auf das gleiche flat-shaded OVTX+TLDO-Format mappt — mit PBR-Material-Farben aus dem glTF-Material-Block.

Mario aus `tooling/assets/3d/super_mario/` wird als Custom-Truhen-Reward exportiert, Pizza aus `tooling/assets/3d/pizza.glb` als rotierende Showcase-Decoration über der Truhe.

## Features & Änderungen

### Box-Room-Generator (`tooling/build_box_room.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | 24 Vertices (6 Faces × 4) für vollständigen Boxraum statt nur 4 Triangles |
| FEATURE | `G_GEOMETRYMODE` mit `G_CULL_BACK` + `Z_BUFFER` + `SHADE` für korrekte 3D-Render-Pipeline |
| FEATURE | Render-Mode auf `G_RM_AA_ZB_OPA_SURF` (0x00552078) — anti-aliased + Z-Buffered Opaque Surface |
| FEATURE | Actor-Library mit Object-ID-Mapping (Pots, Chest, Deku-Baba, Keese — verifiziert gegen `object_table.h`) |
| FEATURE | `chest_params()` Helper baut En_Box-Params semantisch (chest_type, item_id, treasure_flag → bit-packed) |
| FEATURE | `build_unindexed_dl()` für große Meshes — F3DEX2-Vertex-Buffer-Limit (32 Slots) → automatische Multi-Batch-Loads |
| FEATURE | `build_room_header()` nimmt `actors` und `extra_dl_paths` Params, baut korrekte Object-Liste daraus |
| FEATURE | `collect_required_objects()` ermittelt Object-Dependencies aus Actor-Liste |
| FEATURE | `chest_params(item_id=GI_LIVEGEN_MARIO, ...)` — Chest in der Custom-Scene zeigt Mario statt Heart Piece |
| FIX | Object-IDs gegen `object_table.h` verifiziert: `OBJ_BOX=0x000E` (war 0x000A), `OBJ_DEKUBABA=0x0039` (war 0x0008), `OBJ_TSUBO=0x012C` (war 0x0111 — actor-id, nicht object-id) |
| FIX | `GI_HEART_PIECE=0x3E` (war 0x29) — sonst kam Map statt Herzteil aus der Truhe |
| FIX | `rot_y=0x8000` overflow für signed int16 — wrap zu negativ in `build_actor_entry()` |
| FEATURE | Asset-Pfade auf `tooling/assets/3d/` — `_raw_data/` ist User-Drop-Zone, niemals Pipeline-Quelle |

### Mesh-Importer (`tooling/mesh_to_dl.py` — neu)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | trimesh-basierter Universal-Loader für GLB / OBJ / STL / PLY / glTF |
| FEATURE | PBR-Material → Per-Face-Color via `baseColorFactor` (uint8 + float-normalisierung) |
| FEATURE | Multi-Primitive-Scenes werden gemerged (Pizza = Crust + Cheese + Toppings → 1 Vertex/Triangle-Liste) |
| FEATURE | Euler-Rotation X→Y→Z baked-in für Tilt/Orientation (`rotation_deg=(rx, ry, rz)`) |
| FEATURE | Per-Face-Vertex-Duplikation für sharp flat shading (kein interpolated normals) |
| FEATURE | CLI-Inspektion: `python3 mesh_to_dl.py model.glb [scale]` zeigt Bounds und Triangle-Count |

### Tooling-Tests (`tooling/test_build_box_room.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | 24 Verts / 12 Tris für Box-Geometrie validiert |
| FEATURE | `TestActorLibrary` — Object-ID-Lookups, Param-Encoding, Multi-Object-Aggregation |
| FEATURE | 74 Tests insgesamt, alle grün |

### Asset-Management

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `tooling/assets/3d/pizza.glb` — Pizza als rotierende Decoration |
| FEATURE | `tooling/assets/3d/super_mario/model.obj` + `materials.mtl` — Mario als Custom-Item |
| ENHANCEMENT | `_raw_data/` explizit als User→Claude Drop-Zone deklariert, nicht Pipeline-Quelle |

### Dependencies

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `trimesh>=4.5` zu `sidecar/pyproject.toml` |

## Architektur-Erkenntnisse

### F3DEX2 32-Slot-Vertex-Limit

Display Lists referenzieren Vertices über einen 32-Slot-Buffer. Ein einzelner `G_VTX_OTR_HASH` lädt bis zu 32 Vertices ab Position N. Für unsere Mario-Geometrie (3564 Verts) und Pizza (3600 Verts) muss `build_unindexed_dl` automatisch in 30er-Chunks splitten — jeder Chunk lädt bis zu 30 Vertices und emittiert 10 Triangles.

### PBR baseColorFactor — uint8 vs float

trimesh normalisiert Material-Farben unterschiedlich je nach glTF-Version:
- `mat.main_color` → `[r, g, b, a]` als uint8 (0–255)
- `mat.baseColorFactor` → kann float (0.0–1.0) ODER uint8 sein

`mesh_to_dl._extract_color()` checkt `isinstance(seq[0], float) and max(seq[:3]) <= 1.0` und konvertiert entsprechend.

### Drop-Zone vs Pipeline

`_raw_data/` ist die User→Claude Übergabe — Original-Assets, möglicherweise transient, nicht versioniert. **Pipelines dürfen niemals direkt darauf zugreifen** sonst sind Builds non-reproducible. Stattdessen: kopieren nach `tooling/assets/3d/` und von dort konsumieren.

## Generierte .o2r-Struktur

```
zzz_squadala_dungeon.o2r (131402 bytes):
├── scenes/nonmq/ydan_scene/ydan_scene              (Custom Scene, 279B)
├── scenes/nonmq/ydan_scene/ydan_room_0             (Custom Room mit Actor-Liste, 309B)
├── scenes/nonmq/ydan_scene/squadala_box_DL         (Box-Walls DL, 184B)
├── scenes/nonmq/ydan_scene/squadala_box_Vtx        (24 Box-Vertices, 452B)
├── scenes/nonmq/ydan_scene/squadala_mario_DL       (Mario DL, 6776B)
├── scenes/nonmq/ydan_scene/squadala_mario_Vtx      (3564 Mario-Vertices, 57092B)
├── scenes/nonmq/ydan_scene/squadala_pizza_DL       (Pizza DL, 6840B)
├── scenes/nonmq/ydan_scene/squadala_pizza_Vtx      (3600 Pizza-Vertices, 57668B)
└── scenes/nonmq/ydan_scene/ydan_sceneCollisionHeader_00B610  (Custom Collision, 356B)
```

## Nächste Schritte

- M6: LLM-Prompt-Erweiterung um Aktoren — DungeonSpec → Actor-Liste statt nur Geometrie
- Multi-Mesh-Showcase im Custom-Raum (Cupcake.glb ist auch schon da)
- Mesh-LLM-Pipeline (M8) — DungeonSpec → eigene Mesh-Generierung statt vorgefertigte Assets
