---
title: "O2R Reverse Engineering — Checkliste"
created: 2026-04-29
updated: 2026-04-29
category: architecture
tags: [o2r, reverse-engineering, binary, scene, room, collision, display-list]
status: current
related:
  - architecture/soh-scene-format
  - architecture/dungeon-catalog
code_refs:
  - soh-source/soh/soh/resource/importer/SceneFactory.cpp
  - soh-source/soh/soh/resource/importer/scenecommand/
  - soh-source/soh/soh/resource/type/scenecommand/
  - soh-source/soh/soh/resource/type/CollisionHeader.h
  - soh-source/OTRExporter/OTRExporter/
---

# O2R Reverse Engineering — Checkliste

> Ziel: Eine eigene .o2r Scene-Datei erzeugen die SoH als spielbaren Dungeon lädt.
> Methode: Existierende Scene aus oot.o2r auseinandernehmen, Format Byte-für-Byte dokumentieren, Writer bauen, Round-Trip-Test.

## Übersicht

```
scene.o2r (ZIP-Archiv)
│
├── scenes/shared/{name}_scene/
│   ├── {name}_scene                          ← [1] Scene Header
│   ├── {name}_sceneCollisionHeader_XXXXXX    ← [3] Collision Mesh  
│   ├── {name}_sceneTex_XXXXXX               ← [6] Scene-Texturen
│   ├── {name}_sceneTLUT_XXXXXX              ← [6] Textur-Paletten
│   │
│   ├── {name}_room_0                         ← [4] Room Header
│   ├── {name}_room_0ActorEntry_XXXXXX        ← [2] Actor Spawns
│   ├── {name}_room_0DL_XXXXXX               ← [5] Display Lists
│   ├── {name}_room_0Vtx_XXXXXX              ← [5] Vertex Daten
│   ├── {name}_room_0Tex_XXXXXX              ← [6] Room-Texturen
│   ├── {name}_room_0Set_XXXXXX              ← [4] Room Setup Variants
│   │
│   ├── {name}_room_1                         ← Raum 1...
│   └── ...
```

---

## Checkliste

### Phase 1: Analyse (Read)

- [x] **1.1** Referenz-Scene wählen (Deku Tree = einfachste) ✅
- [x] **1.2** Scene Header (`ydan_scene`) komplett Byte-für-Byte dumpen ✅
- [x] **1.3** Jeden Scene Command identifizieren und Grenzen markieren ✅ 12/12 Commands geparst
- [x] **1.4** Room Header (`ydan_room_0`) komplett dumpen ✅ 1047/1047 Bytes geparst
- [x] **1.5** Room Commands identifizieren (Mesh, ActorList, ObjectList) ✅ 8/8 Commands
- [x] **1.6** CollisionHeader komplett dumpen und Felder zuordnen ✅ 46108/46108 Bytes
- [x] **1.7** Display List Format verstanden ✅ TLDO magic, GBI commands, OTR-Opcodes
- [ ] **1.8** Vertex-Daten (`Vtx_XXXXXX`) dumpen — Format pro Vertex bestimmen
- [ ] **1.9** Textur-Referenzen verstehen — wie DLs auf Tex-Einträge verweisen
- [x] **1.10** Actor Entry Format verifiziert ✅ (16 Bytes: id, pos, rot, params)

### Phase 2: Dokumentation

- [ ] **2.1** Binary-Layout für jeden Resource-Typ dokumentieren (Header + Body)
- [ ] **2.2** Scene Command Serialisierung dokumentieren (ID + Payload pro Command)
- [ ] **2.3** Room Command Serialisierung dokumentieren
- [ ] **2.4** Collision Format dokumentieren (Vtx-Array + Poly-Array + SurfaceType + CamData)
- [ ] **2.5** Display List GBI-Befehlssatz dokumentieren (die in SoH verwendeten)
- [ ] **2.6** Vertex-Format dokumentieren (Position, UV, Color/Normal)
- [ ] **2.7** Textur-Referenzierung dokumentieren (TLUT-Zuordnung, Format-Flags)

### Phase 3: Round-Trip Test

