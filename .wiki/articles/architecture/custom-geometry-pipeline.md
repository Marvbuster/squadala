---
title: "Custom Geometry Pipeline — Working!"
created: 2026-05-03
updated: 2026-05-03
category: architecture
tags: [o2r, display-list, vertex, geometry, KRITISCH, working]
status: current
related:
  - architecture/otr-dl-resolution
  - architecture/o2r-reverse-engineering
  - architecture/deku-tree-binary-analysis
---

# Custom Geometry Pipeline

> **STATUS: FUNKTIONIERT.** v0.4.0 (03.05.2026). Vier farbige Triangles rendern in unserem Custom-Raum.

## Komplette Pipeline

```
Python (build_box_room.py)
   │
   ├─ Vertex-Daten + Farben → OVTX Resource (Type 0x4F565458)
   │   └─ 0x40 Header + uint32 count + N×16B vertex data
   │
   ├─ Triangles + Render-State → TLDO Resource (Type 0x4F444C54)
   │   └─ 0x40 Header + ucode=4 + GBI commands (LE)
   │       ├─ G_RDPPIPESYNC
   │       ├─ G_SETOTHERMODE_H (1-cycle)
   │       ├─ G_SETOTHERMODE_L (Render Mode, sft=3!)
   │       ├─ G_GEOMETRYMODE (clear all + G_SHADE | G_SHADING_SMOOTH)
   │       ├─ G_SETCOMBINE (G_CC_SHADE)
   │       ├─ G_VTX_OTR_HASH (16B, hash der OVTX Resource)
   │       ├─ G_TRI2 / G_TRI1
   │       └─ G_ENDDL
   │
   ├─ Room Header → MORO Resource (SetMesh Type 0 → DL-Pfad)
   ├─ Scene Header → MORO Resource (RoomList → Room-Pfad, CollisionHeader → Collision-Pfad)
   └─ Collision → LOCO Resource (mit gültigem CamData-Eintrag!)
   
   → ZIP packen → .o2r File

SoH-Side (HotReload):
   ├─ ArchiveManager::AddArchive(o2r_path)
   ├─ ResourceManager::UnloadResource (für jede überschriebene Datei)
   ├─ ResourceManager::LoadResourceProcess (Preload — wichtig!)
   └─ WarpToEntrance(0x0000)

Engine-Hooks:
   ├─ Scene_CommandCollisionHeader: re-resolve Collision aus Cache
   ├─ OTRfunc_8009728C: blockt roomNum != 0 wenn Debug Room aktiv
   └─ OTRPlay_InitScene: nullt transiActorCtx nach Scene Commands

Render Pipeline:
   ├─ z_room.c::func_80095AB4 (Type 0 Draw)
   │   └─ gSPDisplayList(POLY_OPA_DISP++, dlist.opa)
   │       (dlist.opa ist ein __OTR__-String-Pointer!)
   │
   ├─ GbiWrap.cpp::gSPDisplayList (custom wrapper)
   │   ├─ ResourceMgr_OTRSigCheck → erkennt __OTR__ prefix
   │   ├─ ResourceMgr_LoadGfxByName → lädt Resource, returns Gfx*
   │   └─ __gSPDisplayList → schreibt echten Pointer in DL Buffer
   │
   ├─ Interpreter::Run → execute DL commands
   │   ├─ G_VTX_OTR_HASH → ResourceManager.GetResourceRawPointer(hash)
   │   │   └─ Lädt unsere OVTX Vertices, vtx[idx] in `loaded_vertices[]`
   │   └─ G_TRI2 / G_TRI1 → Interpreter::GfxSpTri1
   │       └─ Rasterizer → Pixel auf dem Bildschirm 🎉
```

## Kritische Erkenntnisse (in Reihenfolge der Entdeckung)

### 1. `__OTR__` DL Resolution

Siehe [OTR DL Resolution](otr-dl-resolution.md). Resolution passiert in `GbiWrap.cpp`, NICHT im Interpreter. Beim Schreiben in den Display-List-Buffer.

### 2. Resource Cache Identifier

`ResourceIdentifier` Cache-Keys haben `{Path, Owner, Parent}`. Defaults sind `{path, 0, nullptr}`. Eviction muss exakt diese Defaults nutzen — andernfalls trifft sie nicht den richtigen Cache-Eintrag.

### 3. Scene NICHT Evicten

