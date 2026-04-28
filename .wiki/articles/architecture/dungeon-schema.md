---
title: "Dungeon Schema"
created: 2026-04-28
updated: 2026-04-28
category: architecture
tags: [schema, pydantic, json, validation, dungeon-spec]
status: current
related:
  - architecture/hybrid-architecture
  - features/llm-agent
code_refs:
  - sidecar/src/livegen/schema.py
  - sidecar/tests/test_schema.py
---

# Dungeon Schema

Das zentrale Datenmodell das der LLM produziert. Validiert durch Pydantic v2.

## Prinzip

Der LLM produziert **niemals** rohe Geometrie oder Koordinaten. Nur einen abstrakten Graphen — der Layout-Solver macht den Rest.

## Top-Level: DungeonSpec

```json
{
  "metadata": { "name": "...", "theme": "ice", "difficulty": "medium" },
  "rooms": [...],
  "connections": [...],
  "logic": { "small_keys_required": 1, "boss": {...} }
}
```

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