- [x] **3.1** Python-Parser für Scene komplett ✅ (alle 12 Commands)
- [x] **3.2** Python-Parser für Room komplett ✅ (alle 8 Commands inkl. SetMesh)
- [x] **3.3** Round-Trip Tests:
  - ✅ Scene Header: 1167/1167 bytes PERFECT MATCH
  - ✅ Room Header: 1047/1047 bytes PERFECT MATCH
  - ✅ CollisionHeader: 46108/46108 bytes PERFECT MATCH
  - Fixes: SkyboxSettings=4B (nicht 3), Cutscenes empty=+1B padding
- [x] **3.4** Generierte .o2r in SoH laden und verifizieren ✅
  - Verbatim Room-Copy: funktioniert, kein Crash
  - Actor-Injection: funktioniert! 2 extra Töpfe sichtbar in Link's Haus
  - Mesh-Type-Wechsel (Type 1→0): crasht — Scene erwartet spezifischen Type
  - Override ohne alt/-Prefix auf Original-Pfad: funktioniert

### Phase 4: Minimale eigene Scene

- [ ] **4.1** Einfachsten möglichen Raum erzeugen: 1 Box, 4 Wände, Boden, Decke
- [ ] **4.2** Collision Mesh dafür generieren (6 Polygone für Box)
- [ ] **4.3** Display List für Box-Geometrie schreiben
- [ ] **4.4** Scene Header mit 1 Room, 1 Entrance, CollisionHeader
- [ ] **4.5** Als .o2r packen und in SoH laden — Link steht in einem Raum?
- [ ] **4.6** Actor hinzufügen (z.B. einen Pot oder Chest)
- [ ] **4.7** Tür-Actor hinzufügen der zu einer Original-Scene führt
- [ ] **4.8** Zweiten Raum hinzufügen mit Tür dazwischen

### Phase 5: Integration

- [ ] **5.1** Scene Compiler vervollständigen (`o2r_writer.py`)
- [ ] **5.2** DungeonSpec → .o2r Pipeline E2E testen
- [ ] **5.3** Entrance-Override in SoH: Tür → generierte Scene
- [ ] **5.4** Hot-Reload: .o2r zur Laufzeit laden ohne Neustart

---

## Detailformat: Resource Header

Jede Resource im .o2r-ZIP hat einen gemeinsamen Header:

```
Offset  Size  Beschreibung
0x00    4     Padding (00000000)
0x04    4     Magic ("MORO" für Scene, "XETO" für Texture, ...)
0x08    4     Endianness/Version (01000000 oder DEADBEEF)
0x0C    4     0xDEADBEEF marker
0x10    4     0xDEADBEEF marker
0x14    28    Padding (zeros)
0x40+         Resource-spezifische Daten
```

## Detailformat: Scene Header (nach 0x40)

```
Offset  Size  Beschreibung
0x40    4     Command Count (uint32 LE)
0x44+         Commands (sequentiell)
```

Jeder Command:
```
4 bytes   Command ID (int32 LE) — siehe SceneCommandID enum
N bytes   Command-spezifische Daten
```

### Scene Command Formate (aus Factory-Code)

| ID | Name | Payload |
|----|------|---------|
| 0 | StartPositionList | uint32 count + count × ActorEntry(16 bytes) |
| 1 | ActorList | uint32 count + count × ActorEntry(16 bytes) |
| 3 | CollisionHeader | uint32 pathLen + path string (null-terminated) |
| 4 | RoomList | uint32 count + count × (uint32 pathLen + path + uint32 vromStart + uint32 vromEnd) |
| 6 | EntranceList | uint32 count + count × uint16 |
| 7 | SpecialObjects | uint8 elfMessage + uint16 globalObject |
| 8 | RoomBehavior | uint32 gameplayFlags + uint32 gameplayFlags2 |
| 10 | Mesh | KOMPLEX — siehe SetMeshFactory |
| 11 | ObjectList | uint32 count + count × uint16 objectId |
| 12 | LightList | uint32 count + count × 22 bytes |
| 13 | PathList | uint32 count + count × (uint32 numPoints + numPoints × Vec3s(6 bytes)) |
| 14 | TransitionActorList | uint32 count + count × TransitionActorEntry(16 bytes) |
| 15 | LightSettings | uint32 count + count × 22 bytes |
| 16 | TimeSettings | uint8 hour + uint8 min + uint8 speed |
| 17 | SkyboxSettings | uint8 skyboxId + uint8 weather + uint8 indoors |
| 18 | SkyboxModifier | uint8 disableSky + uint8 disableSunMoon |
| 19 | ExitList | uint32 count + count × uint16 exitIndex |
| 20 | EndMarker | (keine Daten) |
| 21 | SoundSettings | uint8 reverb + uint8 nightSfx + uint8 bgm |
| 22 | EchoSettings | uint8 echo |

