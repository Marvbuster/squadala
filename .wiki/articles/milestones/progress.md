---
title: "Milestone Progress"
created: 2026-04-29
updated: 2026-04-29
category: milestones
tags: [progress, milestones, status]
status: current
related:
  - architecture/hybrid-architecture
  - architecture/soh-scene-format
---

# Milestone Progress

## M1 — Sidecar Standalone ✅

**Status:** Fertig | **Tests:** 20/20 grün | **Commit:** ce1b29b

- FastAPI auf localhost:7777
- LLM Agent mit Tool-Use (ask_player, submit_dungeon)
- Multi-Backend: Anthropic Claude + Ollama + LM Studio
- DungeonSpec Pydantic-Schema mit Graph-Validierung
- Key-Konsistenzprüfung, Boss-Raum-Validierung

## M2 — Template-Extraktion ✅

**Status:** Fertig | **Tests:** 9/9 grün | **Commit:** 799836e

- 218 Räume aus 10 OoT-Dungeons katalogisiert
- Connectivity-Graphen für alle Dungeons
- Room-Types: entrance, hub, junction, corridor, dead_end, pre_boss
- Design-Patterns: hub_and_spoke, linear_chain, multi_hub, complex_loop, split_path
- Template Library mit Queries (by_type, by_exits, by_theme, by_dungeon)

## M3 — .o2r Compilation 🔧

**Status:** Grundgerüst | **Tests:** 7/7 grün

- Scene Compiler: kopiert Rooms aus Base-Game .o2r
- TransitionActor-Builder für Türen zwischen Räumen
- Layout Solver: BFS-Platzierung auf 2D-Grid
- Logic Validator: Lösbarkeits-Check mit Key-Simulation
- **Offen:** Exaktes Binärformat für Scene-Header noch nicht 1:1 getestet

## M4 — In-Game UI 🔧

**Status:** Code geschrieben, Build in Arbeit

- LiveGenPanel.cpp: ImGui-Window mit Chat-Interface
- LiveGenClient.cpp: HTTP-Client (libcurl) für Sidecar-Kommunikation
- Registrierung in SoH via AddGuiWindow Pattern
- **Offen:** SoH from Source builden, Panel registrieren

## M5 — Hot-Swap ⬜

**Status:** Geplant

- SceneInjector: .o2r zur Laufzeit in mods/ schreiben
- DoorHook: nächste Tür auf neue Scene umleiten
- Randomizer EntranceOverride-System als Basis
- PR #5105 "Shuffle Dungeon Doors" als Referenz

## M6 — Polish ⬜

**Status:** Geplant

- Caching: identische Prompts nicht neu generieren
- Streaming-UI: Agent-Antworten Token-by-Token
- Debug-Overlay: generierter Graph anzeigen
- Telemetry-Toggle

## Erkenntnisse

- **Kein Konkurrenzprojekt** in der SoH-Community für LLM-Dungeon-Generation
- **Ultimate Trial** (ROM-Hack) macht prozedurale Dungeons, aber template-basiert, nicht LLM
- **OoT Randomizer** Logic-Engine ist fast direkt portierbar für Lösbarkeits-Checks
- **MetaZelda** Java-Library generiert Lock-and-Key Dungeon-Graphen (ähnlich unser Schema)
- Akademische Papers bestätigen: LLMs als Constraint-Extractor + klassische Spatial-Algorithmen = bester Ansatz
