# DungeonSpec → Custom-Geometry Bridge

Übersetzt den abstrakten LLM-Output (DungeonSpec) in eine konkrete Custom-Geometry-`.o2r`-Datei mit Aktoren aus dem Spec.

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Sidecar-Modul | `sidecar/src/livegen/compiler/box_room_dungeon.py` |
| Tooling-Backend | `tooling/build_box_room.py::build_dungeon_o2r` |
| API-Endpunkt | `POST /compile`, `POST /dungeons/{id}/activate` |

## Datenfluss

```
LLM → DungeonSpec (abstrakt: type+count, contents)
          │
          ▼
spec_to_actors(room) — Mapping + Layout
          │
          ▼
[{name, x, y, z, rot_y, params}, ...]
          │
          ▼
build_box_room.build_dungeon_o2r(actors=...)
          │
          ▼
.o2r mit Custom-Geometry + Aktoren + Mario-DL + Pizza-DL
```

## Mappings

### Aktoren

`ActorType` (Schema) → `ACTOR_LIBRARY`-Key (build_box_room) → `(actor_id, default_params, [object_ids])`.

Aktuell vollständig gemapped: alle 21 ActorTypes aus dem Schema (keese, skulltula, stalfos, lizalfos, wolfos, white_wolfos, freezard, iron_knuckle, dinolfos, gibdo, redead, poe, floormaster, wallmaster, armos, beamos, like_like, bubble, torch_slug, dodongo, tektite).

Object-IDs sind teilweise mit `TODO: verify` markiert weil sie aus dem v0.4-`scene_builder.py` portiert wurden und noch nicht 1:1 gegen `object_table.h` validiert sind. Aktoren mit ungültigen Object-IDs spawnen nicht.

### Chests

`ChestContent` → `GI_*` Byte (7-bit, fits En_Box-params bits 5-11):

| ChestContent | GI Byte | Notiz |
|--------------|---------|-------|
| piece_of_heart | 0x3E | |
| map | 0x41 | |
| compass | 0x40 | |
| small_key | 0x42 | |
| boss_key | 0x3F | |
| rupees_5 | 0x4C | (= GI_RUPEE_GREEN) |
| rupees_20 | 0x4E | (= GI_RUPEE_RED) |
| rupees_50 | 0x55 | (= GI_RUPEE_PURPLE) |
| **livegen_mario** | **0x7E** | Custom Squadala-Item — Slow-CS + Mario-DL + "Squadala!"-Text |

## Layout-Strategie

- **Gegner:** auf einem Kreis mit Radius 350 um das Raumzentrum verteilt, alle bei `y=-100` (Box-Raum-Boden)
- **Truhen:** am Zentrum aufgefannt (bei mehreren Truhen über `2π/n`)
- **Treasure-Flag:** pro Truhe 1..n im Bereich 0..0x1F, sodass mehrere Truhen pro Raum unterschiedliche Save-Flags belegen
- **Default `rot_y=0x8000`** für Truhen — Spieler kommt von vorne ran

Für M7 (Multi-Room) wird das pro Raum repliziert — derzeit nur Room 0 des Specs gerendert.

## API-Integration

```python
# api.py
from livegen.compiler.box_room_dungeon import build_dungeon_o2r

output = build_dungeon_o2r(spec, Path(mods_path) / "zzz_squadala_dungeon.o2r")
```

Beide HTTP-Endpunkte (`/compile`, `/dungeons/{id}/activate`) benutzen den gleichen Bridge-Compiler.

## Testabdeckung

| Test | Was er prüft |
|------|---------------|
| `test_keese_count_expands_to_circular_placement` | Count→Placements, alle bei `y=-100`, distinct (x,z) |
| `test_all_schema_actors_round_trip` | Jeder `ActorType` hat Library-Mapping (regression guard) |
| `test_chest_contents_map_to_correct_gi` | ChestContent-Bits korrekt in `params` encoded |
| `test_livegen_mario_resolves_to_custom_gi_id` | MARIO=0x7E ist genau der Slot den die soh-fork-Side hooked |
| `test_build_dungeon_o2r_writes_complete_archive` | E2E: spec → `.o2r` mit allen erwarteten Resource-Pfaden |

## Erweiterungspunkte

- **Multi-Room (M7):** Iteriere über alle `spec.rooms` statt nur `[0]`. Connect via `En_Holl` über die `connections`-Liste.
- **Layout-Variation:** Kreis-Layout durch template-spezifische Patterns ersetzen (z.B. `corridor_straight` → Linie, `boss_arena` → Eckpositionen).
- **Custom-Geometry pro Raum:** Statt fixed Box-Geometrie aus `build_box_vertices()`, perspectively pro Raum eigene Wände/Form (M8 LLM-Mesh-Generation).