### ActorEntry Format (16 Bytes)

```
Offset  Size  Typ     Beschreibung
0x00    2     int16   Actor ID
0x02    2     int16   Position X
0x04    2     int16   Position Y
0x06    2     int16   Position Z
0x08    2     int16   Rotation X
0x0A    2     int16   Rotation Y
0x0C    2     int16   Rotation Z
0x0E    2     uint16  Params
```

### TransitionActorEntry Format (16 Bytes)

```
Offset  Size  Typ    Beschreibung
0x00    1     int8   Front Room
0x01    1     int8   Front Effects
0x02    1     int8   Back Room
0x03    1     int8   Back Effects
0x04    2     int16  Actor ID (Tür-Typ)
0x06    2     int16  Position X
0x08    2     int16  Position Y
0x0A    2     int16  Position Z
0x0C    2     int16  Rotation Y
0x0E    2     uint16 Params
```

### CollisionHeader Format

```
Offset  Size  Beschreibung
0x00    6     Vec3s minBounds (x, y, z als int16)
0x06    6     Vec3s maxBounds
0x0C    2     uint16 numVertices
0x0E    N     Vec3s[] vtxList (numVertices × 6 bytes)
...     2     uint16 numPolygons
...     N     CollisionPoly[] polyList (numPolygons × 16 bytes)
...     N     SurfaceType[] (numPolygons entries)
...     N     CamData[]
...     2     uint16 numWaterBoxes
...     N     WaterBox[] (numWaterBoxes × 16 bytes)
```

### CollisionPoly Format (16 Bytes)

```
Offset  Size  Typ     Beschreibung
0x00    2     uint16  Surface type index
0x02    2     uint16  Flags + Vertex A index
0x04    2     uint16  Flags + Vertex B index
0x06    2     uint16  Vertex C index
0x08    2     int16   Normal X (fixed point)
0x0A    2     int16   Normal Y
0x0C    2     int16   Normal Z
0x0E    2     int16   Plane distance
```

---

## Offene Fragen

- [ ] Wie genau serialisiert SetMesh (Command 10) die Display-List-Referenzen?
- [ ] Wie werden Texturen in der DL referenziert — über den ZIP-Pfad oder über Offsets?
- [ ] Welche OoT Objects müssen in der ObjectList stehen damit Türen/Chests funktionieren?
- [ ] Wie funktioniert das Entrance-System genau — kann man neue Scene-IDs registrieren?
- [ ] Braucht man `soh.o2r` oder `oot.o2r` Einträge um eine neue Scene zu registrieren?

## Quellen

| Quelle | Pfad | Nutzen |
|--------|------|--------|
| Scene Factory | `soh-source/soh/soh/resource/importer/SceneFactory.cpp` | Command-Parsing |
| Command Factories | `soh-source/soh/soh/resource/importer/scenecommand/*.cpp` | Einzelne Formate |
| OTRExporter | `soh-source/OTRExporter/OTRExporter/*.cpp` | Wie ROM→o2r konvertiert wird |
| ZAPD | `soh-source/ZAPDTR/ZAPD/ZRoom/` | Room-Strukturen |
| z64scene.h | `soh-source/soh/include/z64scene.h` | C-Structs |
| z64actor.h | `soh-source/soh/include/z64actor.h` | Actor-Format |
| CloudModding Wiki | wiki.cloudmodding.com/oot/ | Community-Dokumentation |
| OoT Decompilation | github.com/zeldaret/oot | Vollständige Referenz |
