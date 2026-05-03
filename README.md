![Squadala](docs/shiptitle.squadala.png)

# Squadala — AI Dungeon Generator for Ship of Harkinian

> *"Squadala! We're off!"* — Generate Zelda dungeons with a local LLM, directly from within the game.

Describe a dungeon, the AI designs it, walk through any door to enter. Custom 3D geometry rendered in real-time via Hot-Reload.

## How It Works

```mermaid
graph LR
    A[Player Prompt] -->|HTTP| B(Python Sidecar)
    B -->|Gemma 4 / Claude| C{LLM}
    C -->|DungeonSpec JSON| B
    B -->|Compile .o2r| D[Scene Builder]
    D -->|Hot-Reload| E[Ship of Harkinian]
    E -->|Portal System| F[Enter Dungeon!]

    style A fill:#4a9eff,color:#fff
    style C fill:#ff6b6b,color:#fff
    style F fill:#51cf66,color:#fff
```

## Architecture

```mermaid
graph TB
    subgraph SoH["Ship of Harkinian (C++ Fork)"]
        Panel[Squadala Panel<br/>ImGui UI]
        Portal[Entrance Override<br/>Portal System]
        HotReload[Hot-Reload<br/>Runtime .o2r]
    end

    subgraph Sidecar["Python Sidecar (FastAPI :7777)"]
        Agent[LLM Agent<br/>Structured JSON]
        Compiler[Scene Compiler<br/>DungeonSpec to .o2r]
        Store[Dungeon Store<br/>~/.squadala/]
    end

    subgraph LLM["Local LLM"]
        Gemma[Gemma 4 26B<br/>via MLX]
    end

    Panel <-->|HTTP| Agent
    Agent <-->|Tool-Use| Gemma
    Agent --> Store
    Store --> Compiler
    Compiler --> HotReload
    Panel --> Portal

    style SoH fill:#1a1a2e,color:#fff
    style Sidecar fill:#16213e,color:#fff
    style LLM fill:#0f3460,color:#fff
```

## Repository Structure

```
squadala/
├── sidecar/         Python FastAPI + LLM Agent (Anthropic / MLX / Ollama)
├── tooling/         Scene & DL compilers (build_box_room.py + 64 Pytest tests)
├── docs/            Project specs
├── .wiki/           Technical deep-dives (DL format, OTR resolution, etc.)
├── release_notes/   Versioned release notes (v0.1 → v0.4)
└── soh-source/      Git submodule → Marvbuster/Shipwright-Squadala (C++ fork)
```

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| LLM Dungeon Generation | Done | Structured JSON output, 100% success rate with Gemma 4 |
| In-Game UI | Done | Squadala panel with Generate + My Dungeons tabs |
| Portal System | Done | Entrance override redirects any door |
| Hot-Reload | Done | No restart needed |
| Dungeon Persistence | Done | Saved in `~/.squadala/dungeons/` |
| Dungeon Notification | Done | Shows dungeon name on entry |
| Actor Injection | Done | Custom enemies and chests |
| **Custom 3D Geometry** | **Done (v0.4)** | Custom Display Lists render in SoH! |
| LLM-Generated Meshes | Planned | MeshLLM / procedural rooms |

## Quick Start

```bash
# 1. Clone with submodule
git clone --recurse-submodules https://github.com/Marvbuster/squadala.git
cd squadala

# 2. Build the fork
cd soh-source
# Follow soh-source/docs/BUILDING.md

# 3. Start the Python sidecar
cd sidecar
uv sync
uv run uvicorn livegen.api:app --port 7777

# 4. Start a local LLM (in another terminal)
mlx_lm.server --model mlx-community/gemma-4-26b-a4b-it-4bit --port 11434

# 5. Launch the game
./soh-source/build-cmake/soh/soh-macos
# ESC → Enhancements → Squadala → describe a dungeon → Enter!
```

## Tech Stack

- **Sidecar:** Python 3.12, FastAPI, Anthropic SDK, Pydantic, NetworkX
- **SoH Fork:** C/C++, ImGui, libcurl, nlohmann/json
- **LLM:** Gemma 4 26B (local via MLX) or Claude Sonnet (Anthropic API)
- **Tooling:** uv, ruff, mypy, pytest

## Documentation

- [Project Overview](docs/oot-live-dungeon-spec.md) — Complete project specification
- [Wiki Index](.wiki/INDEX.md) — Technical articles (architecture, formats, milestones)
- [Custom Geometry Pipeline](.wiki/articles/architecture/custom-geometry-pipeline.md) — How custom 3D rendering works
- [OTR DL Resolution](.wiki/articles/architecture/otr-dl-resolution.md) — How `__OTR__` paths are resolved
- [Release Notes](release_notes/README.md) — Per-version changelogs

## Milestones

| # | Name | Status |
|---|------|--------|
| M1 | Sidecar Standalone | Done |
| M2 | Template Extraction (218 rooms) | Done |
| M3 | .o2r Round-Trip | Done |
| M4 | In-Game UI | Done |
| M5 | Hot-Swap | Done |
| M5+ | **Custom 3D Geometry** | **Done (v0.4)** |
| M6 | Polish | Planned |

## Acknowledgments

This project stands on the shoulders of giants:

- **[Ship of Harkinian](https://github.com/HarbourMasters/Shipwright)** by HarbourMasters — the OoT PC port that makes everything possible
- **The SoH Randomizer Team** — the entrance override system is the foundation of Squadala's portal mechanism
- **[OoT Decompilation](https://github.com/zeldaret/oot)** by zeldaret — actor IDs, object mappings, scene formats
- **[OoT Randomizer](https://github.com/OoTRandomizer/OoT-Randomizer)** — dungeon logic and connectivity data
- **[libultraship](https://github.com/Kenix3/libultraship/)** — the runtime framework powering mod loading and resource management
- **[Fast64](https://github.com/HarbourMasters/fast64)** — Blender tools for OoT scene creation
