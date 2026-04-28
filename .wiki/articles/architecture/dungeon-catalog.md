---
title: "OoT Dungeon-Katalog"
created: 2026-04-29
updated: 2026-04-29
category: architecture
tags: [dungeons, rooms, connectivity, templates, exits, hub, dead-end]
status: current
related:
  - architecture/soh-scene-format
  - architecture/dungeon-schema
---

# OoT Dungeon-Katalog — Raum-Connectivity

> Alle 10 Dungeons mit Raum-Verbindungen, Exit-Anzahl und Klassifizierung.

## Übersicht

| Dungeon | Scene | Räume | Hub (Exits) | Dead Ends | Struktur |
|---------|-------|-------|-------------|-----------|----------|
| Deku Tree | ydan | 12 | Room 3 (4) | 4 | Linear + Branch |
| Dodongo's Cavern | ddan | 17 | Room 0 (6) | 6 | Hub & Spoke |
| Jabu-Jabu's Belly | bdan | 16 | Room 7 (6) | 8 | Multi-Hub |
| Forest Temple | Bmori1 | 23 | Room 2 (7) | 4 | Complex Loop |
| Fire Temple | HIDAN | 27 | Room 1+10 (6+6) | 6 | Dual Hub |
| Water Temple | MIZUsin | 23 | Room 0 (10) | 9 | Central Hub |
| Shadow Temple | HAKAdan | 23 | 4 Hubs (je 4) | 11 | Linear Chain |
| Spirit Temple | jyasinzou | 29 | Room 5 (7) | 6 | Split Path |
| Ganon's Castle | ganontika | 20 | Room 1 (8) | 8 | Hub + Trials |
| Ice Cavern | ice_doukutu | 12 | Room 3 (4) | 3 | Linear |
| **Gesamt** | | **202** | | | |

Boss-Räume sind **separate Scenes** (17 zusätzliche Räume).

## Deku Tree (ydan_scene)

```
Room 0 (Entrance) ──→ Room 1 ──→ Room 2 (dead end)
    │                     
    ├──→ Room 3 (Hub, 4 exits) ──→ Room 4 ──→ Room 5 ──→ Room 6 ──→ Room 7 ──→ Room 8 (dead end)
    │         │
    │         └──→ Room 9 ──→ Room 11 (pre-boss, dead end)
    │
    └──→ Room 10 (dead end)
```

| Room | Exits | Verbindungen | Typ |
|------|-------|-------------|-----|
| 0 | 3 | [1, 3, 10] | Entrance |
| 1 | 2 | [0, 2] | Corridor |
| 2 | 1 | [1] | Dead End |
| 3 | 4 | [0, 4, 7, 9] | Hub |
| 4 | 2 | [3, 5] | Corridor |
| 5 | 2 | [4, 6] | Corridor |
| 6 | 2 | [5, 7] | Corridor |
| 7 | 3 | [3, 6, 8] | Junction |
| 8 | 1 | [7] | Dead End |
| 9 | 2 | [3, 11] | Corridor |
| 10 | 1 | [0] | Dead End |
| 11 | 1 | [9] | Pre-Boss |

## Dodongo's Cavern (ddan_scene)

| Room | Exits | Verbindungen | Typ |
|------|-------|-------------|-----|
| 0 | 6 | [1, 2, 4, 5, 7, 9] | Hub |
| 1 | 3 | [0, 3, 11] | Junction |
| 2 | 3 | [0, 5, 15] | Junction |
| 3 | 4 | [1, 4, 10, 12] | Hub |
| 4 | 3 | [0, 3, 13] | Junction |
| 5 | 2 | [0, 2] | Corridor |
| 6 | 1 | [9] | Dead End |
| 7 | 3 | [0, 8, 16] | Junction |
| 8 | 2 | [7, 14] | Corridor |
| 9 | 4 | [0, 6, 10, 12] | Hub |
| 10 | 2 | [3, 9] | Corridor |
| 11 | 1 | [1] | Dead End |
| 12 | 2 | [3, 9] | Corridor |
| 13 | 1 | [4] | Dead End |
| 14 | 1 | [8] | Dead End |
| 15 | 1 | [2] | Dead End |
| 16 | 1 | [7] | Pre-Boss |

## Jabu-Jabu's Belly (bdan_scene)

