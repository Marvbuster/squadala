# OoT Live Dungeon SoH-Fork v0.8.0 Build 1

**Datum:** 11.05.2026 | **Status:** Abgeschlossen | **Milestone:** Tooling + Portal-Flow

## Zusammenfassung

Zwei große Erweiterungen am Fork: (1) Mesh Lab + Custom Dungeon Modi inkl. eigener Scene-Namespaces, plus (2) ein vollständiger Portal-Flow um per vanilla Door_Warp1 in den Custom Dungeon zu warpen — Boss-Clear-Cutscene, OnePointCutscene-Kameraschwenk, NA_BGM_BOSS_CLEAR, White-Fade, alles wie nach einem echten Boss.

## Features & Änderungen

### Mesh Lab Dropdown (`LiveGenPanel.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Neues Combo-Dropdown "Mesh Lab" neben dem orangen "Debug Room"-Button. Vier Einträge: Empty Box / L-Shape / Maze / Maze Complex |
| FEATURE | `LiveGenPanel::PendingLoad` Enum (NONE / DUNGEON / MESH_LAB) + deferred-load Pattern via `UpdateElement`. Klick auf "Load Lab" queued, Eviction + Warp passieren im nächsten Frame zwischen Render-Phasen (safe) |
| FEATURE | `MESH_LAB_EXPERIMENTS[]` Tabelle mit `{label, o2rPath}` — neue Experimente einfach hinzufügbar |

