---
title: "Hybrid-Architektur (SoH + Sidecar)"
created: 2026-04-28
updated: 2026-04-28
category: architecture
tags: [architecture, sidecar, fastapi, http, soh, hybrid]
status: current
related:
  - architecture/dungeon-schema
  - features/llm-agent
code_refs:
  - sidecar/src/livegen/api.py
  - docs/oot-live-dungeon-spec.md
---

# Hybrid-Architektur (SoH + Python-Sidecar)

Das System besteht aus zwei Prozessen die über HTTP auf localhost kommunizieren.

## Warum Hybrid?

LLM-Logik in Python iteriert sich 50× schneller als in einem rekompilierten C++-Build. Der Sidecar kann live neu gestartet werden während das Spiel läuft. SoH bekommt nur einen dünnen HTTP-Client + Scene-Injector.

## Komponenten

```
┌────────────────────────┐         ┌──────────────────────────┐
│  Ship of Harkinian     │  HTTP   │  Python Sidecar          │
│  (Fork)                │ <─────> │  (FastAPI auf 127.0.0.1) │
│                        │  :7777  │                          │
│  ┌──────────────────┐  │         │  ┌────────────────────┐  │
│  │ ImGui Prompt UI  │  │         │  │ LLM Orchestrator   │  │
│  └──────────────────┘  │         │  │ (`anthropic` Py-SDK)│  │
│  ┌──────────────────┐  │         │  └────────────────────┘  │
│  │ Scene Injector   │  │         │  ┌────────────────────┐  │
│  │ (runtime loader) │  │         │  │ Template Library   │  │
│  └──────────────────┘  │         │  │ + Layout Solver    │  │
│  ┌──────────────────┐  │         │  └────────────────────┘  │
│  │ Hot-Swap Trigger │  │         │  ┌────────────────────┐  │
│  │ (Tür-Hook)       │  │         │  │ Scene Compiler     │  │
│  └──────────────────┘  │         │  │ (Graph → .o2r)     │  │
└────────────────────────┘         │  └────────────────────┘  │
                                   └──────────────────────────┘
```

## Kommunikation

| Richtung | Methode | Zweck |
|----------|---------|-------|
| SoH → Sidecar | POST /sessions | Neue Dungeon-Generation starten |
| SoH → Sidecar | POST /sessions/{id}/message | Spieler-Antwort weiterleiten |
| Sidecar → SoH | Response mit DungeonSpec | Fertiger Dungeon als JSON |
| Sidecar → Disk | .o2r in mods/ schreiben | Scene-Daten für SoH |

## Ablauf (Ende-zu-Ende)

1. F2 drücken → ImGui-Panel öffnet sich
2. Spieler beschreibt Dungeon
3. SoH sendet Prompt an Sidecar
4. Agent stellt Rückfragen / generiert Spec
5. Layout-Solver platziert Räume
6. Scene-Compiler schreibt `.o2r` nach `mods/`
7. SceneInjector registriert neue Scene-ID
8. Nächste Tür → Fade → neuer Dungeon da
