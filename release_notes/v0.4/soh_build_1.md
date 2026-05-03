# OoT Live Dungeon SoH-Fork v0.4.0 Build 1

**Datum:** 03.05.2026 | **Status:** Abgeschlossen | **Milestone:** M5+

## Zusammenfassung

Engine-Hooks für Custom Geometry: Hot-Reload mit Resource-Eviction, Debug-Room-Modus blockt Room-Wechsel, Collision-Rebind sorgt für korrektes Custom-Collision-Loading auch bei gecachter Scene. Custom Display Lists werden über `__OTR__`-Pfade per `GbiWrap.cpp` resolved.

## Features & Änderungen

### LiveGen Panel

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | "Debug Room" Button im StatusBar — direkter Warp zu Custom-.o2r |
| FEATURE | Deferred Loading via `mDebugRoomPending` Flag → Eviction in `UpdateElement()` (zwischen Frames sicher) |
| FEATURE | `mDebugRoomActive` State — bleibt aktiv bis SoH-Neustart |
| FEATURE | Frame-Loop nullt `transiActorCtx.numActors` als Belt-and-Suspenders |

### LiveGen HotReload

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `SetDebugRoomActive(bool)` / `IsDebugRoomActive()` mit C-Bridge |
| FEATURE | Resource-Preload nach `AddArchive` — Room/Coll/DL/Vtx werden sofort gecacht (keine race condition) |
| FEATURE | `WarpToEntrance()` clearet `prevRoom.segment` + `curRoom.segment` für saubere Transition |
| FIX | Scene wird NICHT evicted (würde `play->roomList` dangling lassen → Crash) |

### z_play_otr.cpp

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Direkt nach `OTRScene_ExecuteCommands` Transition Actors nullen wenn Debug Room aktiv |

### z_scene_otr.cpp

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `OTRfunc_8009728C` blockt `roomNum != 0` wenn `LiveGen_IsDebugRoomActive()` |
| FEATURE | `OTRfunc_800973FC` skippt `Actor_SpawnTransitionActors` im Debug-Room-Modus |
| FIX | `Scene_CommandCollisionHeader` re-resolved Collision via `LoadResourceProcess()` — Custom Collision greift auch bei gecachter Scene |
| FEATURE | Erweitertes Room-Init-Logging (path, meshType, polyNum, cmds, isCustom) |

### ResourceManagerHelpers.cpp

| Typ | Beschreibung |
|-----|-------------|
| FIX | `ResourceMgr_LoadGfxByName` mit Null-Check + Logging — verhindert Crash wenn Resource fehlt |

### z_room.c

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Diagnostic-Logging für Type-0 Room-Draws (room->num, segment, opa, flags, polyNum) |

### libultraship/interpreter.cpp

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `gfx_vtx_hash_handler_custom` mit detailliertem Logging (hash, name, raw pointer, count, dst) |
| FEATURE | TRI1-Logging für Debug — counter wird beim Vertex-Load aktiviert |

## Architektur-Erkenntnisse

### `__OTR__` DL Resolution

Der Mechanismus war zwei Tage lang ein Mysterium. Die Lösung steckt in `GbiWrap.cpp`:

```cpp
extern "C" void gSPDisplayList(Gfx* pkt, Gfx* dl) {
    char* imgData = (char*)dl;
    if (ResourceMgr_OTRSigCheck(imgData) == 1) {
        dl = ResourceMgr_LoadGfxByName(imgData);  // Resolves __OTR__ path!
    }
    __gSPDisplayList(pkt, dl);
}
```

SoH wrapped das Standard-`gSPDisplayList`-Macro mit einem C-Hook der `__OTR__`-Strings erkennt und in echte `Gfx*`-Pointer auflöst. Die Resolution passiert beim _Schreiben_ in den Display-List-Buffer, nicht beim _Ausführen_ durch den Interpreter.

### Resource Cache Identifier

`ResourceIdentifier` Cache-Keys haben drei Felder: `{Path, Owner=0, Parent=nullptr}`. Eviction muss die gleichen Defaults nutzen die der Loader benutzt.

### Scene Eviction = Crash

`play->roomList` und Collision-Pointer zeigen in die Scene-Resource. Eviction der Scene macht diese Pointer dangling. Workaround: Scene gecacht lassen, stattdessen Collision-Rebind per `LoadResourceProcess()` in `Scene_CommandCollisionHeader`.

### Render-Mode Bug

`G_SETOTHERMODE_L` mit `sft=0` schreibt den Render-Mode 3 Bits zu niedrig — überschreibt Alpha-Compare und Depth-Source statt der Render-Mode-Bits. Korrekt: `G_MDSFT_RENDERMODE = 3`.

## Wiki-Updates

- `.wiki/articles/architecture/otr-dl-resolution.md` — Komplette Doku des `__OTR__`-DL-Resolution-Mechanismus mit GbiWrap

## Bekannte Limitationen

- Spawn-Position für Custom Scenes wird ignoriert (Original-Deku-Tree-Spawn wird verwendet) — daran liegt's dass Link erst fällt
- Kein Custom Skybox/Lighting (gecachte Scene-LightSettings werden verwendet)
- Original Deku-Tree-Fog (rotbraun) ist sichtbar wenn Camera über die Geometrie rausschaut
