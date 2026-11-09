# SoH Squadala (soh)
_Audit Wiki vs Code · 11 Artikel · 17 Funde · Severity: 0c/4h/9m/4l_

## Zusammenfassung
Das Wiki ist auf dem Stand v0.4 (Anfang Mai 2026) stehen geblieben, der Code ist bei v0.8: Milestone-Artikel, Checklisten und "Nächste Schritte" beschreiben Box-Raum, Multi-Room, Portal und Hot-Reload als offen, obwohl sie laut Release Notes und Code fertig sind. Die komplette SoH-Fork-Seite (`soh-source/soh/soh/Enhancements/livegen/`, 1839 LOC) und mehrere Sidecar-Subsysteme (DungeonStore, Spec-Bridge, GLB-Importer, lokales LLM-Backend) sind gar nicht dokumentiert. Dazu kommen harte Zahlenwidersprüche (Katalog: 10 Dungeons/202 Räume im Wiki, 6 Dungeons/103 Räume im Code; 218 vs 219 Räume), ein nicht existierender Default-Model-String im Code und 27 Commits mit Claude-Attribution gegen die Hausregel. Die Binärformat-Artikel (Deku Tree, GbiWrap, Render-Mode) stimmen dagegen weiterhin mit dem Code überein.

## Funde

### [HIGH] Milestone-Progress steht bei v0.4, Code bei v0.8  — stale
- **Artikel/Datei:** soh/milestones/progress
- **Problem:** Artikel (updated 2026-06-11) sagt M3 "Grundgerüst", M4 "Code geschrieben, Build in Arbeit · Offen: SoH from Source builden, Panel registrieren", M6 "Polish ⬜ Geplant". Tatsächlich sind M3–M7 fertig, M6 heißt im Projekt "Lebender Raum", und v0.5–v0.8 (Box-Raum, Custom Chest Content, GLB-Importer, Spec-Bridge, Multi-Room, Mesh Lab, Door_Warp1-Portal) fehlen komplett. INDEX.md bewirbt den Artikel als "M1-M6 Status".
- **Beleg:** Wiki: "## M4 — In-Game UI 🔧 … **Offen:** SoH from Source builden, Panel registrieren" vs `soh-source/soh/soh/SohGui/SohGui.cpp:191` `mLiveGenWindow = std::make_shared<LiveGen::LiveGenPanel>(CVAR_WINDOW("LiveGen"), "Squadala", …)`; Wiki: "## M6 — Polish ⬜" vs `CLAUDE.md` Milestone-Tabelle "M6 | Lebender Raum | Fertig", "M7 | Multi-Room | Fertig", `release_notes/README.md` "v0.8 … Abgeschlossen".

### [HIGH] Dungeon-Katalog: Wiki 10 Dungeons/202 Räume, Code 6 Dungeons/103 Räume  — contradiction
- **Artikel/Datei:** soh/architecture/dungeon-catalog, .wiki/INDEX.md, soh/milestones/progress
- **Problem:** Der Katalog-Artikel listet 10 Dungeons mit 202 Räumen (+17 Boss), INDEX.md sagt "219 Räume (202 Haupt + 17 Boss)", progress/CLAUDE.md sagen "218 Räume". Die tatsächliche Template-Library enthält nur 6 Dungeons (Deku, Dodongo, Jabu, Forest, Water, Ice) mit 103 Räumen; Fire, Shadow, Spirit und Ganon's Castle sind im Code nicht vorhanden. Drei verschiedene Zahlen im Wiki, keine passt zum Code.
- **Beleg:** `sidecar/src/livegen/templates/catalog/rooms.json` → `dungeons` = {deku_tree:12, dodongo_cavern:17, jabu_jabu:16, forest_temple:23, water_temple:23, ice_cavern:12} = 103; `sidecar/tests/test_templates.py:10` prüft nur `len(lib.templates) > 50`. Wiki dungeon-catalog: "| **Gesamt** | | **202** |"; INDEX.md: "219 Räume (202 Haupt + 17 Boss)"; progress M2: "218 Räume aus 10 OoT-Dungeons katalogisiert".

