# OoT Live Dungeon v0.6 — M6 Lebender Raum + Items-Showcase

**Zeitraum:** Mai 2026
**Fokus:** LLM-Output → Custom-Geometry-Pipeline durchgängig, vollständige Aktor-Library, Items-Showcase im Debug-Raum

## Highlights

🌉 **M6 ist fertig.** Der DungeonSpec aus dem LLM landet jetzt durchgängig in der Custom-Geometry-Pipeline. Neue Bridge `livegen.compiler.box_room_dungeon` mapped abstract `Actor(type, count)` und `Chest(id, contents)` auf konkrete Placements, die HTTP-Endpoints `/compile` und `/dungeons/{id}/activate` benutzen sie statt den alten vanilla-Deku-Tree-Compiler.

📚 **Vollständige ACTOR_LIBRARY** — alle 21 `ActorType`s aus dem Schema sind jetzt in `tooling/build_box_room.py` mapped (skulltula, stalfos, lizalfos, wolfos, freezard, dinolfos, gibdo, redead, poe, floormaster, wallmaster, armos, beamos, like_like, bubble, torch_slug, dodongo, plus die schon vorhandenen). Plus `item00` für En_Item00-Drops mit allen 27 Drop-Varianten.

🎁 **Debug-Raum ist länger und voller.** Box ist jetzt 1200 × 600 × **3000** (verdreifacht in Z), und entlang der westlichen Längsachse stehen 26 verschiedene En_Item00-Drops auf dem Boden — Rupees, Hearts, Bombs, Arrows, Sticks, Shields, Tunics, Bombchu, Magic, Keys, Heart Container, Heart Piece — alles was im Original herumliegen kann.

🛡️ **Defensive Item_Give-Guard.** Ein 1-Liner-Null-Check für `Item_Give(ITEM_NONE)` schützt vor OOB-Read in `gItemSlots[0xFF]` — nicht nur für unsere Spectacle-Items, sondern für alle Aufrufer.

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

- **M6 (Lebender Raum):** Fertig — LLM-Spec → Custom-Geometry-`.o2r` mit Aktoren aus dem Spec, vollständige Library
- **M7 (Multi-Room):** Geplant — Cupcake in Room 2, En_Holl Connector

## Verzeichnisstruktur

```
v0.6/
├── README.md
├── sidecar_build_1.md
└── soh_build_1.md
```
