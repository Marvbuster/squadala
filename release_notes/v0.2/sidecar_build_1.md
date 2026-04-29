# OoT Live Dungeon Sidecar v0.2.0 Build 1

**Datum:** 29.04.2026 | **Status:** Abgeschlossen | **Milestone:** M2+M3

## Zusammenfassung

Template Library mit 218 Dungeon-Räumen, Layout Solver, Logic Validator und Scene Compiler Grundgerüst.

## Features & Änderungen

| Typ | Beschreibung | Feature-Datei |
|-----|-------------|---------------|
| FEATURE | Template Library: 96 Raum-Templates aus 6 Dungeons mit Connectivity | [dungeon_schema](../features/dungeon_schema.md) |
| FEATURE | Room-Katalog (rooms.json): Exits, Typen, Themes, Design-Patterns | [dungeon_schema](../features/dungeon_schema.md) |
| FEATURE | Layout Solver: BFS-Platzierung auf 2D-Grid, kollisionsfrei | — |
| FEATURE | Logic Validator: Lösbarkeits-Check mit Key-Simulation | — |
| FEATURE | Scene Compiler (.o2r Writer): kopiert Rooms, baut TransitionActors | — |
| FEATURE | Multi-LLM-Backend: Anthropic + Ollama + LM Studio Support | [llm_agent](../features/llm_agent.md) |
| ENHANCEMENT | 36 Tests gesamt (Schema + API + Templates + Solver) | — |

## Geänderte Dateien

```
sidecar/src/livegen/
├── llm.py                     # Multi-Backend LLM Abstraction
├── templates/
│   ├── library.py             # Template Library mit Queries
│   └── catalog/rooms.json     # 96 Room-Templates
├── solver/
│   ├── layout.py              # BFS Layout Solver
│   └── logic.py               # Lösbarkeits-Validator
└── compiler/
    └── o2r_writer.py          # Scene Compiler
```
