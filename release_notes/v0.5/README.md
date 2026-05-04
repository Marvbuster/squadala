# OoT Live Dungeon v0.5 — Vollständiger Box-Raum + Custom Chest Content

**Zeitraum:** Mai 2026
**Fokus:** Lebender Custom-Raum mit echter Geometrie, Custom-Item-Pipeline für Truhen, GLB-Mesh-Importer

## Highlights

🎉 **M5++ ist fertig.** Der Custom-Raum hat jetzt 6 Wände, Boden, Decke — keine durchsichtigen Außenflächen mehr, Z-Buffer ist sauber an, Spawn-Position kommt aus der Custom-Scene. Echte OoT-Aktoren spawnen darin (Töpfe, Truhe, Deku-Babas).

🍕 **Mario in der Kiste, Pizza darüber.** Wir haben eine komplette Custom-Item-Pipeline gebaut: eigenes GetItem (`GI_LIVEGEN_MARIO=0x7E` als unbelegter Slot), eigene Draw-Funktion (Mario-DL über Links Kopf), eigener Textbox (`"Squadala!"` in DE/EN/FR), Slow-Chest-Cutscene per `VB_PLAY_SLOW_CHEST_CS` Hook — alles **additiv**, kein einziger vanilla Item/Message überschrieben. Über der Truhe rotiert eine Pizza als showcase-decoration.

🌐 **GLB-Importer mit trimesh.** Der Mesh-Loader ist jetzt format-agnostisch (`tooling/mesh_to_dl.py`). PBR-Materials werden zu Per-Face-Vertex-Farben aufgelöst, Multi-Primitive-Scenes (Pizza = Crust + Cheese + Toppings) werden zu einer Vertex/Triangle-Liste gemerged.

## Builds

### Sidecar
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 04.05.2026 | Abgeschlossen |

### SoH-Fork
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 04.05.2026 | Abgeschlossen |

## Milestones

- **M5++ (Vollständiger Box-Raum):** Fertig — 6 Wände + Boden + Decke, Aktoren spawnen, Z-Buffer ok
- **M6 (Lebender Raum):** Teilweise — Aktor-Library + Object-ID-Mapping fertig, LLM-Prompt-Erweiterung steht noch aus
- **Custom Item System** (cross-cutting): Komplette additive Pipeline für eigene Truhen-Inhalte ohne Vanilla-Overrides

## Verzeichnisstruktur

```
v0.5/
├── README.md
├── sidecar_build_1.md
└── soh_build_1.md
```
