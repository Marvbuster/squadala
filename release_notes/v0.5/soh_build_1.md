# OoT Live Dungeon SoH-Fork v0.5.0 Build 1

**Datum:** 04.05.2026 | **Status:** Abgeschlossen | **Milestone:** M5++ + Custom Item System

## Zusammenfassung

Custom-Item-Pipeline in SoH eingebaut: ein eigenes GetItem (`GI_LIVEGEN_MARIO=0x7E`) wird per Hook in den vanilla `MOD_NONE`-Table additiv eingehängt, eigene Draw-Funktion rendert das Mario-DL über Links Kopf, eigener Textbox via `OnOpenText`-Hook, Slow-Chest-Cutscene per `VB_PLAY_SLOW_CHEST_CS`-Override. Plus eine zweite Decoration über der Truhe (rotierende Pizza). Wallclock-basierte Smooth-Rotation für 3D-Showcases — frame-rate-unabhängig.

**Nichts vanilla wurde überschrieben.** Mario sitzt auf einem ungenutzten `GET_ITEM_NONE`-Slot zwischen `GI_TEXT_0` und `GI_MAX`, der Textbox auf einem GameInteractor-Hook für `textId=0xE000`, die Cutscene auf einem VB-Override gated by params-marker.

## Features & Änderungen

### LiveGen Item Registry (`LiveGenItemRegistry.cpp` — neu)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Custom GetItem-Eintrag (`GI_LIVEGEN_MARIO=0x7E`) im `MOD_NONE`-Table — additiv via `SetItemEntry` |
| FEATURE | Eigene `LiveGen_DrawMarioItem` als `CustomDrawFunc` — pusht Mario-DL über die GetItem-Matrix von `Player_DrawGetItemImpl` |
| FEATURE | `OnOpenText`-Hook für `TEXT_LIVEGEN_MARIO=0xE000` — DE/EN/FR-Message inline gebaut, kein vanilla `message_data_static`-Eintrag |
| FEATURE | `VB_PLAY_SLOW_CHEST_CS`-Override forciert Slow-Cutscene gated by `params >> 5 == GI_LIVEGEN_MARIO` (kein Side-Effect auf vanilla Truhen) |
| FEATURE | `OnActorUpdate`-Hook für `ACTOR_EN_BOX` — patched `player->getItemEntry` so dass `Player_DrawGetItemImpl` unsere `drawFunc` benutzt (vanilla `Actor_OfferGetItemNearby` setzt nur `getItemId`, nicht den Entry) |
| FEATURE | `Matrix_Scale(0.3f)` in drawFunc — Mario auf Heart-Piece-Größe runterskaliert für GetItem-Display |
| FIX | Entry's `getItemId` wird auf player's aktuelles Vorzeichen mirror't — vermeidet Mismatch-Fallback in `func_8084DFF4`, vermeidet Auto-Pickup-Branch bei `z_player.c:7312` |

### LiveGen Decoration (`LiveGenDecoration.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Wallclock-basierte Y-Rotation (`std::chrono::steady_clock`) — frame-rate-unabhängig, 16 Sek/Umdrehung |
| FEATURE | Pizza-Showcase über der Truhe (Y=80, 180°-Offset damit Oberseite zum Spieler bei t=0) |
| FIX | `Matrix_RotateZYX(0, rotation_y, 0, MTXMODE_APPLY)` statt `Matrix_RotateY(rotation_y, ...)` — vanilla erwartet **Radians (f32)**, nicht s16 binary angles. Mit der falschen Funktion drehte sich Mario ~5000 Umdrehungen pro Frame |
| FIX | `__OTR__`-Pfad-Resolution per `ResourceMgr_LoadGfxByName` direkt — der `gSPDisplayList`-Macro expand greift in C++-Scope vor `GbiWrap.cpp` und überspringt die Resolution |

### Item-Tables (`ItemTableManager.cpp/.h`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Neue `SetItemEntry()`-Methode — überschreibt existing keys via `[]` (vs `AddItemEntry` mit `emplace`, das silent fails bei collision) |

### Hot-Reload (`LiveGenHotReload.cpp`)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Pizza-Resources (`squadala_pizza_DL` + `_Vtx`) zum Preload-Set hinzugefügt |
| FEATURE | Mario-Resources bleiben preloaded für GetItem-Display beim Truhe-Öffnen |

