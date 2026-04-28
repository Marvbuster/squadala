---
title: "SoH Scene/Room Format"
created: 2026-04-29
updated: 2026-04-29
category: architecture
tags: [o2r, scene, room, binary-format, collision, actors, transitions]
status: current
related:
  - architecture/dungeon-catalog
  - architecture/hybrid-architecture
  - architecture/dungeon-schema
code_refs:
  - soh-source/soh/soh/resource/importer/SceneFactory.cpp
  - soh-source/soh/soh/resource/type/scenecommand/SetTransitionActorList.h
  - soh-source/soh/soh/resource/type/CollisionHeader.h
  - soh-source/soh/include/z64scene.h
---

# SoH Scene/Room Format — Technische Referenz

> Erkenntnisse aus Analyse von SoH-Sourcecode und `.o2r`-Archiven.

## 1. .o2r Dateiformat

Die `.o2r`-Datei ist ein **ZIP-Archiv** mit serialisierten Ressourcen. Jede Ressource hat einen 0x40-Byte-Header:

```
0x00: 4 bytes padding
0x04: 4 bytes magic (z.B. "MORO" für Scenes, "XETO" für Texturen)
0x08: Version/Flags
0x0C: 0xDEADBEEF marker
0x40+: Ressource-spezifische Daten
```

### Magic Numbers

| Magic | Hex | Typ |
|-------|-----|-----|
| MORO | 4D4F524F | Scene/Room |
| XETO | 5845544F | Texture |
| OCOL | 4F434F4C | Collision Header |
| ORCM | 4F52434D | Scene Command |
| OSKL | 4F534B4C | Skeleton |
| OPTH | 4F505448 | Path |

## 2. Scene-Aufbau

Eine Scene besteht aus **Scene Commands** — serialisiert nach dem 0x40-Header:

```
[0x40] uint32 commandCount
[0x44] Command[] commands
```

### Scene Command IDs

| ID | Name | Beschreibung |
|----|------|-------------|
| 0 | StartPositionList | Spieler-Spawnpunkte |
| 1 | ActorList | Gegner, Items, NPCs |
| 3 | CollisionHeader | Pfad zur Kollisions-Ressource |
| 4 | RoomList | Liste der Raum-Dateien |
| 6 | EntranceList | Eingangs-Definitionen |
| 7 | SpecialObjects | Elf-Message + Global-Object |
| 8 | RoomBehavior | Raum-Verhalten |
| 10 | Mesh | Display Lists (Grafik) |
| 11 | ObjectList | Benötigte Objekt-Dateien |
| 12 | LightList | Dynamische Lichter |
| 13 | PathList | NPC-Pfade |
| 14 | TransitionActorList | Türen zwischen Räumen |
| 15 | LightSettings | Beleuchtungsprofile |
| 16 | TimeSettings | Tageszeit |
| 17 | SkyboxSettings | Himmel |
| 19 | ExitList | Ausgänge (zu anderen Scenes) |
| 20 | EndMarker | Ende der Command-Liste |

## 3. TransitionActorEntry (Türen)

16 Bytes pro Eintrag:

```c
struct TransitionActorEntry {
    struct { s8 room; s8 effects; } sides[2]; // Vorder-/Rückseite
    s16 id;        // Actor-ID (Tür-Typ)
    Vec3s pos;     // X, Y, Z Position
    s16 rotY;      // Rotation
    s16 params;    // Parameter
}; // 0x10 = 16 bytes
```

- `sides[0].room` = Raum auf der Vorderseite der Tür
- `sides[1].room` = Raum auf der Rückseite
- `id` = Tür-Actor-ID (verschiedene Tür-Modelle)
- `params` = Schlüssel-Anforderungen etc.

## 4. ActorEntry (Gegner/Items)

16 Bytes pro Eintrag:

```c
struct ActorEntry {
    s16 id;        // Actor-Typ (aus actor_table.h)
    Vec3s pos;     // X, Y, Z Position
    Vec3s rot;     // Rotation (yaw, pitch, roll)
    s16 params;    // Actor-spezifische Parameter
}; // 0x10 = 16 bytes
```

## 5. CollisionHeader

```c
struct CollisionHeaderData {
    Vec3s minBounds, maxBounds;    // Raum-Begrenzung
    u16 numVertices;
    Vec3s* vtxList;                // 3D-Vertices
    u16 numPolygons;
    CollisionPoly* polyList;       // Kollisions-Polygone
    SurfaceType* surfaceTypeList;  // Boden-Typen
    CamData* cameraDataList;       // Kamera-Daten
    u16 numWaterBoxes;
    WaterBox* waterBoxes;          // Wasser-Bereiche
};
```

## 6. Raum-Dateien

Jeder Raum ist eine eigene Ressource im ZIP:
```
scenes/nonmq/{scene_name}/{scene_name}_room_{N}
```

Ein Raum enthält:
- Room-Header (Actor-Referenzen, Mesh-Typ)
- ActorEntry-Listen
- Display Lists (DL_XXXXXX)
- Vertex-Daten (Vtx_XXXXXX)
- Texturen (Tex_XXXXXX)

## 7. Alt-Asset-System (Mods)

- Pfad-Präfix `alt/` vor dem Original-Pfad
- Beispiel: `alt/textures/vr_LHVR_static/gLinksHouseBgTex`
- Letztes geladenes Archiv (alphabetisch) gewinnt
- `ResourceMgr_FileAltExists(path)` prüft ob Alternative existiert

## 8. Randomizer-Entrance-System

```c
struct EntranceOverride {
    uint16_t type;               // EntranceType enum
    int16_t index;               // Original-Eingang
    int16_t destination;         // Original-Ziel
    int16_t override;            // Neues Ziel
    int16_t overrideDestination; // Alternatives Ziel
};
```

Relevante Funktionen:
- `Entrance_GetOverride(index)` — Shuffled Destination lookup
- `Entrance_OverrideNextIndex(nextEntranceIndex)` — Eingang umleiten

## 9. Quellcode-Referenzen (soh-source/)

| Datei | Inhalt |
|-------|--------|
| `soh/include/z64scene.h` | Scene-Strukturen |
| `soh/include/z64actor.h` | Actor-Definitionen |
| `soh/include/tables/scene_table.h` | Scene-IDs |
| `soh/include/tables/entrance_table.h` | Entrance-IDs |
| `soh/soh/resource/importer/SceneFactory.cpp` | Scene-Parser |
| `soh/soh/resource/importer/scenecommand/` | Command-Factories |
| `soh/soh/resource/type/scenecommand/` | Command-Typen |
| `soh/soh/Enhancements/randomizer/entrance.h` | Entrance-Shuffling |
| `soh/soh/Enhancements/randomizer/dungeon.h` | Dungeon-Info |
| `libultraship/include/ship/resource/archive/O2rArchive.h` | .o2r ZIP-Format |
