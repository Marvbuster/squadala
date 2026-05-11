# OoT Live Dungeon v0.7 — M7 Multi-Room

**Zeitraum:** Mai 2026
**Fokus:** Drei verbundene Räume in einer Scene — En_Holl + En_Door Transitions, getrennte Geometrie/Aktoren pro Raum, room-aware Dekorationen

## Highlights

🚪 **M7 ist fertig.** Aus dem ein-Raum-Showcase ist eine echte Mini-Scene mit drei Räumen geworden:

- **Room 0 (Mitte)** — Mario-Truhe + spinning Pizza, südlicher Spawn
- **Room 1 (Osten)** — Sonic-Truhe + 4 Töpfe + 2 Keese + spinning Cupcake, betreten via En_Holl
- **Room 2 (Westen)** — Hydrant-Truhe + 1 Deku Baba + statische Maus auf dem Boden, betreten durch sichtbare En_Door

🌐 **Eigener Scene-Namespace** `scenes/squadala/` — keine Vanilla-Pfad-Kollisionen mehr, Cache-Eviction nur für echtes Hot-Reload nötig.

🎯 **Drei neue Custom-Chest-Items.** Aufbauend auf Mario aus v0.5 stehen jetzt auch Sonic (`GI_LIVEGEN_SONIC=0x7F`) und Fire Hydrant (`GI_LIVEGEN_HYDRANT=0x7D`) als Custom-Truhen-Inhalte zur Verfügung — gleicher Drei-Layer-Pattern (GI-Slot + ItemTable-Entry + Hooks), eigene Drawfuncs, eigene Textboxen DE/EN/FR.

🍰 **Room-aware Dekorationen.** Pizza und Cupcake sind beide an ihre Räume gepinnt und reagieren korrekt auf Raum-Wechsel — bewusst hardgecodet auf Welt-X-Ranges für M7, mit TODO/BACKLOG-Eintrag für die dynamische Deco-Registry ab M8+.

🎨 **Fake-Light Shading.** `mesh_to_dl.py` kann jetzt per-Face Flat-Shading in die Vertex-Farben backen (`shade_strength`, `light_dir`), damit Modelle ohne echte N64-Lighting trotzdem Kanten haben — nötig weil unsere DLs `G_CC_SHADE` ohne `G_LIGHTING` benutzen.

🐭 **Maus-Addon (v0.7-Spätbug).** Skinned `mouse.glb` (3 Anims, 413-Node-Rig, 3 Textures, 9.7 MB) ist in der Pipeline als statische Rest-Pose mit Textur-Average-Color reingelegt. Skelett-Animation + echte Texture-Samples sind in BACKLOG als M9 (Texturen) / M11 (Animation Pipeline) dokumentiert.

🚪 **Door-Cleanup-Fix.** Vanilla OoT kombiniert nie En_Holl + En_Door im selben Bereich, also war's nie aufgefallen: `func_80031B14` killt nach jeder Transition alle Actors mit `room >= 0 && room != curRoom && room != prevRoom`. Da prevRoom direkt davor auf -1 gesetzt wird, sterben Transition-Actors deren `room`-Feld nicht zum Ziel passt. Fix: in unserem Fork wird `ACTORCAT_DOOR` aus dem Cleanup ausgenommen, gegated auf `LiveGen_IsDebugRoomActive()` — Vanilla bleibt unangetastet.

## Builds

### Sidecar
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 10.05.2026 | Abgeschlossen |

### SoH-Fork
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 10.05.2026 | Abgeschlossen |

## Milestones

- **M7 (Multi-Room):** Fertig — 3 Räume, En_Holl + En_Door, room-aware Deko, dedizierter `scenes/squadala/` Namespace
- **M8 (LLM-Mesh-Generation):** Geplant — Sidecar generiert Mesh-Daten aus DungeonSpec; Dynamic Deco-Registry zieht mit
- **Backlog:** `docs/BACKLOG.md` — formalisierte Sammlung offener Themen, Future Ideas und bekannter Workarounds

## Verzeichnisstruktur

```
v0.7/
├── README.md
├── sidecar_build_1.md
└── soh_build_1.md
```
