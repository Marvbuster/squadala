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
| M1 | Sidecar standalone | Fertig | FastAPI + Structured JSON Agent + Gemma 4 (100% success) |
| M2 | Template-Extraktion | Fertig | 218 Räume, Template Library, 36 Tests |
| M3 | .o2r-Compilation | Fertig (Round-Trip) | Scene+Room+Collision Round-Trip 100% verifiziert |
| M4 | In-Game UI | Fertig | Squadala Panel, Background-Threading, Gemma 4 via MLX |
| M5 | Hot-Swap | Fertig | Custom .o2r per Hot-Reload, Resource-Eviction, Scene-Override-Pipeline komplett |
| M5+ | Custom Geometry | Fertig | Eigene Display Lists rendern! G_VTX_OTR_HASH, OVTX-Vertex-Resources, GbiWrap-Resolution verstanden |
| M5++ | Vollständiger Box-Raum | Fertig | 6 Wände + Boden + Decke, Z-Buffer, Aktoren spawnen, Render-Mode korrekt |
| M5++/Items | Custom Chest Content | Fertig | Mario in der Kiste mit eigener drawFunc + Custom-Text + Slow-CS — additiv, ohne Vanilla-Override |
| M5++/Mesh | GLB-Importer | Fertig | trimesh-basierter Universal-Loader (GLB/OBJ/STL/PLY), PBR-baseColorFactor → Per-Face-Color |
| M6 | Lebender Raum | Fertig | Spec-Bridge `box_room_dungeon` mappt LLM-DungeonSpec auf Custom-Geometry-`.o2r` mit allen 21 ActorTypes; 26 En_Item00-Drops als Showcase im Debug-Raum |
| M7 | Multi-Room | Geplant | Mehrere Räume verbunden via En_Holl, Layout-Solver, eigene Geometrie pro Raum |
| M8 | LLM-Mesh-Generation | Geplant | Sidecar generiert Mesh-Daten aus DungeonSpec, prozedurale Patterns, optional ShapeLLM |
| M9 | Texturen | Geplant | XETO-Textures, G_SETTIMG_OTR_HASH, Tile-Setup, Theme-Atlas |
| M10 | Polish | Geplant | Streaming-UI, Debug-Overlay, Sound, Custom Lighting, Caching, Save/Load |
| v1.0 | Custom Dungeon Showcase | Vision | 5-7 Räume + Mini-Boss + Boss + Item-Logik, durchspielbar |

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