`play->roomList`, `play->colCtx` halten Pointer in die Scene-Resource. Wenn die Scene aus dem Cache evictet wird (shared_ptr drop), zeigen diese Pointer ins Nichts → Crash.

**Workaround:** Scene gecacht lassen. Stattdessen `Scene_CommandCollisionHeader` patchen sodass Collision per `LoadResourceProcess()` neu aufgelöst wird:

```cpp
if (!cmdCol->fileName.empty()) {
    auto resource = ResourceManager->LoadResourceProcess(cmdCol->fileName);
    auto collision = std::static_pointer_cast<SOH::CollisionHeader>(resource);
    if (collision) cmdCol->collisionHeader = collision;
}
BgCheck_Allocate(&play->colCtx, play, (CollisionHeader*)cmdCol->GetRawPointer());
```

Die Collision liegt in unserem (priorisierten) Archive, also lädt `LoadResourceProcess` unsere Custom-Version.

### 4. Camera-Crash bei leerer CollisionHeader

`Camera_Update → func_80041A4C` greift auf `cameraDataList[0]` zu. Wenn `camDataCount=0` ist und `camPosDataSeg=NULL` → Crash.

**Fix:** Mindestens 1 CamData-Eintrag mit `cameraSType=0, numCameras=0, camPosDataIdx=0` und `camPosCount=0`. Die Factory bindet dann `camData[0].camPosData = &camPosDataZero` (Fallback). Kein Crash.

### 5. Hot-Reload Race Condition

Wenn man Resources im ImGui-Button-Handler evictet, sind die Display-List-Buffer noch in Bearbeitung → Use-After-Free → Crash mit Garbage-Opcodes.

**Fix:** Set Flag im Button-Handler, do Eviction in `UpdateElement()` (zwischen Frames sicher).

### 6. Transition Actors

Selbst nach `transiActorCtx.numActors = 0` werden Transition Actors während `Actor_SpawnTransitionActors()` gespawnt. Die laufen dann als reguläre Actors weiter und triggern Room-Wechsel.

**Fix:** Bei aktivem Debug-Room `Actor_SpawnTransitionActors` komplett skippen + `transiActorCtx.list = nullptr` setzen + `OTRfunc_8009728C` für `roomNum != 0` blocken.

### 7. **Der entscheidende Bug — `G_MDSFT_RENDERMODE = 3`!**

Aus `gbi.h`:
```c
#define G_MDSFT_RENDERMODE  3
#define G_MDSIZ_RENDERMODE  29
```

Encoded:
```
w0 = (G_SETOTHERMODE_L << 24) | ((32 - sft - len) << 8) | (len - 1)
   = (0xE2 << 24) | ((32 - 3 - 29) << 8) | 28
   = 0xE200001C
```

NICHT `0xE200031C` (sft=0)! Mit `sft=0` werden Bits 0-28 geschrieben, mit `sft=3` Bits 3-31. Die echten Render-Mode-Bits liegen in 3-31. Mit dem falschen Shift ist FORCE_BL nie gesetzt → Pixel werden verworfen.

Gefunden durch Hex-Dump-Vergleich mit `ydan_room_0DL_0033F0` (originale Deku-Tree-DL).

## Default Render-State

Was funktioniert:
- **Cycle Type:** 1-cycle (`G_CYC_1CYCLE = 0`, sft=20, len=2)
- **Render Mode:** `G_RM_OPA_SURF | G_RM_OPA_SURF2` = `0x0F0A4000` (FORCE_BL, kein Z-Test im Test, kein AA)
- **Geometry Mode:** `G_SHADE | G_SHADING_SMOOTH` (kein Lighting, kein Cull für Test)
- **Combiner:** `G_CC_SHADE` (w0=0xFC000000, w1=0x00020904) — Vertex-Farben

## Sichtbares Resultat

Vier Triangles in den 4 Himmelsrichtungen um Origin:
- 🔴 Norden (Z=-500): Rot
- 🟢 Süden (Z=+500): Grün
- 🔵 Osten (X=+500): Blau
- 🟡 Westen (X=-500): Gelb

## Nächste Schritte

- Box-Raum mit allen 6 Wänden + Boden + Decke (24 Vertices, 12 Triangles)
- Spawn-Position aus Custom-Scene respektieren (aktuell wird Original-Spawn genommen)
- Texturen statt nur Vertex-Farben
- LLM-spezifizierte Meshes (DungeonSpec → Geometry-Generator)