### [HIGH] SoH-Fork-Seite (Panel, Hot-Reload, Portal, Item-Registry) nicht dokumentiert  — gap
- **Artikel/Datei:** (fehlender Artikel; betrifft soh/architecture/hybrid-architecture)
- **Problem:** Die In-Game-Hälfte des Systems hat keinen Wiki-Artikel: `LiveGenPanel.cpp` (471 LOC, Tabs Generate/My Dungeons/Debug Room), `LiveGenHotReload.cpp` (526 LOC, AddArchive/Eviction/DebugMode), `LiveGenEntrance.cpp` + `LiveGenBridge.cpp` (Portal via Entrance-Override, `LiveGen_ProcessEntrance` aus z_play.c), `LiveGenItemRegistry.cpp` (Custom Chest Content "Mario"), `LiveGenDecoration.cpp`. Auch die Namespaces `scenes/squadala/`, `scenes/squadala_custom/`, `scenes/squadala_mesh_lab/`, das Ausgabefile `zzz_squadala_dungeon.o2r` und Door_Warp1-Portal sind nirgends im Wiki erwähnt. Nur custom-geometry-pipeline streift Hot-Reload-Snippets.
- **Beleg:** `git -C soh-source ls-files | grep livegen` → 11 Dateien, `wc -l` = 1839 LOC; `grep -rli "LiveGenHotReload\|LiveGenEntrance\|Door_Warp1\|zzz_squadala\|scenes/squadala" .wiki/articles` → keine Treffer. `tooling/build_box_room.py:1171` `TARGET = "scenes/squadala"`, `:2873` `TARGET = "scenes/squadala_custom"`; `sidecar/src/livegen/api.py:131` `Path(mods_path) / "zzz_squadala_dungeon.o2r"`.

### [HIGH] Sidecar: DungeonStore, Spec-Bridge, GLB-Importer und Mods-Autodetect fehlen im Wiki  — gap
- **Artikel/Datei:** (fehlende Artikel; betrifft soh/architecture/hybrid-architecture, soh/architecture/custom-geometry-pipeline)
- **Problem:** Wesentliche Sidecar-Module ohne Doku: `dungeon_store.py` (Persistenz unter `~/.squadala/dungeons`, active-Marker, nur einmal im Endpoint-Table erwähnt), `compiler/box_room_dungeon.py` (M6 Spec-Bridge DungeonSpec → Custom-Geometry-`.o2r`, alle 21 ActorTypes), `tooling/mesh_to_dl.py` (trimesh-basierter GLB/OBJ/STL/PLY-Importer, M5++/Mesh), `api._detect_mods_path()`. Der README-Flow "mlx_lm.server … --port 11434" (Gemma 4 via MLX) kommt im Wiki nicht vor.
- **Beleg:** `sidecar/src/livegen/dungeon_store.py:12` `STORE_DIR = Path.home() / ".squadala" / "dungeons"`; `sidecar/pyproject.toml` dependency `trimesh>=4.5`; `grep -rli "box_room_dungeon\|mesh_to_dl\|trimesh\|GLB\|_detect_mods_path" .wiki/articles` → keine Treffer. `release_notes/features/spec_bridge.md`, `mesh_importer.md` existieren, Wiki-Pendant fehlt.

### [MEDIUM] Default-Model-ID `claude-sonnet-4-5-20250514` existiert nicht  — code-smell
- **Artikel/Datei:** sidecar/src/livegen/llm.py:59,227 · soh/features/llm-agent · .wiki/INDEX.md
- **Problem:** Der Anthropic-Default ist ein nicht existierender Snapshot-String. Die echte Sonnet-4.5-ID ist `claude-sonnet-4-5-20250929` (Alias `claude-sonnet-4-5`). Mit `LIVEGEN_LLM_PROVIDER=anthropic` ohne `LIVEGEN_MODEL` schlägt jeder Call mit not_found fehl. Das Wiki dokumentiert den falschen String als Fakt in zwei Artikeln.
- **Beleg:** `llm.py:59` `def __init__(self, model: str = "claude-sonnet-4-5-20250514", …)`; `llm.py:227` `os.environ.get("LIVEGEN_MODEL", "claude-sonnet-4-5-20250514")`; Wiki llm-agent: "**Modell:** `claude-sonnet-4-5-20250514` (Default…)"; Modell-Referenz (claude-api-Skill `shared/models.md:96`): "Claude Sonnet 4.5 | `claude-sonnet-4-5` | `claude-sonnet-4-5-20250929`".

