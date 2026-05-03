# OoT Live Dungeon Sidecar v0.4.0 Build 1

**Datum:** 03.05.2026 | **Status:** Abgeschlossen | **Milestone:** M5+

## Zusammenfassung

Custom 3D-Geometrie rendert in Ship of Harkinian! `tooling/build_box_room.py` produziert ein vollständiges `.o2r` mit Custom Scene, Room, Display List, Vertex-Resource und Collision. Vier farbige Triangles werden korrekt vom N64 Display List Interpreter ausgeführt.

## Features & Änderungen

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | CRC64-Implementierung — exakter Port von SoH's `StrHash64.cpp` (ECMA-182, kein Final Inversion) |
| FEATURE | OVTX-Vertex-Resource-Builder (16 Bytes/Vertex, alle LE) |
| FEATURE | TLDO-Display-List-Builder mit `G_VTX_OTR_HASH` (0x32, expanded 16B) |
| FEATURE | MORO-Scene-Builder — Custom Scene mit 1 Room, keine Transition Actors, Pfad zur Custom Collision |
| FEATURE | MORO-Room-Builder — SetMesh Type 0 mit Pfad zur Custom DL |
| FEATURE | LOCO-Collision-Builder — flacher Boden mit korrekten CamData-Einträgen |
| FEATURE | Resource-Header-Builder — gemeinsamer 0x40-Byte Header für alle SoH-Ressourcen |
| FIX | `G_MDSFT_RENDERMODE = 3` (nicht 0!) — der entscheidende Bug der zwei Tage gekostet hat |
| FIX | Vertex-Indexing für G_TRI2 — `vN*2 << shift` mit korrekten Shifts (16, 8, 0) |
| FIX | Skybox-Settings sind 4 Bytes (unk, skyboxId, weather, indoors), nicht 3 |
| FIX | Spawn-Actor-ID = `0x0000` (ACTOR_PLAYER), nicht `0x000F` (Bg_Ydan_Sp) |
| FIX | SpecialObjects mit `struct.pack('<h', 1)` für korrekte Endianness |
| FIX | Collision mit gültigem CamData-Eintrag (sonst Crash in `Camera_Update`) |
| FEATURE | 64 Pytest-Tests (`test_build_box_room.py`) — CRC64-Tabelle, Resource-Header, Vertex-Format, DL-Encoding, Geometry, Room, Collision, Integration |

## Tests

```
$ uv run pytest tooling/test_build_box_room.py -v
============================== 64 passed in 0.05s ==============================
```

64 Tests, alle grün. CRC64-Tabelle gegen bekannte Werte verifiziert (Polynom 0x42F0E1EB...), DL-Bytes gegen Original-Deku-Tree-DL verglichen.

## Generierte .o2r-Struktur

```
zzz_squadala_dungeon.o2r (2046 bytes):
├── scenes/nonmq/ydan_scene/ydan_scene              (Custom Scene, 279B)
├── scenes/nonmq/ydan_scene/ydan_room_0             (Custom Room, 173B)
├── scenes/nonmq/ydan_scene/squadala_box_DL         (Custom DL, 152B)
├── scenes/nonmq/ydan_scene/squadala_box_Vtx        (Custom Vertices, 452B)
└── scenes/nonmq/ydan_scene/ydan_sceneCollisionHeader_00B610  (Custom Collision, 172B)
```

## Verifikationsmethode

Hex-Dump des Original-Deku-Tree-DL `ydan_room_0DL_0033F0` mit `python3 -c "..."` und Vergleich Byte-für-Byte mit unserem DL. Das war die einzige Methode den `G_MDSFT_RENDERMODE`-Bug zu finden — beide DLs hatten denselben Combiner-Setup, aber unterschiedliche `G_SETOTHERMODE_L` Bytes:

- Original: `w0 = 0xE200001C` (sft=3)
- Unser:    `w0 = 0xE200031C` (sft=0) ← FALSCH

Mit `sft=0` wurde der Render-Mode in Bits 0-28 geschrieben, mit `sft=3` korrekt in Bits 3-31 (wo die echten Render-Mode-Bits sind).

## Nächste Schritte

- Box-Raum mit allen 6 Wänden + Boden + Decke (statt nur 4 Triangles)
- Mesh-Generator für LLM-spezifizierte Räume (DungeonSpec → Custom Geometry)
- Texturen statt nur Vertex-Farben
