# OoT Live Dungeon SoH-Fork v0.7.0 Build 1

**Datum:** 10.05.2026 | **Status:** Abgeschlossen | **Milestone:** M7

## Zusammenfassung

SoH-seitige Multi-Room-Unterstützung: Debug-Room lädt jetzt aus dem `scenes/squadala/`-Namespace, Safety-Nets im Room/Scene-Loader die `En_Holl`-Transitions blockiert haben sind gefallen, und die Custom-Chest-Item-Registry ist um Sonic + Hydrant erweitert. Decoration-Hook ist room-aware.

## Features & Änderungen

### Scene Override (`z_play_otr.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Wenn `LiveGen_IsDebugRoomActive()`, wird Scene-Pfad auf `scenes/squadala/dungeon_scene` umgeleitet — kein Vanilla-Deku-Tree-Override mehr nötig |
| FIX | v0.5 Safety-Net `play->transiActorCtx.numActors = 0` ist gefallen — blockierte En_Holl/En_Door Spawns |

### Multi-Room-Loader (`z_scene_otr.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FIX | Safety-Net in `OTRfunc_800973FC` gefallen — `Actor_SpawnTransitionActors` darf jetzt feuern (war früher übersprungen, wenn Debug-Room aktiv) |
| FIX | Safety-Net in `OTRfunc_8009728C` gefallen — `roomNum != 0` blockierte den Wechsel auf Room 1/2 |

### LiveGenItemRegistry — drei Custom Chest Items

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `LiveGen_RegisterItem()`-Helper — gemeinsamer Drei-Layer-Pattern (GI-Slot + ItemTable-Entry + drawFunc + Custom-Textbox) |
| FEATURE | `GI_LIVEGEN_SONIC=0x7F` mit `LiveGen_DrawSonicItem` (Scale 0.216) und Custom-DE/EN/FR-Textbox |
| FEATURE | `GI_LIVEGEN_HYDRANT=0x7D` (ersetzt `GI_TEXT_0`-Placeholder-Slot) mit `LiveGen_DrawHydrantItem` (Scale 0.3 + `Matrix_Translate(0,-12,0)` damit das hohe Modell ins GetItem-Window passt) |
| FEATURE | `LiveGen_IsCustomGi()` — zentraler Predicate-Check für die VB-Hooks |

### LiveGenDecoration — room-aware Multi-Decoration

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `RoomDecoration`-Struct mit `x_min/x_max` Welt-Bounds, Pivot-Position, Y-Rotation-Offset, `bool spin` und DL-Pfad |
| FEATURE | Filter über `Link.world.pos.x` — robust gegen `curRoom`-Race während En_Holl-Transitions |
| FEATURE | Pizza (Room 0) + Cupcake (Room 1) mit überlappenden Ranges für door-peek-through |
| FEATURE | Mouse (Room 2) — statische Deko (`spin=false`), Rest-Pose der `mouse.glb` |
| FIX | Akzeptiert `prevRoom.segment != NULL` während Mid-Transition — sonst flackert Decoration für 1 Frame |
| TODO | M8+ Dynamic Deco-Registry (siehe `docs/BACKLOG.md`) — Hard-Codings hier sind bewusster Übergangs-Hack |

### Door Cleanup Fix (`z_actor.c::func_80031B14`)

| Typ | Beschreibung |
|-----|-------------|
| FIX | `ACTORCAT_DOOR` wird im Room-Mismatch-Cleanup ausgespart wenn `LiveGen_IsDebugRoomActive()`. Vanilla OoT kombiniert nie En_Holl + En_Door im selben Bereich, deshalb war der latente Bug nie aufgefallen: `prevRoom` wird vor dem Cleanup auf -1 gesetzt, danach killt der Filter jeden Actor mit Room-Mismatch — was in unserer 3-Raum-Konstellation jeden zweiten Transition-Actor abräumt. Door-Actors handhaben ihren eigenen Lifecycle (En_Holl updated sein eigenes `room`-Feld pro Frame, En_Door per Cutscene), das Cleanup ist für sie nicht nötig. |

### LiveGenHotReload — Squadala-Namespace Preload

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Preload-Liste auf `scenes/squadala/`-Pfade umgestellt: `dungeon_scene`, `collision`, `room_0/1/2`, alle DL/Vtx-Resources für Mario/Sonic/Hydrant/Pizza/Cupcake |

## Wirkung auf bekannte v0.5/v0.6-Limitations

- **Multi-Room** (in v0.5/v0.6 als TODO benannt) ist jetzt erledigt.
- **Cupcake** war bei v0.6 als M7-Vorschau gelistet — jetzt drin.
- **Custom Chest 7-bit Limit**: Mit Mario (0x7E) + Sonic (0x7F) + Hydrant (0x7D) sind die freien Slots in der unteren `GI_TEXT_*`-Range aufgebraucht; weiter dokumentiert in BACKLOG als known limitation.

## Architektur-Erkenntnisse

### Room-aware Decoration: Welt-Position vs. curRoom

Die ursprüngliche Implementierung gated Pizza/Cupcake über `play->roomCtx.curRoom.num == ANCHOR_ROOM`. Während `En_Holl`-Transitions ist `curRoom` aber bereits auf den Ziel-Raum geflippt, *bevor* Link physisch durchgegangen ist — Resultat: Pizza-Pop-In im Nachbar-Raum für 1 Frame, Cupcake-Pop-Out beim Rückweg. Link's `world.pos.x` ist monoton mit der physischen Bewegung — direkter Filter ist jitter-frei. Das ist trotzdem nur ein Workaround für M7; sauber ist Decoration-as-Actor mit Vanilla-Room-Cull-Semantik (M8+).

### Safety-Nets fallen lassen war richtig

Die in v0.5 eingebauten Defensive-Checks (`numActors=0` Reset, `Actor_SpawnTransitionActors` skip, `roomNum != 0` block) waren Krücken für den damaligen Single-Room-Fall. Sobald die Scene den TransitionActor-Header korrekt trägt und die Geometrie/ObjectList auf alle Räume vorbereitet sind, sind sie unnötig — und blockieren das Multi-Room-Verhalten aktiv. Aufräumen statt feature-flagging.

## Bekannte Limitationen

- En_Door (visible Wood Door) hat keine DynaPoly-Collision — Static Walls drumrum müssen den Durchgang sperren bis die En_Door-Cutscene Link warpt. Im Debug-Layout ist die Tür entsprechend in eine solide Wand (kein Door-Cutout in der Collision) gesetzt.
- Custom-Chest-Item-Limit (7-bit chest_params) → siehe BACKLOG.

## Nächste Schritte

- M8 / Dynamic Deco-Registry (Decoration-as-Actor, siehe BACKLOG)
- M9 — Texturen (XETO-Textures, G_SETTIMG_OTR_HASH, Theme-Atlas)
