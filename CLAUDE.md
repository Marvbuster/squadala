# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**OoT Live Dungeon** — Ein Mod für Ship of Harkinian (PC-Port von Zelda OoT), der per LLM zur Laufzeit neue Dungeons generiert und ins Spiel injiziert.

| Komponente | Pfad | Tech Stack |
|-----------|------|------------|
| **Sidecar** | `sidecar/` | Python 3.12+, FastAPI, Anthropic SDK, Pydantic, NetworkX |
| **SoH-Fork** | `soh-fork/` (ab M4) | C/C++, ImGui, libcurl, nlohmann/json |
| **SoH-Source** | `soh-source/` (gitignored) | Referenz-Clone von HarbourMasters/Shipwright |
| **Tooling** | `tooling/` | Python-Scripts für Template-Extraktion, Validierung |
| **Docs** | `docs/` | Projekt-Specs (oot-live-dungeon-spec.md) |
| **Wiki** | `.wiki/` | Technische Erkenntnisse, Architektur, Dungeon-Katalog |

## Wiki (Dreh- und Angelpunkt)

Das Wiki (`.wiki/`) enthält alle technischen Erkenntnisse und ist die zentrale Wissensquelle:

```
.wiki/
├── INDEX.md                                    ← Einstiegspunkt
├── wiki.config.md                              ← Konfiguration
└── articles/
    ├── architecture/
    │   ├── hybrid-architecture.md              ← SoH + Sidecar Architektur
    │   ├── dungeon-schema.md                   ← Pydantic DungeonSpec
    │   ├── soh-scene-format.md                 ← .o2r Format, Commands, Actors
    │   └── dungeon-catalog.md                  ← 218 Räume, Connectivity
    └── features/
        └── llm-agent.md                        ← Claude Tool-Use Agent
```

**WICHTIG:** Vor jeder Implementierung zuerst `.wiki/INDEX.md` lesen. Neue Erkenntnisse immer ins Wiki schreiben, nicht in docs/.

## Common Commands

### Sidecar (`sidecar/`)
```bash
cd sidecar
uv sync                           # Dependencies installieren
uv run pytest tests/ -v           # Tests laufen lassen
uv run ruff check src/ tests/     # Linting
uv run uvicorn livegen.api:app --reload --port 7777   # Dev-Server starten
```

## Architecture

### Hybrid: In-Game C++ + Python-Sidecar
- **SoH** (C/C++) bekommt einen dünnen HTTP-Client + Scene-Injector
- **Sidecar** (Python/FastAPI auf localhost:7777) macht die LLM-Logik
- Kommunikation über HTTP/JSON auf 127.0.0.1
- Sidecar kann live neugestartet werden während das Spiel läuft

### LLM Agent Flow
1. Spieler gibt Prompt im ImGui-Panel
2. SoH sendet POST /sessions an Sidecar
3. Claude Agent stellt 0-3 Rückfragen (ask_player Tool)
4. Agent submitted DungeonSpec (submit_dungeon Tool)
5. Layout-Solver platziert Räume kollisionsfrei
6. Scene-Compiler erzeugt `.o2r`-Datei
7. SoH lädt `.o2r` zur Laufzeit über mods/-System

### Datenformat
- **LLM Output:** DungeonSpec JSON (Pydantic-validiert)
- **Scene Output:** `.o2r`-Format (SoH Asset-Container)
- Der LLM produziert **niemals** Geometrie — nur den Dungeon-Graphen

## Milestones

| # | Name | Status | Beschreibung |
|---|------|--------|-------------|
| M1 | Sidecar standalone | Fertig | FastAPI + Agent + Schema + Tests (20/20 grün) |
| M2 | Template-Extraktion | In Arbeit | 218 Räume katalogisiert, Connectivity-Graphen dokumentiert |
| M3 | .o2r-Compilation | Ausstehend | Graph → SoH-kompatible Scene-Datei |
| M4 | In-Game UI | Ausstehend | ImGui-Panel im SoH-Fork |
| M5 | Hot-Swap | Ausstehend | Runtime Scene-Injection + Door-Hook |
| M6 | Polish | Ausstehend | Caching, Streaming-UI, Debug-Overlay |

## Code Rules

- **Python:** ruff/mypy strict, max 400 LOC pro Datei
- **C++:** SoH-Style folgen
- **Sprache:** Deutsch für Doku und Release Notes, Englisch für Code
- **Tests sind nicht optional**
- Niemals direkt upstream SoH-Code editieren — Patches in `livegen/` halten

## Verzeichnisse

- `docs/` — Projekt-Specs und Architektur-Docs
- `release_notes/` — Versionierte Release Notes nach Schnack-Format
- `sidecar/` — Python-Sidecar (FastAPI + LLM Agent)
- `tooling/` — Hilfs-Scripts
- `roms/` — ROM-Dateien (gitignored!)
