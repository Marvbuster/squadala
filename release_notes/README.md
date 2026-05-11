# OoT Live Dungeon — Release Notes

**Projekt:** OoT Live Dungeon — LLM-generierte Dungeons für Ship of Harkinian
**Plattform:** Python 3.12+ (Sidecar) / C++ (SoH-Fork)
**Autor:** Robin Wichmann

---

## Versionsübersicht

| Version | Sidecar | SoH-Fork | Status |
|---------|---------|----------|--------|
| v0.8 | Build 1 | Build 1 | Abgeschlossen — Mesh Lab Sandbox + Door_Warp1 Boss-Clear-Portal in den Custom Dungeon |
| v0.7 | Build 1 | Build 1 | Abgeschlossen — M7 Multi-Room (3 Räume, En_Holl + En_Door, room-aware Deko, Squadala-Namespace) |
| v0.6 | Build 1 | Build 1 | Abgeschlossen — M6 Lebender Raum (Spec-Bridge) + Items-Showcase im längeren Debug-Raum |
| v0.5 | Build 1 | Build 1 | Abgeschlossen — Vollständiger Box-Raum + Custom Chest Content + GLB-Importer |
| v0.4 | Build 1 | Build 1 | Abgeschlossen — Custom 3D Geometry rendert! |
| v0.3 | Build 1 | Build 1 | Abgeschlossen |
| v0.2 | Build 1 | Build 1 | Abgeschlossen |
| v0.1 | Build 1 | — | Abgeschlossen |

## Verzeichnisstruktur

```
release_notes/
├── README.md
├── features/
│   ├── dungeon_schema.md
│   ├── llm_agent.md
│   └── api_endpoints.md
└── v0.1/
    ├── README.md
    └── sidecar_build_1.md
```

## Präfixe

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Neues Feature / neue Funktionalität |
| ENHANCEMENT | Verbesserung bestehender Funktionen |
| FIX | Bugfix |
| CRITICAL | Kritischer Fix |
| PERF | Performance-Verbesserung |
| REFACTOR | Code-Refactoring ohne Feature-Änderung |