### [MEDIUM] LLM-Agent: lokales Backend als "Tests/Offline" abgetan, ist aber der Haupt-Pfad  — stale
- **Artikel/Datei:** soh/features/llm-agent
- **Problem:** Artikel: "Lokales LLM-Backend für Tests/Offline-Betrieb". Im Code ist `OpenAICompatibleBackend` ein vollwertiges Backend mit drei Providern (`openai`/`ollama`, `lmstudio`) und eigenen Env-Vars (`LIVEGEN_LLM_PROVIDER`, `LIVEGEN_BASE_URL`, `LIVEGEN_API_KEY`); README, CLAUDE.md (M1: "Gemma 4 (100% success)", M4: "Gemma 4 via MLX") und SQUADALA.md beschreiben Gemma 4 lokal als Standard-Betrieb. Keine der Env-Vars steht im Wiki.
- **Beleg:** `llm.py:99-111` `class OpenAICompatibleBackend … base_url="http://localhost:11434/v1"`; `llm.py:217-243` `create_backend()` liest `LIVEGEN_LLM_PROVIDER`, `LIVEGEN_BASE_URL`, `LIVEGEN_API_KEY`; `grep -rl "LIVEGEN_LLM_PROVIDER\|LIVEGEN_BASE_URL" .wiki/articles` → leer. `README.md` Quick Start Schritt 4: `mlx_lm.server --model mlx-community/gemma-4-26b-a4b-it-4bit --port 11434`.

### [MEDIUM] Code-Root `soh-fork/soh/src/livegen/` existiert nicht  — broken-ref
- **Artikel/Datei:** .wiki/wiki.config.md (Code Roots) · CLAUDE.md (Komponenten-Tabelle)
- **Problem:** wiki.config.md nennt als Code Root "SoH-Fork (ab M4): `soh-fork/soh/src/livegen/`", CLAUDE.md "`soh-fork/` (ab M4)" und "Patches in `livegen/` halten". Ein Verzeichnis `soh-fork/` gibt es nicht; der Fork ist das Submodule `soh-source/` (Marvbuster/Shipwright-Squadala, branch develop), der Code liegt unter `soh-source/soh/soh/Enhancements/livegen/`.
- **Beleg:** `ls soh-fork` → "No such file or directory"; `.gitmodules`: `path = soh-source`, `url = git@github.com:Marvbuster/Shipwright-Squadala.git`; `git -C soh-source ls-files | grep livegen` → `soh/soh/Enhancements/livegen/LiveGen*.cpp`.

### [MEDIUM] Hybrid-Architektur: F2-Hotkey, SceneInjector/Scene-ID und /health-Payload stimmen nicht  — stale
- **Artikel/Datei:** soh/architecture/hybrid-architecture
- **Problem:** (a) "1. F2 drücken → ImGui-Panel öffnet sich": im Fork gibt es kein F2-Binding, das Panel wird über den Enhancements-Sidebar-Eintrag "Squadala" geöffnet (ESC → Enhancements → Squadala laut SQUADALA.md). (b) "7. SceneInjector registriert neue Scene-ID": tatsächlich wird kein Scene-ID registriert, sondern per Entrance-Override umgeleitet (`LiveGen_ProcessEntrance`). (c) "GET /health … gibt Version + Backend zurück": Code liefert nur `{"status": "ok"}`. (d) Das Ausgabefile ist fest `zzz_squadala_dungeon.o2r`, nicht generisch "nach mods/".
- **Beleg:** `grep -rn "F2" soh-source/soh/soh/Enhancements/livegen/` → leer; `soh-source/soh/soh/SohGui/SohMenuEnhancements.cpp:1938-1942` `AddSidebarEntry("Enhancements", "Squadala", 1); AddWidget(path, "Open Squadala", WIDGET_WINDOW_BUTTON)`; `LiveGenBridge.cpp:12` `int16_t LiveGen_ProcessEntrance(int16_t entrance)`; `sidecar/src/livegen/api.py:188-190` `def health() -> dict: return {"status": "ok"}`.

