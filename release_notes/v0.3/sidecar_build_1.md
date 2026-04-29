# OoT Live Dungeon Sidecar v0.3.0 Build 1

**Datum:** 29.04.2026 | **Status:** Abgeschlossen | **Milestone:** M3+M4

## Zusammenfassung

Structured JSON Agent (100% Success Rate mit Gemma 4), O2R Round-Trip Test bestanden, Squadala In-Game UI funktional.

## Features & Änderungen

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Structured JSON Agent — Schema im Prompt statt Tool-Use |
| FEATURE | Normalizer für Gemma-Quirks (IDs, Feldnamen, Keys, Truncation) |
| FEATURE | Auto-Fix: Key-Chests für locked doors, Boss-Keys |
| FEATURE | DungeonBuilder API (deterministisch, fehlersicher) |
| FIX | exclude_none in API Responses (keine null-Werte mehr) |
| FIX | .env Loading via python-dotenv |
| FIX | 16k max_tokens für Gemma 4 Reasoning-Headroom |
| FEATURE | O2R Round-Trip: Scene + Room + Collision 100% Byte-identisch |
| FEATURE | Collision-Export als .obj für Blender |
| FEATURE | Test-Scene-Builder (Phase 4 Vorbereitung) |
