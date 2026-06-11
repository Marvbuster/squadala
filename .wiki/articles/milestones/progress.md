---
title: "Milestone Progress"
created: 2026-04-29
updated: 2026-06-11
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

> **Hinweis (Stand Mai 2026):** Der hier dokumentierte M1-Tool-Use-Ansatz (`ask_player`, `submit_dungeon`) wurde mittlerweile durch **strukturierten JSON-Output** abgelöst — `livegen/agent.py` arbeitet inzwischen ohne Tools (`tools=[]`), der Agent liefert das Dungeon-JSON direkt im Response-Text (Default-Backend: Anthropic `claude-sonnet-4-5-20250514`, lokal via OpenAI-kompatiblem Backend). Details siehe [features/llm-agent](../features/llm-agent.md). Der Milestone-Eintrag bleibt historisch korrekt für den damaligen Stand.

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

## M5 — Hot-Swap ✅

**Status:** Fertig | **Version:** v0.3 + v0.4

- ✅ ArchiveManager::AddArchive zur Laufzeit
- ✅ ResourceManager::UnloadResource + LoadResourceProcess Preload
- ✅ Deferred Eviction in UpdateElement (vermeidet Use-After-Free)
- ✅ Scene-Override-Pipeline (Custom Scene + Room + Collision)
- ✅ Collision-Rebind in Scene_CommandCollisionHeader
- ✅ Transition-Actor-Block für Debug-Room-Modus
- ✅ Direct-Warp via TRANS_TRIGGER_START

## M5+ — Custom Geometry ✅ (Bonus)

**Status:** Fertig | **Version:** v0.4 (03.05.2026)

- ✅ CRC64-Hash-Implementation (ECMA-182, kein Final Inversion)
- ✅ OVTX Vertex Resource (Type 0x4F565458)
- ✅ TLDO Display List Resource (Type 0x4F444C54)
- ✅ G_VTX_OTR_HASH (0x32, expanded 16B) referenziert Vertices per Hash
- ✅ GbiWrap.cpp __OTR__ DL Resolution verstanden und dokumentiert
- ✅ Render-State korrekt encoded (G_MDSFT_RENDERMODE = 3, NICHT 0!)
- ✅ Vier farbige Triangles rendern in Custom-Raum
- ✅ 64 Tests grün
- 🔜 Vollständiger Box-Raum (6 Wände + Boden + Decke)
- 🔜 LLM-spezifizierte Meshes
- 🔜 Texturen statt Vertex-Farben

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