### [MEDIUM] Scene-Pfad-Namespace widersprüchlich: `scenes/shared/` vs `scenes/nonmq/` vs `scenes/squadala/`  — contradiction
- **Artikel/Datei:** soh/architecture/o2r-reverse-engineering · soh/architecture/soh-scene-format · soh/architecture/deku-tree-binary-analysis
- **Problem:** o2r-reverse-engineering zeigt die Archiv-Struktur unter `scenes/shared/{name}_scene/`, soh-scene-format (§6) und deku-tree-binary-analysis unter `scenes/nonmq/{scene}/…`. Kein Artikel erklärt, dass `nonmq` der Vanilla-Quellpfad und `shared` der (alte) Writer-Output ist, und dass der aktuelle Build in den eigenen Namespace `scenes/squadala/` schreibt (M7-2b, gerade um Vanilla-Pfad-Kollisionen zu vermeiden).
- **Beleg:** Wiki o2r-RE: "├── scenes/shared/{name}_scene/"; Wiki soh-scene-format: "scenes/nonmq/{scene_name}/{scene_name}_room_{N}"; Code `sidecar/src/livegen/compiler/o2r_writer.py:86` `scene_path = f"scenes/shared/{scene_name}_scene"`, `scene_builder.py:13` `DEKU_TREE = "scenes/nonmq/ydan_scene"`, `tooling/build_box_room.py:1171` `TARGET = "scenes/squadala"`; `docs/BACKLOG.md`: "M7-2b: Custom Scene unter `scenes/squadala/` (keine Vanilla-Pfad-Kollisionen)".

### [MEDIUM] Checklisten/„Nächste Schritte" zeigen erledigte Arbeit als offen  — stale
- **Artikel/Datei:** soh/architecture/o2r-reverse-engineering · soh/architecture/custom-geometry-pipeline
- **Problem:** o2r-RE Phase 4 (Box-Raum, Collision, DL, Actor, Tür, zweiter Raum) und Phase 5 (Entrance-Override 5.3, Hot-Reload 5.4) sind alle unchecked; Punkt 1.8 "Vertex-Daten dumpen" offen, obwohl OVTX implementiert ist. custom-geometry-pipeline "Nächste Schritte": "Box-Raum mit allen 6 Wänden…", "LLM-spezifizierte Meshes" — v0.5 (Box-Raum), v0.6 (Spec-Bridge), v0.7 (Multi-Room + En_Door), v0.8 (Portal) sind fertig.
- **Beleg:** Wiki o2r-RE: "- [ ] **4.1** Einfachsten möglichen Raum erzeugen", "- [ ] **5.4** Hot-Reload"; Code `tooling/build_box_room.py:266` "# OVTX — Vertex Resource", `LiveGenHotReload.cpp:77` `archiveMgr->AddArchive(o2rPath)`; `CLAUDE.md`: "M5++ | Vollständiger Box-Raum | Fertig", "M7 | Multi-Room | Fertig … En_Holl + En_Door".

### [MEDIUM] Dungeon-Schema-Enums stimmen nicht mit schema.py überein  — stale
- **Artikel/Datei:** soh/architecture/dungeon-schema
- **Problem:** Wiki: "ActorType: 22 OoT-Gegnertypen" → Code hat 21 (CLAUDE.md sagt ebenfalls 21). Wiki: "ChestContent: small_key, boss_key, map, compass, items, rupees" → Code hat 14 Werte, darunter `arrows_10/30`, `bombs_5/10`, `rupees_5/20/50`, `recovery_heart`, `piece_of_heart` und das Custom-Item `livegen_mario` (M5++/Items), das für die Item-Registry im Fork zentral ist; `items` und `rupees` existieren nicht.
- **Beleg:** `sidecar/src/livegen/schema.py:44-66` `class ActorType` mit 21 Membern (keese … tektite); `schema.py:69-86` `class ChestContent` … `livegen_mario = "livegen_mario"`; Wiki: "**ChestContent:** small_key, boss_key, map, compass, items, rupees".

### [MEDIUM] Hardcodierter Entwickler-Pfad als Mods-Autodetect  — code-smell
- **Artikel/Datei:** sidecar/src/livegen/api.py:28-37
- **Problem:** `_detect_mods_path()` prüft als ersten Kandidaten Robins Home-Pfad `~/workspace/SoH/soh-source/build-cmake/soh/mods`; es gibt keine Env-Var-Überschreibung (z. B. `LIVEGEN_MODS_PATH`). `/dungeons/{id}/activate` ignoriert zudem ein mitgegebenes `mods_path` und nutzt nur die Autodetektion, während `/compile` es akzeptiert. Auf jedem anderen Rechner liefert `/activate` einen 500.
- **Beleg:** `api.py:32` `os.path.expanduser("~/workspace/SoH/soh-source/build-cmake/soh/mods")`; `api.py:165-167` `mods_path = _detect_mods_path(); if not mods_path: raise HTTPException(500, …)`; `api.py:125` `mods_path = req.mods_path or _detect_mods_path()`.

