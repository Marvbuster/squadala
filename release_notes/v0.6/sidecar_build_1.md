# OoT Live Dungeon Sidecar v0.6.0 Build 1

**Datum:** 04.05.2026 | **Status:** Abgeschlossen | **Milestone:** M6

## Zusammenfassung

M6 ist durchverdrahtet: der abstrakte DungeonSpec aus dem LLM (Rooms mit Aktoren und Chests, ohne Positionen) wird über eine neue Bridge in eine konkrete Actor-Liste übersetzt und an die Custom-Geometry-Pipeline weitergegeben. HTTP-`/compile` und `/dungeons/{id}/activate` produzieren jetzt das gleiche `.o2r`-Format wie der `tooling/build_box_room.py`-CLI — mit echtem Custom-Box-Raum statt Vanilla-Deku-Tree-Override.

Plus: ACTOR_LIBRARY auf alle 21 ActorTypes aus dem Schema erweitert (vorher 9), das Debug-Raum-Default-Layout hat jetzt 26 En_Item00-Showcase-Items entlang der neuen langen Z-Achse, und der Box-Raum ist von 1200×600×1200 auf 1200×600×**3000** verlängert.

## Features & Änderungen

### DungeonSpec-Bridge (`compiler/box_room_dungeon.py` — neu)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `spec_to_actors(room)` — abstract `Actor(type, count)` + `Chest(id, contents)` → konkrete Placements (Kreis-Layout für Gegner, Center für Truhen) |
| FEATURE | `build_dungeon_o2r(spec, output_path)` — End-to-End-Compiler vom DungeonSpec zur Custom-Geometry-`.o2r` |
| FEATURE | `ACTOR_TYPE_TO_LIBRARY` — alle 21 Schema-`ActorType`s gemapped auf `bbr.ACTOR_LIBRARY`-Keys |
| FEATURE | `CHEST_CONTENT_TO_GI` — `ChestContent` → `GI_*` Bytes (incl. neuer `livegen_mario` → `0x7E`) |
| FEATURE | sys.path-Bridge zu `tooling/build_box_room` ohne 800 LoC zu duplizieren |

### Schema-Erweiterung (`schema.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `ChestContent.livegen_mario` — Custom Squadala-Item, mappiert auf `GI_LIVEGEN_MARIO=0x7E` und triggert die Slow-CS + Custom-Drawfunc + "Squadala!"-Textbox aus v0.5 |

### Agent-Prompt (`agent.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `SCHEMA_SHAPE` listet `livegen_mario` als chest-content-Option, sodass der LLM Mario in Truhen platzieren kann |

### API-Wiring (`api.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `/compile` und `/dungeons/{id}/activate` benutzen jetzt `box_room_dungeon.build_dungeon_o2r` statt `scene_builder.build_dungeon_o2r` (vanilla Deku-Tree-Override) |
| FEATURE | `_detect_mods_path()` Helper extrahiert für DRY |
| FEATURE | API-Version auf 0.5.0 angehoben (war 0.3.0) |

### Tooling-Refactor (`build_box_room.py`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `build_dungeon_o2r(output_path, actors=None, include_mario_dl, include_pizza_dl)` als wiederverwendbare Library-Funktion — CLI bleibt thin wrapper über `main()` |
| FEATURE | `DEFAULT_ACTORS` extrahiert; `_resolve_default_actors()` materialisiert mit chest-params + Item-Showcase-Reihe |
| FEATURE | Box-Dimensionen Defaults: `w=600, h=600, d=1500` → 3000 lang in Z |
| FEATURE | `ITEM00_SHOWCASE` Liste mit 26 En_Item00 Drop-Varianten (RUPEE_GREEN..BOMBCHU); ITEM00_FLEXIBLE ausgelassen weil unstable |
| FEATURE | `_build_item_row(x, z_min, z_max)` — spreadt Drops gleichmäßig entlang einer Linie |
| FEATURE | ACTOR_LIBRARY +18 Schema-Typen (skulltula, stalfos, lizalfos, wolfos, white_wolfos, freezard, dinolfos, gibdo, redead, poe, floormaster, wallmaster, armos, beamos, like_like, bubble, torch_slug, dodongo) |
| FEATURE | ACTOR_LIBRARY[`item00`] — En_Item00 (Actor-ID 0x0015), nutzt gameplay_keep, Drop-Variant über params |
| FEATURE | ITEM00_* Konstanten (RUPEE_GREEN..BOMBCHU) als Modul-Symbole exposed |

