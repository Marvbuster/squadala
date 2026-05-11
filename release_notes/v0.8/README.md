# OoT Live Dungeon v0.8 — Mesh Lab + Door_Warp1 Portal

**Zeitraum:** Mai 2026
**Fokus:** Sandbox-Tooling für Custom-Geometry-Experimente + immersives Boss-Clear-Style Portal in den Custom Dungeon

## Highlights

🧪 **Mesh Lab Dropdown.** Eigener Sandbox-Modus mit vier Layouts (Empty Box, L-Shape, Maze, Maze Complex) zum Iterieren auf Geometrie ohne Dungeon-Decoration-Noise. Jeder Lab läuft in seinem eigenen Namespace `scenes/squadala_mesh_lab/`, Hot-Reload-Eviction wurde rausgenommen (war Race mit dem Graphics-Thread, hat reproducible gecrasht).

🌀 **Door_Warp1 Boss-Clear-Portal.** Drückt man "Enter Dungeon", spawnt das vanilla blaue Lichtsäulen-Warp-Pillar genau vor Link — ausgewählt über Raycast-Suche in 12 Richtungen, so dass es nie in einer Wand landet. Kamera-Schwenk via `OnePointCutscene_Attention`, Boss-Clear-BGM startet, Link wird beim Reinlaufen automatisch in die Float-Cutscene gezogen, Bild fadet weiß aus → Custom Dungeon lädt. Komplett vanilla machinery, wir setzen nur die zwei Magic-State-Bits (`nextCutsceneIndex=0xFFEF` + `nextEntranceIndex=0`) damit der Actor außerhalb seiner Boss-Scenes funktioniert.

🏛️ **Custom Dungeon als eigene Scene.** Das Ziel des Entry-Portals ist jetzt eine separate `scenes/squadala_custom/` Scene mit eigener `.o2r` — kein Kollision mehr mit dem 3-Raum Debug Room. Aktuell eine simple 2000×800×3000 Empty Box als Platzhalter; LLM-kompilierte Inhalte können später einfach in diesen Slot reinwachsen.

🧱 **Thick-Wall Maze-Geometrie.** `_build_thick_maze` baut Wand-Blöcke mit allen vier Außenseiten (keine "spitze Plane"-Edges sichtbar wenn die Wand mitten im Raum endet). Mixed mit thin walls für Türen-Spezialfall (Türenpanel sitzt flush in der Wand). Per-Wand-Palette + Fake-Light-Shading damit benachbarte Wände visuell unterscheidbar bleiben.

🩹 **DL-Batching für große Meshes.** `build_display_list` splittet jetzt automatisch in 64-Vertex-Chunks und benutzt G_VTX_OTR_HASH's `w1`-Byte-Offset für die Sub-Resource-Loads. Vorher knallte alles >64 Verts in einem G_VTX-Command und der Vertex-Buffer overflow'te (Maze Complex hat 136 Verts).

🗝️ **Locked-Door-Workflow.** Maze v1 + v2 haben einen kleinen Chest mit Small Key, eine Locked Door (`DOOR_LOCKED` params), und einen Big Chest dahinter. Switch-Flag im Temp-Bank → Tür entsperrt sich beim Scene-Reload wieder. Lab-Chest-Treasure-Flags werden bei jedem Hot-Reload zurückgesetzt damit man's wiederholt testen kann.

## Builds

### Sidecar
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 11.05.2026 | Abgeschlossen |

### SoH-Fork
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 11.05.2026 | Abgeschlossen |

## Milestones

- **M7 (Multi-Room):** Fertig in v0.7, weiter genutzt in v0.8
- **Tooling/Sandbox:** Mesh Lab + Custom-Dungeon-Pipeline live
- **Custom Dungeon Portal-Flow:** kompletter Round-Trip Lab → Entry-Warp → Custom Dungeon → (Exit-Warp deferred)
- **M8 (LLM-Mesh-Generation):** Geplant — der Custom-Dungeon-Slot wartet auf LLM-generierten Content

## Verzeichnisstruktur

```
v0.8/
├── README.md
├── sidecar_build_1.md
└── soh_build_1.md
```