### [MEDIUM] 27 Commits mit Claude-Attribution gegen die Hausregel  — code-smell
- **Artikel/Datei:** git log (Hauptrepo)
- **Problem:** Globale CLAUDE.md: "Never add Claude attribution to git commit messages. No `Co-Authored-By: Claude …` trailer". Die Historie enthält 27 Commits mit `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` bzw. Opus 4.6.
- **Beleg:** `git log --format='%H %s%n%b' | grep -ic "co-authored\|claude\|anthropic"` → 27; Beispiel-Trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

### [LOW] Collision-Magic "OCOL" vs "LOCO" inkonsistent benannt  — contradiction
- **Artikel/Datei:** soh/architecture/soh-scene-format (Magic-Tabelle) · soh/architecture/custom-geometry-pipeline
- **Problem:** soh-scene-format listet "OCOL | 4F434F4C", custom-geometry-pipeline nennt dieselbe Resource "LOCO". Die Tabelle mischt Darstellungen: "MORO | 4D4F524F" ist die On-Disk-Bytefolge, "OCOL | 4F434F4C" dagegen der uint32-Wert (On-Disk LE = "LOCO"). Beide Zeilen derselben Tabelle folgen unterschiedlichen Konventionen.
- **Beleg:** `tooling/build_box_room.py:56` `RES_COLLISION = 0x4F434F4C  # "LOCO" as LE uint32`; `build_box_room.py:54` `RES_SCENE = 0x4F524F4D  # "MORO" as LE uint32`; deku-tree-binary-analysis: "0x04: 4D 4F 52 4F  Magic "MORO"" (Bytes auf Disk).

### [LOW] nutshell/wiki.config behaupten Tech-Stack docker, ios, swift und Docker-Deployment  — stale
- **Artikel/Datei:** .wiki/nutshell.md · .wiki/wiki.config.md
- **Problem:** `tech_stack: [cpp, docker, ios, python, swift]`, `deployment: platform docker, self-hosted`. Im Repo gibt es keine Swift-/iOS-Dateien und kein eigenes Dockerfile; das einzige Dockerfile ist das Upstream-Build-Dockerfile von HarbourMasters im Submodule. Das Projekt ist ein lokaler Mod + lokaler Sidecar, kein Deployment.
- **Beleg:** `git ls-files | grep -iE "\.swift$|Dockerfile|docker-compose"` → leer (Hauptrepo); `soh-source/Dockerfile` ist Upstream-SoH.

### [LOW] CLAUDE.md und README driften vom Wiki ab (Wiki-Baum, M6, Release-Range)  — stale
- **Artikel/Datei:** CLAUDE.md · README.md (Einstiegspunkte, die aufs Wiki verweisen)
- **Problem:** CLAUDE.md zeigt einen Wiki-Baum mit 5 Artikeln (11 existieren) und "Dungeon-Katalog — 218 Räume". README: "M6 | Polish | Planned" und "release_notes/ … (v0.1 → v0.4)" vs CLAUDE.md "M6 Lebender Raum Fertig" und v0.8.
- **Beleg:** `CLAUDE.md` Abschnitt "Wiki": listet hybrid-architecture, dungeon-schema, soh-scene-format, dungeon-catalog, llm-agent; `wiki ls soh` → 11 Artikel. `README.md`: "| M6 | Polish | Planned |"; `release_notes/README.md`: "v0.8 … Abgeschlossen".

### [LOW] `uv.lock` wird per .gitignore ausgeschlossen  — code-smell
- **Artikel/Datei:** .gitignore · AGENTS.md
- **Problem:** `.gitignore` enthält `sidecar/uv.lock`; AGENTS.md/CLAUDE.md verlassen sich auf `uv sync` für reproduzierbare Installs. Ohne committetes Lockfile bekommt jede Maschine andere Versionen (fastapi/anthropic/trimesh nur mit Untergrenzen gepinnt).
- **Beleg:** `.gitignore`: "# uv\nsidecar/uv.lock"; `git ls-files | grep uv.lock` → leer; `sidecar/pyproject.toml` nur `>=`-Pins.
