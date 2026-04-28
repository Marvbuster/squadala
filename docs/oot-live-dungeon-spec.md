# OoT Live Dungeon — Projekt-Entwurf für Claude Code

> Ein Mod für Ship of Harkinian, der per LLM-Prompt im laufenden Spiel neue
> Dungeons generiert und sie nahtlos einblendet.

## 1. Vision

Spieler drückt im Spiel `F2`, ein ImGui-Panel erscheint, beschreibt:
> "Ein Eis-Dungeon mit drei Räumen, einem kleinen Schlüssel-Puzzle, einem
> Mini-Boss, und am Ende eine Iron-Knuckle-Arena."

Ein Agent stellt 1–3 Rückfragen ("Bullet-Bag oder Bombentasche als Belohnung?
Lieber Linear oder Hub-and-Spoke?"), generiert dann einen Dungeon-Graphen,
das System puzzelt fertige Raum-Templates so zusammen dass Geometrie und
Logik aufgehen, und die nächste Tür im Spiel führt direkt rein. Kein
Neustart, kein Patch, keine Custom-Map laden.

## 2. Architektur (Hybrid: In-Game C++ + Python-Sidecar)

```
┌────────────────────────┐         ┌──────────────────────────┐
│  Ship of Harkinian     │  HTTP   │  Python Sidecar          │
│  (gefordkter Build)    │ <─────> │  (FastAPI auf 127.0.0.1) │
│                        │  :7777  │                          │
│  ┌──────────────────┐  │         │  ┌────────────────────┐  │
│  │ ImGui Prompt UI  │  │         │  │ LLM Orchestrator   │  │
│  └──────────────────┘  │         │  │ (Claude Agent SDK) │  │
│  ┌──────────────────┐  │         │  └────────────────────┘  │
│  │ Scene Injector   │  │         │  ┌────────────────────┐  │
│  │ (runtime loader) │  │         │  │ Template Library   │  │
│  └──────────────────┘  │         │  │ + Layout Solver    │  │
│  ┌──────────────────┐  │         │  └────────────────────┘  │
│  │ Hot-Swap Trigger │  │         │  ┌────────────────────┐  │
│  │ (Tür-Hook)       │  │         │  │ Logic Validator    │  │
│  └──────────────────┘  │         │  │ (Solvability)      │  │
└────────────────────────┘         │  └────────────────────┘  │
                                   │  ┌────────────────────┐  │
                                   │  │ Scene Compiler     │  │
                                   │  │ (Graph → SoH .o2r) │  │
                                   │  └────────────────────┘  │
                                   └──────────────────────────┘
```

**Warum Hybrid?**
LLM-Logik in Python iteriert sich 50× schneller als in einem rekompilierten
C++-Build. Der Sidecar kann live neu gestartet werden während das Spiel läuft.
SoH bekommt nur einen dünnen Client + Scene-Injector.

## 3. Tech Stack

### In-Game (Fork von shipofharkinian/Ship)
- **Sprache:** C/C++ (so wie SoH selbst)
- **HTTP-Client:** `cpr` oder `libcurl` (ohnehin Dependencies vorhanden)
- **JSON:** `nlohmann/json`
- **UI:** ImGui (bereits in SoH integriert)

### Sidecar
- **Python 3.12+**
- **FastAPI** + Uvicorn für lokale HTTP-API
- **Anthropic SDK** (`anthropic`) für Tool-Use-Loop mit Claude
- **NetworkX** für Layout-Graph + Solvability-Check
- **Pydantic** für Schema-Validierung der LLM-Outputs

### Datenformat
- **Scene Spec:** JSON (siehe §5)
- **Scene Output:** SoH `.o2r`-Format (Custom-Asset-Container den SoH bereits
  zur Laufzeit aus `mods/` lädt – das ist der Schlüssel-Hack)

## 4. Repo-Struktur

```
oot-live-dungeon/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── scene-spec.md          # JSON-Schema für Dungeon-Graphen
│   └── room-templates.md      # Wie man neue Templates hinzufügt
│
├── soh-fork/                  # Submodule oder Git-Subtree von SoH
│   └── (kompletter SoH-Tree, mit Patches in soh/src/livegen/)
│       └── soh/src/livegen/
│           ├── LiveGenPanel.cpp       # ImGui-Panel
│           ├── LiveGenClient.cpp      # HTTP an Sidecar
│           ├── SceneInjector.cpp      # Lädt .o2r zur Laufzeit
│           └── DoorHook.cpp           # Hookt die "next door"-Logik
│
├── sidecar/
│   ├── pyproject.toml
│   ├── src/livegen/
│   │   ├── api.py                     # FastAPI-Endpoints
│   │   ├── agent.py                   # LLM-Orchestrierung
│   │   ├── schema.py                  # Pydantic-Modelle
│   │   ├── templates/
│   │   │   ├── library.py             # Lädt + indiziert Templates
│   │   │   └── catalog/               # JSON-Templates pro Raum
│   │   ├── solver/
│   │   │   ├── layout.py              # Räume in 3D platzieren
│   │   │   └── logic.py               # Lösbarkeit prüfen
│   │   └── compiler/
│   │       └── o2r_writer.py          # Graph → .o2r-Datei
│   └── tests/
│
└── tooling/
    ├── extract_templates.py   # Aus existierenden Dungeons Templates ziehen
    └── validate_scene.py      # CLI-Validator für JSON-Specs
```

## 5. Schema: Was der LLM produziert

Der LLM produziert **niemals** rohe Geometrie oder Koordinaten. Nur diesen
Graphen — der Solver macht den Rest.

```json
{
  "metadata": {
    "name": "Forsaken Ice Tomb",
    "theme": "ice",
    "difficulty": "medium",
    "estimated_minutes": 25
  },
  "rooms": [
    {
      "id": "entrance",
      "template": "small_chamber_2exit",
      "theme_overrides": { "floor": "ice", "walls": "frozen_stone" },
      "actors": [{ "type": "freezard", "count": 2 }],
      "chests": []
    },
    {
      "id": "key_puzzle",
      "template": "block_push_room",
      "actors": [{ "type": "white_wolfos", "count": 1 }],
      "chests": [{ "id": "c1", "contents": "small_key" }]
    }
  ],
  "connections": [
    { "from": "entrance", "to": "key_puzzle", "type": "open_door" },
    { "from": "entrance", "to": "boss_antechamber", "type": "small_key_door" }
  ],
  "logic": {
    "small_keys_required": 1,
    "boss_key_chest": "compass_room.c1",
    "map_chest": "entrance.c1",
    "boss": { "type": "iron_knuckle", "room": "boss_arena" }
  }
}
```

Pydantic erzwingt das Schema. Was nicht ins Schema passt, wird abgelehnt
und der Agent bekommt einen Tool-Error zurück mit Korrektur-Hinweis.

## 6. Der "BOOM live"-Trick

Echtes synchrones Streaming geht nicht – auch das Originalspiel lädt
zwischen Räumen. Wir maskieren das:

1. Spieler beendet den Prompt-Dialog → Sidecar startet Generation (~5–15 s).
2. Spielfigur kann normal weiterlaufen, der nächste verschlossene Eingang
   ist *bisher* irgendeine generische Tür.
3. Sobald der Sidecar fertig ist, wird die `.o2r`-Datei in den `mods/`-Ordner
   geschrieben und der `SceneInjector` registriert sie als neue Scene-ID.
4. Wenn der Spieler die Tür öffnet, läuft die normale Tür-Animation
   (~1.5 s Fade) — in der Zeit lädt SoH die neue Scene aus `.o2r`.
5. Tür auf → neuer Raum da. Fühlt sich seamless an.

Fallback wenn Generation länger dauert: Tür ist "magisch verschlossen"
mit Animation, bis fertig.

## 7. Milestones (jeweils standalone testbar)

### M1 — Sidecar standalone (ohne Spiel)
- FastAPI läuft, ein Endpoint `/generate`.
- LLM-Agent mit Tool-Use, erzeugt valides Schema-JSON.
- 5 hand-geschriebene Raum-Templates im Katalog.
- Layout-Solver platziert Räume kollisionsfrei.
- Logic-Validator prüft Lösbarkeit.
- **Output:** JSON, das nachweislich konsistent ist.
- **Test:** `pytest` + manuelle Prompts via curl.

### M2 — Template-Extraktion
- Tool das aus den 9 Original-OoT-Dungeons (in SoH-Format) Räume rauszieht
  und sie als wiederverwendbare Templates speichert.
- Ziel: 30–50 Templates abdecken (klein/mittel/groß × Theme × Funktion).

### M3 — `.o2r`-Compilation
- Aus Graph + Templates eine echte `.o2r`-Datei erzeugen die SoH frisst.
- Manuell in `mods/` werfen → SoH startet → neuer Raum existiert.
- Hier liegt das größte Reverse-Engineering-Risiko, siehe §8.

### M4 — In-Game UI
- ImGui-Panel im SoH-Fork, sendet Prompts an Sidecar.
- Zeigt Rückfragen + Antworten.
- Schreibt finale `.o2r` nach `mods/`.

### M5 — Hot-Swap
- `SceneInjector` registriert neue Scene-ID zur Laufzeit.
- `DoorHook` redirectet die nächste verfügbare Tür auf die neue Scene.
- Ende-zu-Ende-Demo: Prompt → 15 s warten → Tür auf → drin.

### M6 — Polish
- Caching: identische Prompts nicht neu generieren.
- Streaming-UI: Agent-Antworten erscheinen Token-by-Token im Panel.
- Telemetry-Toggle, Debug-Overlay (zeigt generierten Graphen).

## 8. Risiken & wo es weh tun wird

**`.o2r`-Format-Reverse-Engineering (M3).**
Der heikelste Punkt. Das Format ist nicht offiziell dokumentiert — du musst
es aus dem SoH-Sourcecode herauslesen (`soh/src/resource/`) und aus
existierenden Texture-Packs wie OoT Reloaded analysieren. Plane 2–3 Wochen
nur dafür ein. **Notfall-Plan:** Statt echter Scene-Injection das Spiel
neustarten und den neuen Dungeon nach Reload anbieten — weniger
beeindruckend, aber 10× einfacher.

**LLM-Geometrie-Konsistenz.**
Selbst mit Templates wird das LLM Pläne produzieren die geometrisch nicht
gehen (5 Türen aus einem 4-Türen-Raum, Räume die sich überlappen). Der
Layout-Solver muss das fangen und entweder reparieren oder mit einem
strukturierten Fehler zurück an den Agent schicken (Tool-Error mit Hinweis
"Raum X hat nur 2 Exits, du hast 3 Connections vorgesehen").

**Lösbarkeit.**
Klassisches Constraint-Problem: Boss-Key muss erreichbar sein bevor
Boss-Tür gebraucht wird. NetworkX + Topological-Sort über den
Logic-Graphen. Die OoT-Randomizer-Community hat das längst gelöst — schau
dir [zsr.link](https://zsr.link) und den OoT-Randomizer-Source an, da ist
die Logic-Engine fast direkt portierbar.

**Performance.**
Claude API Latenz: 3–10 s pro Roundtrip. Mit 2–3 Tool-Use-Roundtrips bist
du bei 15–30 s. Acceptable für ein "Magic Dungeon Spawn"-Feature, aber
plan UI dafür ein (Lade-Animation, "der Magier denkt nach…").

**Legal.**
SoH selbst ist kein Hexenkram (MIT-lizenziert), du brauchst aber dein
eigenes legales OoT-ROM zum Generieren des Asset-Containers. Das ist
genau dieselbe Situation wie SoH ohnehin schon hat. Nicht öffentlich
ausliefern mit ROM-Inhalten.

## 9. Erstes Prompt für Claude Code

Wenn du in einem leeren Repo `claude` startest, könntest du das hier
als Initial-Prompt geben:

````markdown
Wir bauen ein Projekt namens "oot-live-dungeon" — ein Mod für Ship of
Harkinian (PC-Port von Zelda OoT), der per LLM zur Laufzeit neue Dungeons
generiert und sie ins Spiel injiziert.

Lies zuerst @docs/architecture.md und @docs/scene-spec.md komplett.

Wir starten bei Milestone M1: dem Python-Sidecar standalone.

Konkrete Aufgabe für diese Session:
1. Setze `sidecar/` als uv-Projekt auf (Python 3.12, pyproject.toml).
2. Implementiere `sidecar/src/livegen/schema.py` mit Pydantic-Modellen
   für Room, Connection, Logic, DungeonSpec — siehe Beispiel in
   docs/scene-spec.md.
3. Implementiere `sidecar/src/livegen/agent.py`:
   - Nutzt das Anthropic SDK (claude-sonnet-4-5 oder neuer).
   - Tool-Use-Loop mit zwei Tools:
     * `ask_player(question, options?)` — Rückfrage stellen
     * `submit_dungeon(spec)` — finalen Spec absenden
   - Max 3 Rückfragen, dann muss er submitten.
4. Schreibe `sidecar/src/livegen/api.py` mit FastAPI:
   - POST /sessions → neue Session, returnt session_id
   - POST /sessions/{id}/message → Spieler-Antwort, returnt nächste
     Frage ODER finalen Spec
5. Tests in `sidecar/tests/` für Schema-Validierung und einen E2E-Test
   mit mock Anthropic Client.

Halte den Code minimal aber typsauber. Keine Layout-Logik in dieser
Session, keine Templates, kein .o2r — nur Agent + Schema + API.

Plane das in einzelne Commits auf. Frag mich vor Pkg-Installs.
````

---

**Empfohlene Reihenfolge in Claude Code:**

1. Erst `docs/`-Markdowns generieren lassen (architecture, scene-spec,
   room-templates). Die werden dein "Ground Truth" für alle späteren
   Sessions — Claude Code wird sie immer wieder lesen.
2. Dann M1 (Sidecar standalone). Komplett ohne Spiel, in 1–2 Sessions
   machbar.
3. M2 (Template-Extraktion) — eigene Session, eigener Kontext.
4. M3 (`.o2r`-Format) — hier mit `claude` mit erweitertem Kontext und
   ggf. mit direktem Studium des SoH-Sourcecodes als Referenz.
5. M4–M6 in eigenen Branches, jeder Milestone ein Merge.

**CLAUDE.md im Repo-Root anlegen** mit:
- Style-Guide (Python: ruff/mypy strict; C++: SoH-Style folgen)
- Niemals direkt in `soh-fork/` upstream-Code editieren — Patches in
  `livegen/` halten, sonst werden Merges aus upstream zur Hölle
- Tests sind nicht optional