### z_play.c (Hook)

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `LiveGen_DrawSpinningMario(play)` Hook nach `Room_Draw` — zeichnet Pizza-Decoration mit Wallclock-Rotation |

### ResourceManagerHelpers.cpp

| Typ | Beschreibung |
|-----|-------------|
| FIX | Spammy `LoadGfx`-Logging entfernt (war jede Frame im Log) |

## Architektur-Erkenntnisse

### Custom-Item ohne Vanilla-Override

Drei Layer machen das ganz additiv möglich:

1. **GI-ID** — `0x7E` ist ein leerer `GET_ITEM_NONE`-Slot zwischen `GI_TEXT_0` (0x7D) und `GI_MAX` (0x84). Vanilla schreibt nichts Reales in dieses Slot. `SetItemEntry` überschreibt die `GET_ITEM_NONE`-Placeholder-Entry. Heart Piece, Map, Compass etc. bleiben unangetastet.

2. **TextID** — `0xE000` liegt safely jenseits aller vanilla + randomizer textIds (Max ist `~0x9212` bei Carpet-Salesman). `GameInteractor::OnOpenText`-Hook fängt nur diesen einen textId ab und liefert die Custom-Message via `LoadIntoFont()` + `loadFromMessageTable=false`.

3. **Cutscene** — `VB_PLAY_SLOW_CHEST_CS` ist eine Vanilla-Behavior-Flag. Default-Logik ist `itemId != ITEM_NONE && gi >= 0 && Item_CheckObtainability == ITEM_NONE`. Mit `itemId=ITEM_NONE` würde die Slow-CS skipped — wir overrun das Should-Flag aber nur wenn `chest->params >> 5 == GI_LIVEGEN_MARIO`. Vanilla-Truhen sehen nichts davon.

### Player→Entry Bridge via OnActorUpdate

Vanilla `EnBox_WaitOpen` ruft `Actor_OfferGetItemNearby` mit dem negativen GI als nur-Identifier:

```c
Actor_OfferGetItemNearby(actor, play, -(this->dyna.actor.params >> 5 & 0x7F));
```

Das setzt `player->getItemId = -0x7E`, **aber NICHT `player->getItemEntry`**. `Player_DrawGetItemImpl` liest aber `this->getItemEntry.drawFunc` — ohne valid Entry rendert vanilla `GetItem_Draw(drawIdPlusOne - 1)` was unser `OBJECT_GI_HEARTS / GID_HEART_PIECE`-Placeholder als Heart Piece zeichnet.

Lösung: ein `OnActorUpdate(ACTOR_EN_BOX)`-Hook der jede Frame `player->getItemEntry = ItemTable_Retrieve(GI_LIVEGEN_MARIO)` setzt — solange `player->getItemId` matchen tut. Idempotent, keine Race Conditions.

### Sign-Mirroring statt Sign-Flipping

Erst Idee: `player->getItemId = +GI_LIVEGEN_MARIO` flippen. Triggert aber **Auto-Pickup-Pfad** in `z_player.c:7312` (`if (getItemId > 0)` → freestanding-item-walked-over). Truhe wurde nicht geöffnet, stattdessen jede Frame `Item_Give(0xFF)` Spam.

Sauberer Fix: `entry.getItemId = player->getItemId` mirror't (negativ pre-A-press, positiv post-Open via vanilla `func_8083A434:5651` flip). Equality-Check passt immer, kein Lookup-Fallback, kein Auto-Pickup.

### Wallclock-Rotation > gameplayFrames

`gameplayFrames` tickt in SoH viel zu schnell (vermutlich render-rate-interpoliert). `std::chrono::steady_clock` gibt frame-rate-unabhängige Real-Time-Rotation. 4 Schritte pro Millisekunde × 65536 / 1000 = ~16 Sekunden pro volle Umdrehung.

## Bekannte Limitationen

- `Item_Give(ITEM_NONE)` läuft am Ende des Get-Item-Flows — vanilla Code-Pfad. ITEM_NONE = 0xFF, `gItemSlots[0xFF]` ist OOB-Read aber in der Praxis stabil. Cleaner wäre ein VB-Hook zum Skippen, kostet aber upstream-Edit. Reservierter Punkt.
- Pizza-Decoration und Mario-Truhen-Item teilen sich derzeit den `LiveGen_DrawSpinningMario`-Hook-Namen (Legacy) — funktional irrelevant, könnte später renamed werden.
