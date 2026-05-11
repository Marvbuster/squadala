# Squadala Backlog

Lebende Liste offener Themen. Drei Sektionen: geplante Milestones,
nice-to-have Ideen, bekannte Bugs. Erledigtes wandert ins `release_notes/`,
nicht hierher.

---

## Geplante Milestones

Spiegel der Tabelle in `CLAUDE.md` — Details zu dem was noch offen ist.

### M7 — Multi-Room (in Arbeit)

- [x] M7-1: 2 Räume in einer Scene
- [x] M7-2: Tür-Loch in geteilter Wand (3 Panels)
- [x] M7-2b: Custom Scene unter `scenes/squadala/` (keine Vanilla-Pfad-Kollisionen)
- [x] M7-3a: Collision mit Tür-Cutout
- [x] M7-3b: En_Holl Transition-Actor (Room-Wechsel)
- [x] M7-4: Room 2 + En_Door (sichtbare Holztür) + Hydrant-Chest
- [ ] **M7-5: Cupcake-Deko in Room 1** (rotierend, room-aware wie Pizza)

### M8 — LLM-Mesh-Generation
Sidecar generiert Mesh-Daten aus DungeonSpec, prozedurale Patterns,
optional ShapeLLM. Vorab-Recherche zu Modellen (MeshGPT, ShapeLLM,
Point-E o.ä.) und Strategien liegt in
`.wiki/articles/architecture/mesh-generation-research.md`.

### LLM Tooling / MCP-Server für Dungeon-Authoring

Sobald das LLM Räume selbst bauen soll, braucht es **dedizierte Tools**
mit Schemas — kein "Freitext-Prompt → hoffe es bleibt valide".
Idealerweise als MCP-Server (Model Context Protocol), den das LLM per
Tool-Call anspricht.

Erste Tool-Skizze:

- `room.create(name, dimensions, theme)` — neuer Raum mit Custom-Geometry
- `room.connect(from, to, door_type)` — Tür/Korridor zwischen Räumen
- `actor.place(room, type, position, params)` — Gegner/NPC platzieren
- `chest.place(room, position, content, treasure_flag)` — Truhe + Inhalt
- `puzzle.create(type, trigger, payoff)` — Schalter→Tür, Block-Puzzle,
   Torch-Lighting, Time-Trial, …
- `puzzle.validate(dungeon)` — prüft Solvability (TBC: Path-Solver,
   Inventar-Constraint-Check, kein Soft-Lock)
- `dungeon.compile()` — finale `.o2r`

Schemas (Pydantic / JSON-Schema) als Source-of-Truth:
- `RoomSpec`, `ActorSpec`, `ChestSpec`, `PuzzleSpec`, `DungeonSpec`
- Validierung auf Sidecar-Seite, Fehler als strukturierte Antworten
  zurück ans LLM → erlaubt Self-Correction.