| Room | Exits | Verbindungen | Typ |
|------|-------|-------------|-----|
| 0 | 1 | [1] | Entrance |
| 1 | 5 | [0, 2, 4, 5, 14] | Hub |
| 2 | 3 | [1, 3, 7] | Junction |
| 3 | 4 | [2, 6, 13, 14] | Hub |
| 4 | 2 | [1, 6] | Corridor |
| 5 | 2 | [1, 15] | Corridor |
| 6 | 2 | [3, 4] | Corridor |
| 7 | 6 | [2, 8, 9, 10, 11, 12] | Hub |
| 8-12 | 1 | [7] | Dead End |
| 13 | 1 | [3] | Dead End |
| 14 | 2 | [1, 3] | Corridor |
| 15 | 1 | [5] | Pre-Boss |

## Forest Temple (Bmori1_scene)

| Room | Exits | Verbindungen | Typ |
|------|-------|-------------|-----|
| 0 | 1 | [1] | Entrance |
| 1 | 2 | [0, 2] | Corridor |
| 2 | 7 | [1, 3, 4, 5, 7, 8, 17] | Main Hub |
| 3 | 2 | [2, 16] | Corridor |
| 4 | 2 | [2, 6] | Corridor |
| 5 | 2 | [2, 11] | Corridor |
| 6 | 3 | [4, 12, 13] | Junction |
| 7 | 4 | [2, 9, 10, 15] | Hub |
| 8 | 6 | [2, 9, 10, 11, 18, 21] | Hub |
| 9-10 | 2 | [7, 8] | Corridor |
| 11 | 3 | [5, 8, 19] | Junction |
| 12 | 2 | [6, 19] | Corridor |
| 13 | 2 | [6, 20] | Corridor |
| 14 | 1 | [20] | Dead End |
| 15 | 3 | [7, 16, 20] | Junction |
| 16 | 2 | [3, 15] | Corridor |
| 17 | 2 | [2, 22] | Corridor |
| 18 | 1 | [8] | Dead End |
| 19 | 3 | [11, 12, 21] | Junction |
| 20 | 3 | [13, 14, 15] | Junction |
| 21 | 2 | [8, 19] | Corridor |
| 22 | 1 | [17] | Pre-Boss |

## Water Temple (MIZUsin_scene)

| Room | Exits | Verbindungen | Typ |
|------|-------|-------------|-----|
| 0 | 10 | [1,3,4,5,9,10,11,12,17,20] | Central Hub |
| 1 | 2 | [0, 2] | Corridor |
| 2-4 | 1 | [0/1] | Dead End |
| 5 | 2 | [0, 6] | Corridor |
| 6 | 2 | [5, 13] | Corridor |
| 7 | 2 | [13, 21] | Corridor |
| 8 | 2 | [9, 21] | Corridor |
| 9 | 2 | [0, 8] | Corridor |
| 10 | 1 | [0] | Dead End |
| 11 | 2 | [0, 22] | Corridor |
| 12 | 4 | [0, 14, 15, 16] | Hub |
| 13 | 2 | [6, 7] | Corridor |
| 14-15 | 2 | [12, 14/15] | Corridor |
| 16-20 | 1 | [...] | Dead End |
| 21 | 2 | [7, 8] | Corridor |
| 22 | 1 | [11] | Pre-Boss |

## Dungeon-Design-Patterns

### Erkannte Muster für Template-Generierung:

1. **Hub & Spoke** (Dodongo, Water, Ganon): Ein zentraler Raum mit vielen Exits
2. **Linear Chain** (Shadow, Ice): Räume in Reihe, gelegentliche Abzweigungen
3. **Multi-Hub** (Jabu, Fire): Mehrere Hub-Räume verbunden
4. **Complex Loop** (Forest): Verschlungene Pfade die sich kreuzen
5. **Split Path** (Spirit): Parallele Wege (Child/Adult) die sich am Hub treffen

### Raum-Typen für Templates:

| Typ | Exits | Beschreibung | Beispiele |
|-----|-------|-------------|-----------|
| Entrance | 1-3 | Eingangsraum, verbindet Overworld mit Dungeon | ydan_0, bdan_0 |
| Hub | 4-10 | Zentraler Raum mit vielen Abzweigungen | MIZUsin_0 (10!), Bmori1_2 (7) |
| Junction | 3 | Kreuzung, T-Stück | ydan_7, HIDAN_5 |
| Corridor | 2 | Verbindungsgang zwischen Räumen | Die meisten Räume |
| Dead End | 1 | Sackgasse — oft mit Puzzle oder Chest | Viele |
| Pre-Boss | 1 | Letzter Raum vor dem Boss | ydan_11, ddan_16 |
| Boss Arena | 0-1 | Boss-Kampf (separate Scene) | Eigene Scenes |
