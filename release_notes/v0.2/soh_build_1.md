# OoT Live Dungeon SoH-Fork v0.2.0 Build 1

**Datum:** 29.04.2026 | **Status:** Abgeschlossen | **Milestone:** M4 (Vorbereitung)

## Zusammenfassung

SoH (Shipwright-Squadala) erfolgreich from Source gebaut auf macOS 26 / Apple Silicon. Build-Fixes für Apple Clang 17+. LiveGen UI-Code geschrieben.

## Features & Änderungen

| Typ | Beschreibung |
|-----|-------------|
| FIX | FMT_CONSTEVAL=constexpr für Apple Clang 17+ Kompatibilität |
| FIX | tinyxml2 v7→v11 Update in ZAPDTR Submodule |
| FIX | Include-Pfade für Homebrew Dependencies (libzip, tinyxml2) |
| FEATURE | LiveGenPanel.cpp — ImGui Chat-Interface für Dungeon-Prompt |
| FEATURE | LiveGenClient.cpp — HTTP-Client (libcurl) für Sidecar-Kommunikation |
| FEATURE | LiveGenClient.h — API-Definitionen (Session, GenerationResult) |

## Abhängigkeiten

- Fork: github.com/Marvbuster/Shipwright-Squadala
- Branch: livegen/main
- Base: SoH v9.2.3 (develop)
