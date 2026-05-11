# OoT Live Dungeon Sidecar v0.7.0 Build 1

**Datum:** 10.05.2026 | **Status:** Abgeschlossen | **Milestone:** M7

## Zusammenfassung

Drei-Raum-Scene mit `En_Holl` + `En_Door` Transitions, eigenem Scene-Namespace `scenes/squadala/`, drei Custom-Chest-Rewards (Mario/Sonic/Hydrant) und room-aware Decorations (Pizza/Cupcake). Hauptarbeit liegt im `tooling/build_box_room.py`-Refactor: aus dem Single-Room-Builder ist ein Multi-Room-Compiler geworden, der pro Raum eigene Geometrie + Aktor-Listen baut und `TransitionActorEntry`-Einträge im Scene-Header emittiert.

## Features & Änderungen

### Multi-Room (`tooling/build_box_room.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `build_collision()` akzeptiert `min_x/max_x/floor_y/h/min_z/max_z` + optionale `inner_walls`-Liste mit Tür-Cutouts (3-Panel-Pattern, bidirektionale Polys) |
| FEATURE | `build_scene_header()` nimmt jetzt eine Liste von `room_paths` plus `transition_actors` und `spawn_pos`/`spawn_rot_y` |
| FEATURE | `build_dungeon_o2r()` als Multi-Room-Compiler — pro Raum eigene Vertex/DL-Resources, Aktor-Liste, ObjectList |
| FEATURE | 3-Room-Standalone-CLI (`main()`) — Room 0 Mitte, Room 1 Ost (Sonic/Töpfe/Keese), Room 2 West (Hydrant/Deku Baba) |
| FIX | LightSettings-Fog: `struct.pack('<hh', fogNear, zFar)` statt hardgecodeter BE-Bytes — SoH liest little-endian, alte Variante hat fogNear=-8189/zFar=16 erzeugt → Black Screen |
| FIX | EntranceList wird VOR SpawnList emittiert — `Scene_CommandSpawnList` deref'd `setupEntranceList` direkt, Reihenfolge spielt Rolle |
| FIX | Z-Fight an der geteilten Wand: Tür-Panels werden 1 Unit nach innen gezogen, sonst flackert der Wand-Übergang |
| FIX | Shared-Objects: Union aller Aktor-Required-Objects aus *allen* Räumen wird in jeden Raum geschrieben — verhindert dass `func_80031A28` Aktoren killt deren Objekt nicht in der neuen Room-ObjectList steht (Workaround, Permanenter Fix in BACKLOG) |
| FEATURE | Door-Specs pro Wand-Seite: `DOOR_SPEC_HOLL` 120×200 (Wand-Loch passt zur En_Holl-Fade-Plane), `DOOR_SPEC_DOOR` 60×100 (Loch passt exakt zum `gDoorLeftDL`-Panel — kein schwarzer Rahmen mehr) |

### Custom Scene Namespace (`scenes/squadala/`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `TARGET = "scenes/squadala"` — eigener Namespace ohne Vanilla-Pfad-Kollisionen |
| FEATURE | Cache-Eviction in `LiveGenHotReload.cpp::HotReloadDungeon` ist nur für echte Hot-Reloads nötig (Rebuild zwischen Debug-Room-Klicks) — beim ersten Klick ist eh cache-miss |

### Mesh Pipeline (`tooling/mesh_to_dl.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `color_override`-Parameter — überspringt Material-Extraktion ganz, falls man eine Solid-Color setzen will (Hydrant: GLB hat eine Image-Texture, kein `baseColorFactor`) |
| FEATURE | `shade_strength` + `light_dir` — bakt Per-Face Flat-Shading in die Vertex-Farben (Face-Normalen mit Vertex-Rotation gedreht, Dot mit Light, multipliziert auf Color). Nötig weil unsere DLs `G_CC_SHADE` ohne `G_LIGHTING` benutzen |
| FIX | `_extract_color()` erkennt PIL-Images über `size+mode` Attribute statt über Type-Check — fängt den Fall ab dass `baseColorTexture` ein Image-Objekt zurückgibt statt einer Color-Tuple |

### Custom-Item Library Erweiterung

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Sonic-Mesh als zweites Custom-Chest-Reward (`scenes/squadala/sonic_DL`/`sonic_Vtx`) |
| FEATURE | Fire Hydrant als drittes Custom-Chest-Reward (`hydrant_DL`/`hydrant_Vtx`), `scale=14000`, `rotation_deg=(-90, 0, 0)` (Z-up Source), `color_override=(220,30,30,255)`, `shade_strength=0.6` |
| FEATURE | Cupcake-Mesh als zweite Decoration (`cupcake_DL`/`cupcake_Vtx`), `rotation_deg=(-90, 0, 0)` |
| FEATURE | Mouse-Mesh als dritte Decoration (`mouse_DL`/`mouse_Vtx`, 6218 Tris), `scale=167`, `color_override=(198,172,169,255)` (diffuse-Textur-Average), `shade_strength=0.6`. Skelett-Anims + Textures ungenutzt — siehe BACKLOG M9 / M11 |

### Tooling-Tests

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `tooling/test_build_box_room.py` — Multi-Room-spezifische Tests (Room-Counts, TransitionActor-Format, Door-Cutout-Geometrie) |

## Architektur-Erkenntnisse

### LLM braucht weder Multi-Room noch En_Holl direkt zu kennen

`build_box_room.py` enthält die Multi-Room-Logik als Tooling-Library. Die Sidecar-API (`compiler/box_room_dungeon.py` aus v0.6) bleibt unangetastet — das LLM produziert weiter `DungeonSpec` mit `Room(name, actors, chests)`. Wenn M7-Layouts ankommen, übersetzt der Compiler sie auf die neue Multi-Room-Builder-API. Damit bleibt das Schema abstrakt; die räumliche Layout-Logik ist Compiler-Sache.

### Hardgecodete Decoration-Ranges sind ein bewusstes M7-Übergangs-Hack

`LiveGenDecoration.cpp` filtert Pizza/Cupcake aktuell nach Link's Welt-X — okay für die 3-Raum-Test-Scene, nicht für vom LLM komponierte Dungeons. Drei Optionen für die dynamische Lösung sind in `docs/BACKLOG.md "Dynamic Deco-Registry"` formalisiert; Zielbild ab M8+ ist Variante 3 (Decoration als echter Actor mit Vanilla-Cull-Lifecycle).

## Bekannte Limitationen

- `LiveGenDecoration.cpp` ist hardcoded auf 2 Decorations (Pizza/Cupcake) mit Welt-X-Ranges aus dem Debug-Layout. Erst bei M8+ relevant.
- ObjectList-Union: jeder Raum trägt die Required-Objects *aller* Aktoren — Memory-Verschwendung bei großen Dungeons. Workaround dokumentiert in BACKLOG.

## Nächste Schritte

- M8 — Sidecar generiert Mesh-Daten aus DungeonSpec (prozedurale Patterns + optional ShapeLLM)
- Dynamic Deco-Registry parallel zu M8 (Decoration-as-Actor)
- MCP-style LLM-Tool-Surface für komplexere Dungeon-Authoring (siehe BACKLOG)