### Tests

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `tests/test_box_room_dungeon.py` — 5 Tests: Kreis-Placement, Schema-Coverage, ChestContent→GI, MARIO=0x7E, e2e .o2r build |
| FEATURE | `tests/test_mesh_to_dl.py` — 4 Tests: Pizza GLB load, PBR-Color-Extraction (3 distinct Pizza-Farben), X-Tilt Z-Range, default_color Fallback |
| FEATURE | `test_all_schema_actors_round_trip` — fängt zukünftige `ActorType`-Erweiterungen ohne Library-Mapping |
| FIX | `test_first_vertex_is_floor_corner` und `test_bounding_box` für non-square room (d=1500) angepasst |

### Dependencies

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `trimesh>=4.5` ist in `pyproject.toml`; aktiv im sidecar venv installiert |

## Architektur-Erkenntnisse

### Schema bleibt abstrakt — Compiler platziert

Der DungeonSpec sagt nur _was_ in den Räumen ist (`Actor(type, count)` plus `Chest(id, contents)`), nicht _wo_. Die Bridge entscheidet das beim Kompilieren — Gegner werden auf einen Kreis um das Raumzentrum verteilt, Truhen ans Zentrum gefannt. Das hält den LLM-Output stabil und macht Layout zur Compiler-Verantwortung.

### Sidecar konsumiert tooling/ via sys.path

`tooling/build_box_room.py` ist 830+ LoC byte-genauer Layout-Code (Resource-Header, OVTX, TLDO, Collision, Scene-Header). Statt das nach `sidecar/src/livegen/compiler/` zu duplizieren, fügt der Bridge-Compiler `tooling/` über sys.path ein und importiert `build_box_room` direkt. Single source of truth.

### Sliver tests entkoppelt von venv state

`test_mesh_to_dl.py` und der e2e-Test in `test_box_room_dungeon.py` skippen sauber wenn `trimesh` nicht installiert ist — die ImportError landet nicht im Stacktrace, der Test läuft einfach nicht. So funktioniert das Test-Suite auch in lean CI environments.

## Generierte .o2r-Struktur (default debug-room)

```
zzz_squadala_dungeon.o2r (131818 bytes):
├── scenes/nonmq/ydan_scene/ydan_scene
├── scenes/nonmq/ydan_scene/ydan_room_0             (725B — 34 Aktoren statt 8)
├── scenes/nonmq/ydan_scene/squadala_box_DL
├── scenes/nonmq/ydan_scene/squadala_box_Vtx
├── scenes/nonmq/ydan_scene/squadala_mario_DL
├── scenes/nonmq/ydan_scene/squadala_mario_Vtx
├── scenes/nonmq/ydan_scene/squadala_pizza_DL
├── scenes/nonmq/ydan_scene/squadala_pizza_Vtx
└── scenes/nonmq/ydan_scene/ydan_sceneCollisionHeader_00B610  (longer in Z)
```

Layout: 4 Pots in den Original-Cluster-Ecken, Mario-Truhe im Zentrum, 3 Deku-Babas südlich, 26 Item-Drops als Reihe entlang x=-300, z=-1300..+1300.

## Nächste Schritte

- M7: Cupcake-Decoration in Room 2, multi-room mit `En_Holl` Connector zwischen Room 1 (current debug) und Room 2
- ACTOR_LIBRARY uncertainty-Pass: TODO-markierte Object-IDs gegen object_table.h verifizieren
- Optional: LLM-Prompt-Härtung mit Beispielen, sobald das Dungeon-Setting feststeht
