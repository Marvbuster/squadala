---
title: "Dungeon Schema"
created: 2026-04-28
updated: 2026-05-16
category: architecture
tags: [schema, pydantic, json, validation, dungeon-spec, llm-output]
status: current
related:
  - architecture/hybrid-architecture
  - features/llm-agent
code_refs:
  - sidecar/src/livegen/schema.py
  - sidecar/src/livegen/agent.py
  - sidecar/tests/test_schema.py
---

# Dungeon Schema

Das zentrale Datenmodell, das der LLM produziert. Validiert durch Pydantic v2.

> **Achtung — zwei Schemas im Spiel:** Das **kanonische Pydantic-Schema** (interne Wahrheit, validiert + von Builder/Solver konsumiert) unterscheidet sich vom **LLM-Output-Schema** (Prompt-Shape, das dem Modell vorgegeben wird). `DungeonAgent._normalize()` in `sidecar/src/livegen/agent.py:144` mapped vom LLM-Format ins Pydantic-Format. Beide werden unten dokumentiert, plus die Mapping-Tabelle.

## Prinzip

Der LLM produziert **niemals** rohe Geometrie oder Koordinaten. Nur einen abstrakten Graphen — der Layout-Solver macht den Rest.

## Pydantic-Schema (intern, `schema.py`)

Das ist die kanonische Form nach Normalisierung — alles, was Builder, Solver und Validator sehen.

```json
{
  "metadata": { "name": "...", "theme": "ice", "difficulty": "medium", "estimated_minutes": 20 },
  "rooms": [
    { "id": "entrance_hall", "template": "small_chamber_2exit",
      "actors": [{"type": "keese", "count": 2}],
      "chests": [{"id": "c0_0", "contents": "small_key"}] }
  ],
  "connections": [
    { "from_room": "entrance_hall", "to_room": "hub", "type": "open_door" }
  ],
  "logic": { "small_keys_required": 1, "boss_key_chest": "room.chest_id",
             "boss": { "type": "...", "room": "..." } }
}
```

Definiert in `sidecar/src/livegen/schema.py:160` (`DungeonSpec`).

## LLM-Output-Schema (extern, Prompt-Shape)

Was der LLM tatsächlich produzieren soll — bewusst simpler, weil kleine Modelle besser mit flachen Namen umgehen. Definiert als `SCHEMA_SHAPE` in `sidecar/src/livegen/agent.py:16`:

```json
{
  "dungeon_name": "string (max 80 chars)",
  "theme": "forest|fire|water|shadow|spirit|ice|stone|generic",
  "difficulty": "easy|medium|hard",
  "rooms": [
    {
      "name": "string (lowercase, underscores)",
      "template": "small_chamber_2exit|corridor_straight|boss_arena|...",
      "enemies": [{"type": "keese|stalfos|...", "count": 1}],
      "chests": ["small_key|boss_key|map|compass|..."]
    }
  ],
  "connections": [
    {"from": "room_name_a", "to": "room_name_b", "door_type": "open_door|small_key_door|..."}
  ],
  "boss": {"room": "room_name", "type": "enemy_type"}
}
```

## Mapping (LLM-Output → Pydantic)

`DungeonAgent._normalize()` in `agent.py:144`:

| LLM-Feld | Pydantic-Feld | Transformation |
|----------|---------------|----------------|
| `dungeon_name` | `metadata.name` | String, auf 80 Zeichen gecappt; Fallback `name` oder `"Generated Dungeon"` |
| `theme` | `metadata.theme` | Direkt, Default `generic` |
| `difficulty` | `metadata.difficulty` | Direkt, Default `medium` |
| `rooms[].name` | `rooms[].id` | Lowercase, Spaces/Bindestriche → Underscores, Sonderzeichen entfernt, mit `room_`-Prefix falls leer/nicht-alphabetisch |
| `rooms[].enemies` | `rooms[].actors` | Filter auf `VALID_ENEMIES`, `count` auf 1–10 begrenzt; Fallback-Feldname `actors` wird ebenfalls akzeptiert |
| `rooms[].chests` (String-Array) | `rooms[].chests` (Object-Array) | Jeder gültige Content wird zu `{id: "c{i}_{j}", contents: ...}` |
| `rooms[].template` | `rooms[].template` | Validiert gegen `VALID_TEMPLATES`, Fallback `small_chamber_2exit` |
| `connections[].from` | `connections[].from_room` | Ref-Resolution via `room_id_map`; Aliasse `from_room`, `room_a`, `source` werden ebenfalls akzeptiert |
| `connections[].to` | `connections[].to_room` | Analog (Aliasse `to_room`, `room_b`, `target`) |
| `connections[].door_type` | `connections[].type` | Validiert gegen `VALID_DOOR_SET` |
| `boss` | `logic.boss` | Direkt übernommen, `boss.room` durch Ref-Resolution gemappt |

**Warum die Asymmetrie?** Das LLM-Schema ist tokeneffizienter (kurze Feldnamen, flache Struktur), und vor allem **tolerant** — kleine Modelle (Gemma 4, Qwen 14B) liefern oft Varianten wie `enemies` statt `actors` oder `from`/`source` statt `from_room`. Der Normalizer akzeptiert mehrere Aliasse, statt die Generation hart abzulehnen. Erst die Pydantic-Schicht prüft Graph-Integrität, Key-Konsistenz und Boss-Validierung — das ist die einzige Form, die irgendwo persistiert oder ans Plugin geschickt wird.

## Modell-Hierarchie

```
DungeonSpec
├── Metadata (name, theme, difficulty, estimated_minutes)
├── Room[] (id, template, theme_overrides, actors, chests)
│   ├── Actor[] (type, count)
│   └── Chest[] (id, contents)
├── Connection[] (from, to, type)
└── Logic (small_keys_required, boss_key_chest, boss)
    └── BossSpec (type, room)
```

## Validierungen (model_validators)

| Check | Fehler wenn... |
|-------|---------------|
| Graph-Integrität | Connection referenziert unbekannten Raum |
| Unique IDs | Doppelte Room-IDs oder Chest-IDs im selben Raum |
| Chest-Referenzen | `logic.boss_key_chest` zeigt auf nicht-existente Room.Chest |
| Key-Konsistenz | Mehr small_key_doors als small_key Chests |
| Boss-Raum | `logic.boss.room` existiert nicht |

## Enums

- **Theme:** forest, fire, water, shadow, spirit, ice, stone, generic
- **DoorType:** open_door, small_key_door, boss_key_door, puzzle_door, one_way
- **ActorType:** 22 OoT-Gegnertypen (keese bis tektite)
- **ChestContent:** small_key, boss_key, map, compass, items, rupees