### Debug Mode Enum (`LiveGenHotReload.{h,cpp}`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `enum class DebugMode { OFF, DUNGEON, MESH_LAB, CUSTOM_DUNGEON }`. Ersetzt das bisherige `bool sDebugRoomActive` |
| FEATURE | `GetDebugScenePath()` returns Namespace-Pfad pro Modus — wird von `z_play_otr.cpp` für den Scene-Load-Redirect gelesen. Drei Namespaces parallel: `scenes/squadala/`, `scenes/squadala_mesh_lab/`, `scenes/squadala_custom/` |
| FEATURE | `HotReloadMeshLab(o2rPath)`, `HotReloadCustomDungeon(o2rPath)` — analog zu `HotReloadDungeon`. AddArchive ohne Eviction (Eviction race'd mit dem Graphics-Thread, hat reproducible gecrasht) |

### Door_Warp1 Portal Flow

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `SpawnEntryPortal()` — spawnt Door_Warp1 in der aktuellen Scene mit `WARP_DUNGEON_CHILD` params. OnePointCutscene swingt Kamera, Boss-Clear-BGM startet. Vanilla actor übernimmt: Player-in-Range → Float-Cutscene → Pitch-Rise → White-Fade |
| FEATURE | `FindClearPortalSpot()` — Raycast-Suche in 12 Richtungen (0°, ±30°, ±60°, ±90°, ±120°, ±150°, 180°). Pro Kandidat: `BgCheck_EntityLineTest1` von Link's Brusthöhe (kein Walltreffer) + `BgCheck_EntityRaycastFloor1` (echter Boden unten). Erster freier Spot wird's, kein "Portal in der Wand" mehr |
| FEATURE | `Object_Spawn(OBJECT_WARP1)` vor `Actor_Spawn` — Door_Warp1's drawFunc dereferenced `gWarpCrystalDL` aus OBJECT_WARP1's Segment. Ohne preload ist die Segment-Adresse NULL, Graphics-Thread crash beim ersten Draw |
| FEATURE | Magic-State-Bits gesetzt damit Vanilla-Cutscene-Code auch außerhalb der Boss-Scenes feuert: `gSaveContext.nextCutsceneIndex = 0xFFEF` + `play->nextEntranceIndex = 0`. Für non-Boss-Scenes überschreibt die hardcoded sceneNum-Chain im Actor `nextEntranceIndex` nicht — unser Preset bleibt aktiv |
| FEATURE | `Audio_QueueSeqCmd(NA_BGM_BOSS_CLEAR)` während des Cutscene-Setups → der orchestrale Pad-Sound nach Boss-Kämpfen läuft im Hintergrund |
| FEATURE | `SetDebugMode(CUSTOM_DUNGEON)` BEVOR der Cutscene-Trigger feuert → `GetDebugScenePath()` returnt scenes/squadala_custom/... wenn die Scene-Init im neuen Scene-Load aufgerufen wird |
| FEATURE | `PreDungeonState` (entrance + Pos + RotY + roomNum) wird beim Entry-Portal-Spawn gespeichert. Aktuell nicht verbraucht — wartet auf Exit-Warp-Flow |

### Hooks (`RegisterPortalHooks`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `GameInteractor::OnPlayerUpdate` — Per-Frame-Hook. Aktuell no-op weil Vanilla-Actor selbst Proximity managed. Stub für späteren Exit-Warp-Flow |
| FEATURE | `GameInteractor::OnSceneInit` — Reset `sActiveWarp = nullptr` + `sExitPortalSpawnedThisScene = false` beim Scene-Change |
| FEATURE | `GameInteractor::OnTransitionEnd` — Stub für post-warp Position-Restore (wartet auf Exit-Flow) |

### Scene-Redirect (`z_play_otr.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Scene-Load-Redirect liest jetzt `LiveGen_GetDebugScenePath()` statt hardcoded `"scenes/squadala/dungeon_scene"`. Funktioniert für alle drei Modi (DUNGEON, MESH_LAB, CUSTOM_DUNGEON) |

### LiveGen Bridge (`LiveGenBridge.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `LiveGen_ProcessEntrance` setzt `DebugMode::CUSTOM_DUNGEON` wenn das EntranceManager-Portal eine Entrance redirected. Vor v0.8 war's `DUNGEON` — jetzt zeigt die "vanilla door → portal" Methode in den Custom-Dungeon-Slot, nicht ins 3-Raum-Debug |

### Decoration-Gate (`LiveGenDecoration.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FIX | Decoration-Rendering (Pizza/Cupcake/Mouse) gated jetzt auf `GetDebugMode() == DUNGEON` statt `IsDebugRoomActive()`. Vorher wurden Decorations auch in MESH_LAB + CUSTOM_DUNGEON gerendert — Pizza tauchte beim "Enter Dungeon"-Click im Lab auf |
| FIX | `SetDebugMode(CUSTOM_DUNGEON)` deferred bis ProcessEntrance feuert (LiveGenBridge) — wenn vor dem Button-Click schon im Lab, kein vorzeitiges Mode-Flip mehr |

### Hot-Reload Chest-Flag-Reset

| Typ | Beschreibung |
|-----|-------------|
| FIX | `HotReloadMeshLab` clearted die Treasure-Flags 10-13 für Scene 0 sowohl in `gSaveContext.sceneFlags[].chest` als auch in `play->actorCtx.flags.chest`. Vorher: Chest geöffnet → Hot-Reload → Chest steht als "schon offen" da, kein Key zu holen, Locked Door bleibt locked. Jetzt: jeder Hot-Reload spawnt frische Chests |

## Bekannte Limitationen

- **Exit-Warp** aus dem Custom Dungeon ist deaktiviert. `PreDungeonState` wird gespeichert aber nicht verwendet. Aktuell nur via Panel-Buttons rauskommen.
- **Dungeon-Title-Card** ("In den Custom Dungeon …") nicht implementiert. Vanilla-Title-Card-System wartet im BACKLOG.
- **Portal-Raycast** ist fixed-distance (200 Units). Bei sehr kleinen Räumen findet's evtl. keinen Spot in alle 12 Richtungen → Fallback auf Link's eigene Position (Portal spawnt direkt bei ihm, OnePointCam swingt auf Link).

## Wirkung auf bekannte v0.7-Limitations

- ObjectList-Union beim Multi-Room-Build (BACKLOG): unverändert
- Custom-Chest 7-bit Limit: unverändert
- Spitze-Plane-Edges in Walls: jetzt gelöst via Thick-Wall-Block-API

## Nächste Schritte

- M8: LLM-generierte Custom-Dungeon-Inhalte in den `scenes/squadala_custom/`-Slot
- Title-Card (Zelda dungeon-signature) beim Custom-Dungeon-Landing
- Exit-Warp: Door_Warp1 im Custom Dungeon, Position-Restore beim OnTransitionEnd-Hook
- 2-Ebenen-Maze (Leiter + Rampe) als nächstes Mesh-Lab-Experiment
