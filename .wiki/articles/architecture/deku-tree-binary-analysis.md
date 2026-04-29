---
title: "Deku Tree Binary Analysis"
created: 2026-04-29
updated: 2026-04-29
category: architecture
tags: [o2r, binary, deku-tree, scene-header, room-header, reverse-engineering, WICHTIG]
status: current
related:
  - architecture/o2r-reverse-engineering
  - architecture/soh-scene-format
---

# Deku Tree Binary Analysis

> **WICHTIG:** Dies ist die Referenz-Analyse die als Vorlage für unseren Scene-Writer dient.
> Jedes Byte wurde aus der echten `oot.o2r` gelesen und gegen den SoH-Sourcecode verifiziert.

## 1. Scene Header (`ydan_scene`)

**Dateigröße:** 1167 Bytes | **Magic:** MORO | **Commands:** 12

### Resource Header (0x00-0x3F)

Alle Resources in .o2r haben denselben 64-Byte Header:

```
0x00: 00 00 00 00          Padding
0x04: 4D 4F 52 4F          Magic "MORO" (Scene/Room)
0x08: 00 00 00 00          Version/Flags (0 für Scene)
0x0C: EF BE AD DE          DEADBEEF Marker
0x10: EF BE AD DE          DEADBEEF Marker  
0x14: 00 × 44              Padding bis 0x3F
```

### Scene Commands (ab 0x40)

```
0x40: 0C 00 00 00          uint32 commandCount = 12
```

| # | Offset | Cmd ID | Name | Payload Size | Beschreibung |
|---|--------|--------|------|-------------|-------------|
| 0 | 0x0044 | 21 | SoundSettings | 3 B | reverb=3 nature=0x13 seq=0x1C |
| 1 | 0x004B | 4 | RoomList | variabel | 12 Rooms mit Pfaden + VROM |
| 2 | 0x0289 | 14 | TransitionActorList | 4+12×16 | 12 Türen |
| 3 | 0x0351 | 25 | Cutscenes | variabel | Intro-Cutscene |
| 4 | ? | 6 | EntranceList | 4+N×2 | Spawn-Punkte |
| 5 | ? | 15 | LightSettings | 4+N×22 | Beleuchtung |
| 6 | ? | 3 | CollisionHeader | 4+pathLen | Pfad zur Collision |
| 7 | ? | 7 | SpecialObjects | 3 | elf + object |
| 8 | ? | 17 | SkyboxSettings | 3 | sky + weather + indoor |
| 9 | ? | 16 | TimeSettings | 3 | Tageszeit |
| 10 | ? | 22 | EchoSettings | 1 | Hall-Effekt |
| 11 | ? | 20 | EndMarker | 0 | Ende |

### Exakte Command Payloads

**SoundSettings (ID=21):** `int8 reverb, int8 natureAmbienceId, int8 seqId`

**RoomList (ID=4):**
```
uint32 numRooms
per Room:
  uint32 pathLength
  char[pathLength] path (null-terminated, z.B. "scenes/nonmq/ydan_scene/ydan_room_0\0")
  uint32 vromStart
  uint32 vromEnd
```

**TransitionActorList (ID=14):**
```
uint32 numTransitions
per Transition (16 bytes):
  int8  frontRoom
  int8  frontEffects  
  int8  backRoom
  int8  backEffects
  int16 actorId        (0x002E = Standard-Dungeon-Tür, 0x0023 = andere Tür)
  int16 posX, posY, posZ
  int16 rotY
  uint16 params
```

### Türen des Deku Tree (12 Transitions)

```
[0]  R0 <-> R1   actor=0x002E pos=(-455, 400, 455)    rotY=-8192
[1]  R5 <-> R6   actor=0x002E pos=(-1535,-760, 1070)   rotY=-16384
[2]  R3 <-> R4   actor=0x002E pos=(-75, -880, 580)     rotY=0
[3]  R8 <-> R7   actor=0x002E pos=(-2420,-760,-453)    rotY=8192
[4]  R11<-> R9   actor=0x002E pos=(-896,-1880,-964)    rotY=4187
[5]  R2 <-> R1   actor=0x002E pos=(-936, 400, 936)     rotY=24576
[6]  R0 <-> R10  actor=0x002E pos=(-560, 800, 0)       rotY=-16384
[7]  R7 <-> R6   actor=0x002E pos=(-1855,-760, 770)    rotY=0
[8]  R5 <-> R4   actor=0x002E pos=(-335,-880, 960)     rotY=16384
[9]  R0 <-> R3   actor=0x0023 pos=(0,  -320, 0)        rotY=-16384  ← Anderer Tür-Typ!
[10] R3 <-> R9   actor=0x0023 pos=(-635,-1100, 0)      rotY=-16384
[11] R7 <-> R3   actor=0x0023 pos=(-1055,-820, 0)      rotY=16384
```

---

## 2. Room Header (`ydan_room_0`)

**Dateigröße:** 1047 Bytes | **Magic:** MORO | **Commands:** 8

### Room Commands

| # | Cmd ID | Name | Beschreibung |
|---|--------|------|-------------|
| 0 | 22 | EchoSettings | echo=7 |
| 1 | 8 | RoomBehavior | flags=1 flags2=0x0 |
| 2 | 18 | SkyboxModifier | disableSky=1 disableSun=1 (Innenraum) |
| 3 | 16 | TimeSettings | 255:255 speed=0 (eingefrorene Zeit) |
| 4 | 10 | **SetMesh** | Type 2, 7 DList-Paare |
| 5 | 11 | ObjectList | 11 Objekte |
| 6 | 1 | ActorList | 27 Actors |
| 7 | 20 | EndMarker | — |

