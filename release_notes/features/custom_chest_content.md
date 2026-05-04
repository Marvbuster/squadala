# Custom Chest Content System

Pipeline für Truhen mit eigenen 3D-Modellen, Texten und Cutscenes — **ohne** vanilla SoH/OoT-Items oder Messages zu überschreiben.

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Code | `soh-fork/soh/Enhancements/livegen/LiveGenItemRegistry.cpp` |
| Item-Table-Erweiterung | `soh-fork/soh/Enhancements/item-tables/ItemTableManager.{h,cpp}` |
| Truhe-Param-Helper | `tooling/build_box_room.py::chest_params()` |

## Drei-Layer-Architektur

### 1. GI-Slot

Vanilla OoT/SoH definiert `GI_*` IDs bis `GI_MAX=0x84`. Dazwischen gibt's leere `GET_ITEM_NONE`-Placeholder-Slots — wir benutzen `0x7E`.

```cpp
constexpr uint8_t GI_LIVEGEN_MARIO = 0x7E;  // unbelegt, fits 7-bit chest params
```

### 2. Item-Table-Eintrag

`ItemTableManager::AddItemEntry` benutzt `unordered_map::emplace` — silent fails bei key-collision (vanilla hat schon `GET_ITEM_NONE` auf `0x7E`). Daher neue Methode `SetItemEntry` mit `[]`-Overwrite:

```cpp
GetItemEntry entry = GET_ITEM(
    ITEM_NONE,                  // kein Inventar-Side-Effect
    OBJECT_GI_HEARTS,           // Placeholder (drawFunc overrides)
    GID_HEART_PIECE,            // Placeholder
    TEXT_LIVEGEN_MARIO,         // 0xE000 — eigener TextId
    0x80, CHEST_ANIM_LONG, ITEM_CATEGORY_MAJOR, MOD_NONE, GI_LIVEGEN_MARIO);
entry.drawFunc = LiveGen_DrawMarioItem;
ItemTableManager::Instance->SetItemEntry(MOD_NONE, GI_LIVEGEN_MARIO, entry);
```

### 3. Hooks

| Hook | Zweck |
|------|-------|
| `OnOpenText` (gated by textId) | Custom-Message via `CustomMessage("...DE...", "...EN...", "...FR...").LoadIntoFont()` + `loadFromMessageTable=false` |
| `VB_PLAY_SLOW_CHEST_CS` (gated by chest params) | Forciert Slow-Cutscene auch mit `itemId=ITEM_NONE` |
| `OnActorUpdate(ACTOR_EN_BOX)` | Patched `player->getItemEntry` so `Player_DrawGetItemImpl.drawFunc` greift |

## Warum kein Vanilla-Override

- **Heart Piece bleibt Heart Piece.** `GI_HEART_PIECE=0x3E` Eintrag wird nicht angefasst.
- **Vanilla Truhen unverändert.** Slow-CS-Override greift nur bei `chest->params >> 5 == GI_LIVEGEN_MARIO`.
- **Message-Table sauber.** Kein Eintrag in `message_data_static`, der OnOpenText-Hook reagiert nur auf unsere TextId.

## Truhe-Definition (Sidecar)

```python
# build_box_room.py
{"name": "chest", "x": 0, "y": -100, "z": 0, "rot_y": 0x8000,
 "params": chest_params(item_id=GI_LIVEGEN_MARIO, treasure_flag=1)},
```

`chest_params()` baut die 16-bit En_Box-Params semantisch:
- bits 0-4: treasure_flag
- bits 5-11: getItemId (7 bit → `GI_LIVEGEN_MARIO=0x7E` passt)
- bits 12-15: chest_type (`ENBOX_TYPE_BIG_DEFAULT=0` für Heart-Piece-Style große Truhe)

## Player-Entry-Bridge

Vanilla `Actor_OfferGetItemNearby` setzt nur `player->getItemId`, nicht den Entry. `Player_DrawGetItemImpl` liest aber `this->getItemEntry.drawFunc` — ohne Bridge rendert vanilla `GetItem_Draw` mit den Placeholder-IDs (Heart Piece).

Der `OnActorUpdate(ACTOR_EN_BOX)`-Hook spiegelt jede Frame:

```cpp
if (player->getItemId == -GI_LIVEGEN_MARIO || player->getItemId == GI_LIVEGEN_MARIO) {
    GetItemEntry entry = ItemTable_Retrieve(GI_LIVEGEN_MARIO);
    entry.getItemId = player->getItemId;  // mirror sign
    player->getItemEntry = entry;
}
```

`player->getItemId` darf NICHT geflippt werden — positiv triggert Auto-Pickup-Pfad. Stattdessen wird das `entry.getItemId` an die aktuelle Sign angepasst, damit alle Equality-Checks passen.

## Erweiterungspunkte

Neue Custom-Items:
- Eigene GI-IDs aus `0x7F` (1 weiterer Slot innerhalb 7-bit), oder Pipeline für höhere Tabelle
- Gleiche drawFunc-Pattern, eigene `__OTR__`-Pfade
- Eigene TextIds aus `0xE001+`

Neue Custom-Truhen-Cutscenes:
- Andere VB-Flags (`VB_GIVE_ITEM_FROM_CHEST` etc.) nach gleichem params-marker-Pattern
