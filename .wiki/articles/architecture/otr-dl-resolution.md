---
title: "OTR Display List Resolution — GbiWrap"
created: 2026-04-30
updated: 2026-04-30
category: architecture
tags: [o2r, display-list, gbi, rendering, WICHTIG]
status: current
related:
  - architecture/o2r-reverse-engineering
  - architecture/deku-tree-binary-analysis
---

# OTR Display List Resolution

> **WICHTIG:** So funktioniert das DL-Rendering in SoH. Kritisch für Custom Geometry.

## Der Flow

### 1. SetMesh Factory (Resource-Load-Time)

`soh/soh/resource/importer/scenecommand/SetMeshFactory.cpp`:

```cpp
meshOpa = "__OTR__" + meshOpa;
setMesh->opaPaths.push_back(meshOpa);
dlist.opa = (Gfx*)setMesh->opaPaths.back().c_str();  // STRING POINTER!
```

Der `opa` Pointer ist KEIN Gfx* — er zeigt auf einen `__OTR__`-String!

### 2. Room Rendering (Runtime)

`soh/src/code/z_room.c` (func_80095AB4 für Type 0):

```c
for (i = 0; i < polygon0->num; i++) {
    if ((flags & 1) && (polygonDlist->opa != NULL)) {
        gSPDisplayList(POLY_OPA_DISP++, polygonDlist->opa);  // String-Pointer!
    }
}
```

### 3. GbiWrap Interceptor (DER SCHLÜSSEL!)

`soh/soh/GbiWrap.cpp`:

```cpp
extern "C" void gSPDisplayList(Gfx* pkt, Gfx* dl) {
    char* imgData = (char*)dl;
    if (ResourceMgr_OTRSigCheck(imgData) == 1) {
        dl = ResourceMgr_LoadGfxByName(imgData);  // ← RESOLUTION!
    }
    __gSPDisplayList(pkt, dl);
}
```

**SoH hat einen C-Wrapper um `gSPDisplayList`!** Dieser:
1. Prüft ob der Pointer ein `__OTR__`-String ist
2. Wenn ja: lädt die DL-Resource via `ResourceMgr_LoadGfxByName()`
3. Ersetzt den String-Pointer mit dem echten `Gfx*` (`&Instructions[0]`)
4. Ruft dann das echte `__gSPDisplayList(pkt, actualGfx)` auf

### 4. Resource Loading

`soh/soh/ResourceManagerHelpers.cpp`:

```cpp
Gfx* ResourceMgr_LoadGfxByName(const char* path) {
    ResourceMgr_UnloadOriginalWhenAltExists(path);
    auto res = std::static_pointer_cast<Fast::DisplayList>(
        ResourceMgr_GetResourceByNameHandlingMQ(path));
    return (Gfx*)&res->Instructions[0];
}
```

Lädt die DL-Resource per Pfad, gibt `Instructions.data()` zurück.

## Wichtig für Custom Geometry

1. **DL-Name kann frei gewählt werden** — GbiWrap resolved jeden `__OTR__`-Pfad
2. **Der ResourceManager cacht aggressiv** — einmal geladene DLs bleiben im Cache
3. **Cache-Eviction ist gefährlich** — NICHT während des Renderings (Use-After-Free!)
4. **Eviction muss zwischen Frames passieren** — z.B. in `UpdateElement()` VOR dem Rendering
5. **AddArchive überschreibt `mFileToArchive`** — neueste Archive haben Priorität

## Cache-Eviction Race Condition

```
FALSCH: Button Click → Evict → Warp (gleicher Frame = Crash!)
RICHTIG: Button Click → Flag setzen → Nächster Frame: Evict + Warp
```

Die Eviction entfernt den `shared_ptr` aus dem Cache. Wenn der Interpreter noch
einen rohen `Gfx*` auf die alten Instructions hat → Use-After-Free → Crash.
