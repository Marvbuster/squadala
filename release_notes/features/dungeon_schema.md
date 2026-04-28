# Dungeon Schema

Pydantic-basiertes Datenmodell für LLM-generierte Dungeons.

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Dateien | `sidecar/src/livegen/schema.py` |
| Validierung | Pydantic v2 mit model_validators |
| Format | JSON |

## Modelle

| Modell | Beschreibung |
|--------|-------------|
| `DungeonSpec` | Top-Level: Metadata + Rooms + Connections + Logic |
| `Room` | Raum mit Template-ID, Actors, Chests |
| `Connection` | Verbindung zwischen Räumen (Tür-Typ) |
| `Logic` | Schlüssel-Anforderungen, Boss-Spec, Chest-Referenzen |
| `Metadata` | Name, Theme, Schwierigkeit, geschätzte Dauer |

## Validierungen

- Alle Connections referenzieren existierende Räume
- Keine doppelten Room-IDs oder Chest-IDs
- Chest-Referenzen in Logic sind gültig (Format: `room_id.chest_id`)
- Anzahl Small-Key-Chests ≥ Anzahl Small-Key-Doors
- Boss-Raum muss existieren

## Themes

forest, fire, water, shadow, spirit, ice, stone, generic

## Tür-Typen

open_door, small_key_door, boss_key_door, puzzle_door, one_way
