# OoT Live Dungeon Sidecar v0.1.0 Build 1

**Datum:** 28.04.2026 | **Status:** In Arbeit | **Milestone:** M1

## Zusammenfassung

Initiales Setup: Python-Sidecar mit Dungeon-Schema, LLM-Agent (Claude Tool-Use) und FastAPI-Endpoints.

## Features & Änderungen

| Typ | Beschreibung | Feature-Datei |
|-----|-------------|---------------|
| FEATURE | uv-Projekt mit Python 3.12, FastAPI, Anthropic SDK, Pydantic, NetworkX | — |
| FEATURE | DungeonSpec Pydantic-Schema mit Graph-Validierung | [dungeon_schema](../features/dungeon_schema.md) |
| FEATURE | Room, Connection, Logic, Metadata Modelle | [dungeon_schema](../features/dungeon_schema.md) |
| FEATURE | Key-Konsistenzprüfung (Schlüssel ≥ verschlossene Türen) | [dungeon_schema](../features/dungeon_schema.md) |
| FEATURE | Claude Agent mit Tool-Use-Loop (ask_player, submit_dungeon) | [llm_agent](../features/llm_agent.md) |
| FEATURE | Max 3 Rückfragen, automatische Schema-Validierung bei Submit | [llm_agent](../features/llm_agent.md) |
| FEATURE | FastAPI: POST /sessions, POST /sessions/{id}/message, GET /health | [api_endpoints](../features/api_endpoints.md) |
| FEATURE | 20 Tests: Schema-Validierung + E2E mit Mock-Client | — |

## Geänderte Dateien

```
sidecar/
├── pyproject.toml
├── src/livegen/
│   ├── schema.py          # Pydantic-Modelle (DungeonSpec, Room, Connection, Logic...)
│   ├── agent.py           # Claude Tool-Use-Loop
│   └── api.py             # FastAPI-Endpoints
└── tests/
    ├── test_schema.py     # 13 Schema-Tests
    └── test_api.py        # 7 API-Tests
```