### SetMesh Details (Type 2 — 3D mit Culling)

```
int8  data = 0 (unused)
int8  meshType = 2
int8  polyNum = 7

per Polygon:
  int8  polyType (unused)
  int16 posX, posY, posZ    ← Culling-Position
  int16 unk_06              ← Culling-Radius?
  string opaPath            ← Opaque Display List (ZIP-Pfad)
  string xluPath            ← Translucent Display List (ZIP-Pfad)
```

**WICHTIG:** Die DL-Pfade verweisen auf andere Einträge im selben .o2r-ZIP!
Beispiel: `"scenes/nonmq/ydan_scene/ydan_room_0DL_0033F0"` → lädt die DL-Datei aus dem ZIP.

### Mesh-Einträge Room 0

| # | Position | Opaque DL | Translucent DL |
|---|----------|-----------|----------------|
| 0 | (-59,-790,80) | ydan_room_0DL_006D28 | — |
| 1 | (-198,-895,0) | — | ydan_room_0DL_012DD0 |
| 2 | (98,-790,0) | — | ydan_room_0DL_012C48 |
| 3 | (0,480,0) | ydan_room_0DL_005E00 | — |
| 4 | (0,250,0) | — | ydan_room_0DL_012460 |
| 5 | (0,90,748) | ydan_room_0DL_006738 | — |
| 6 | (-40,260,84) | ydan_room_0DL_0033F0 | ydan_room_0DL_011230 |

### ObjectList (11 Objekte)

```
0x0036, 0x001e, 0x0024, 0x0039, 0x0164, 
0x000e, 0x00a4, 0x012b, 0x00b7, 0x00bb, 0x015c
```

Diese Object-IDs müssen in der ObjectList stehen damit die Actors in diesem Raum funktionieren.
Jeder Actor-Typ braucht bestimmte Objects (Modelle, Animationen, Texturen).

### ActorList (27 Actors)

| Actor ID | Count | Typ (geschätzt) |
|----------|-------|-----------------|
| 0x0095 | 3 | Skulltulas |
| 0x0037 | 3 | Deku Babas |
| 0x0125 | 5 | Grass/Bushel |
| 0x0055 | 3 | Büsche |
| 0x000A | 1 | Chest |
| 0x000F | 1 | Spieler-Spawn? |
| 0x011B | 9 | Ranken/Spinnweben |
| 0x0015 | 2 | Türen/Ladezonen |

---

## 3. Erkenntnisse für den Scene-Writer

### Was wir für eine minimale Scene brauchen:

1. **Scene Header** mit:
   - SoundSettings (3 B)
   - RoomList (Pfade zu unseren Rooms)
   - TransitionActorList (Türen zwischen Rooms)
   - CollisionHeader (Pfad zur Collision-Datei)
   - EndMarker

2. **Pro Room** ein Room Header mit:
   - RoomBehavior (5 B)
   - SkyboxModifier (2 B) — disableSky=1 für Indoor
   - TimeSettings (3 B) — 255:255 für eingefrorene Zeit
   - SetMesh — **verweist auf DL-Dateien im ZIP**
   - ObjectList — muss die Objects aller Actors im Room enthalten
   - ActorList — Gegner, Items, Deko
   - EndMarker

3. **Pro Room** die referenzierten Dateien:
   - Display Lists (DL_XXXXXX) — Geometrie-Renderbefehle
   - Vertex-Daten (Vtx_XXXXXX) — 3D-Punkte
   - Texturen (Tex_XXXXXX) — Oberflächen

### String-Format in .o2r

```
uint32 length (inklusive Null-Terminator)
char[length] string (null-terminated)
```

Leerer String: `00 00 00 00` (length=0, kein Content)

### Payload-Größen pro Command (VERIFIZIERT)

| Command | ID | Payload |
|---------|-----|---------|
| SoundSettings | 21 | 3 Bytes (int8 × 3) |
| RoomBehavior | 8 | **5 Bytes** (int8 + int32) ← ACHTUNG: nicht 8! |
| EchoSettings | 22 | 1 Byte |
| SkyboxModifier | 18 | 2 Bytes |
| TimeSettings | 16 | 3 Bytes |
| SkyboxSettings | 17 | 3 Bytes |
| SpecialObjects | 7 | 3 Bytes (int8 + int16) |
| CameraSettings | 23 | 1 Byte |
| EndMarker | 20 | 0 Bytes |
| RoomList | 4 | uint32 count + count × (string + 2×uint32) |
| ActorList | 1 | uint32 count + count × 16 Bytes |
| TransitionActorList | 14 | uint32 count + count × 16 Bytes |
| ObjectList | 11 | uint32 count + count × 2 Bytes |
| EntranceList | 6 | uint32 count + count × 2 Bytes |
| ExitList | 19 | uint32 count + count × 2 Bytes |
| LightSettings | 15 | uint32 count + count × 22 Bytes |
| CollisionHeader | 3 | string (Pfad zur Collision-Datei) |
| SetMesh | 10 | KOMPLEX — siehe oben |