Damit kann das LLM auch komplexere Sachen wie **mehrstufige Rätsel**
sauber planen ("dieser Schalter öffnet die Tür im Nachbarraum, der
Schlüssel dafür liegt hinter dem Boss") ohne Hand-Coding pro
Rätsel-Typ.

### M9 — Texturen
XETO-Textures, G_SETTIMG_OTR_HASH, Tile-Setup, Theme-Atlas.

### M10 — Polish
Streaming-UI, Debug-Overlay, Sound, Custom Lighting, Caching, Save/Load.

### M11 — Animation Pipeline
Skinned Meshes mit OoT-`SkelAnime`-Daten. Heute backt `mesh_to_dl.py` nur
einen statischen Rest-Pose-DL — die Maus-GLB in Room 2 trägt z.B. 3 Anims
(idle/run/jump) + 413-Node-Skelett, die alle ungenutzt bleiben. Schritte:
1. Skin/Joint-Hierarchie + Inverse-Bind-Matrizen aus GLB extrahieren →
   Limb-Tree-Struktur (vergleichbar mit OoT-Standard-`SkelLimbHeader`).
2. Pro Limb eigenes DL emitten (heute alles in einem flachen Mesh).
3. Animation-Tracks (Translation/Rotation pro Joint pro Frame) in
   OoT-Pose-Format umwandeln.
4. Custom-Actor mit `SkelAnime_Update` + DrawFunc statt Decoration-DL —
   Decorations sind Static-Draws ohne Update-Lifecycle.

Voraussetzung: M9 (Texturen), sonst sieht jeder skinned Mesh weiter
flach-shadiert aus.

### v1.0 — Custom Dungeon Showcase
5–7 Räume + Mini-Boss + Boss + Item-Logik, durchspielbar.

---

## Nice-to-have / Future Ideas

- **Dynamic Deco-Registry** — `LiveGenDecoration.cpp` hardcoded heute zwei
  Display-Lists mit Welt-X-Ranges (Pizza/Cupcake im 3-Raum-Debug-Setup).
  Sobald das LLM Räume baut, kennt der C++-Code weder die Anzahl noch die
  Layouts. Drei Optionen, in steigender Sauberkeit:
  1. **Build-time-Header**: `tooling/build_box_room.py` emittiert beim
     Compile zusätzlich einen `decoration_table.h` mit den Ranges, der
     mit dem nächsten SoH-Build mit reinkommt. Schnell zu bauen, aber
     Hot-Reload braucht trotzdem Game-Restart.
  2. **Daten im `.o2r`**: Eigener Resource-Type `DecorationList` neben
     Scene/Room. Sidecar packt das mit, SoH lädt es zur Laufzeit. Echtes
     Hot-Reload möglich, aber neuer Resource-Factory-Code im Fork.
  3. **Deko als echter Actor**: Custom-Actor in der LLM-Scene, dessen
     `room`-Feld die Vanilla-Cull-Logik (`func_80031A28`,
     `Actor_UpdateAll` mit room-mask) übernimmt. Kein neuer Daten-Channel,
     keine custom Cull-Heuristik im Render-Hook nötig — der Actor-Layer
     macht es richtig. Zielbild ab M8+.
- **Dynamic N64 music per dungeon** — LLM komponiert MIDI mit N64-Sound-
  Bänken passend zum Dungeon-Theme. Schließt die "alles passt zusammen"-
  Lücke, weil sceneNum=0 sonst immer Deku-Tree-Musik liefert. Siehe
  Memory `project_future_dynamic_music.md`.
- **SceneNum-Decoupling** — sceneNum auf `SCENE_TESTROOM` (0x6E) o.ä.
  umrouten wenn Debug-Room aktiv, damit Vanilla-Deku-Tree-Logik
  (Musik, Title-Card "Im Deku Baum", Treasure-Flag-Range, Cutscene-
  Trigger) komplett wegfällt. Heute trickst der Treasure-Flag eines
  Custom-Chest gegen Vanilla-Flags (siehe Saber → fall-through-floor;
  hatten als treasure_flag=5 statt 3 umgangen).
- **GLB-Texture → Vertex-Color baking im Loader** — `mesh_to_dl.py` liest
  aktuell nur `baseColorFactor`. Wenn das GLB stattdessen ein
  `baseColorTexture` mitbringt, sampeln wir nicht in die Vertex-Farben,
  sondern fallen auf `color_override`/`default_color` zurück (siehe
  Fire-Hydrant: musste manuell als Solid-Color gesetzt werden). Sauberer
  Loader-Path: pro Vertex UV nehmen → Texture an UV samplen → diese
  Farbe pro Vertex schreiben.
- **Free-Cam / Debug-Overlay** — Position/Camera/curRoom als On-Screen-
  Overlay, plus Free-Fly-Camera für Mesh-Inspection ohne Link-Constraint.
  Hätte uns beim Black-Screen-Debug deutlich Zeit gespart.
- **TextureCustom-Path für Item-DLs** — z.B. Sonic/Hydrant kriegen
  Vanilla-Light-Beleuchtung über G_LIGHTING statt unserer flachen
  `G_CC_SHADE`, dann brauchen wir kein Pre-Bake der Face-Schattierung
  in `mesh_to_dl.shade_strength`.

---

## Bekannte Bugs / Workarounds

- **Saber-Modell** verformt sich beim `y_offset=0` Re-Centering. Workaround:
  durch Fire-Hydrant ersetzt. Eigentliche Ursache unklar — möglicherweise
  ein OBJ-Parser-Issue bei nicht-zentrierten Source-Meshes.
- **VTX-Log-Spam** in `interpreter.cpp` ist mit `sLgVtxLogsLeft=30`
  einmalig gedeckelt (statt per Frame). Funktional ok, aber das Counter-
  Pattern ist eklig — bei vollem Reset (z.B. Spiel-Neustart ohne Restart
  vom Build) sieht man das Log nicht. Schöner wäre eine ringbuffer-
  basierte Variante oder ein CVar.
- **Custom-Chest item_id-Limit** — `chest_params` packt nur 7 Bit (max
  0x7F). Mit Mario (0x7E) + Sonic (0x7F) + Hydrant (auf 0x7D = vanilla
  GI_TEXT_0 verlegt) sind die freien Placeholder-Slots aufgebraucht.
  Erweiterte Item-IDs brauchen entweder ein anderes Encoding (höhere
  Param-Bits ausnutzen) oder eine Tabelle, die Chest-7-Bit-IDs auf
  echte 16-Bit-GIs mapt.
- **`func_80031A28` Actor-Cleanup** killt jeden Actor dessen Required-
  Object nicht in der neuen Room-ObjectList steht. Heute umgangen,
  indem wir die Union aller Actor-Objekte aus allen Rooms in jeden
  Room schreiben. Für 3 kleine Räume harmlos; in großen Dungeons
  ist das Memory-Verschwendung — sollte später per-room-genau werden
  (nur die Objekte einbeziehen, die Actors mit `roomNumber` in die
  jeweils benachbarten Rooms tatsächlich brauchen).
