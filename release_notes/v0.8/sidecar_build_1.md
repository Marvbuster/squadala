# OoT Live Dungeon Sidecar v0.8.0 Build 1

**Datum:** 11.05.2026 | **Status:** Abgeschlossen | **Milestone:** Tooling

## Zusammenfassung

`tooling/build_box_room.py` wird zum richtigen Sandbox-Compiler: neue `build_mesh_lab_o2r(layout=...)` mit vier Layouts (Empty Box / L-Shape / Maze v1 / Maze Complex), neue `build_custom_dungeon_o2r()` für den Portal-Ziel-Slot, plus geometrie-seitig zwei größere Renovierungen: Thick-Wall-Blocks gegen "spitze Plane"-Kanten und automatisches Vertex-Batching für Meshes >64 Verts.

## Features & Änderungen

### Mesh Lab Pipeline

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `build_mesh_lab_o2r(output, layout=...)` — vier Layouts: `empty`, `l_shape`, `maze`, `maze_complex` |
| FEATURE | `--mesh-lab` CLI baut alle vier `.o2r`-Varianten auf einmal |
| FEATURE | Eigener Namespace `scenes/squadala_mesh_lab/` — Hot-Reload-Wechsel evicted nie die Dungeon-Cache |
| FEATURE | `_build_l_shape_geometry` + `_build_l_shape_collision` — L-Shape mit korrekter CCW-Perimeter-Winding (interior-on-right) für Visual + Collision |
| FEATURE | `_build_thick_maze(bounds, wall_blocks, thin_walls)` — Mixed-Mode: dicke Block-Walls (4 Outward-Faces, no spitze Edges) + thin walls (1 Plane, flush mit Türen). Door-Cutout-Logik emittiert Left/Lintel/Right-Panels |
| FEATURE | Maze v1: Z-Zigzag mit kleinem Chest (Small Key, treasure_flag=10) + Locked En_Door + großem Chest (Heart Piece, treasure_flag=11) |
| FEATURE | Maze Complex: 4 Barrieren + 2 Dead-End-Stubs, thick blocks im Inneren, thin door-wall die hinter den Outer-Walls bei x=±510 versteckt ist |

### Custom Dungeon Slot

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | `build_custom_dungeon_o2r(output)` — single empty 2000×800×3000 box in `scenes/squadala_custom/` Namespace |
| FEATURE | `--custom-dungeon` CLI baut diese .o2r — Ziel des Door_Warp1-Entry-Portals |

### DL Builder — Vertex-Batching

| Typ | Beschreibung |
|-----|-------------|
| FIX | `build_display_list` splittet Verts jetzt in 64-Vertex-Batches (F3DEX2 `MAX_VERTICES`). Pro Batch eigene G_VTX_OTR_HASH-Command mit `w1=byte_offset` in dieselbe Vertex-Resource, Tri-Indices remapped auf Buffer-Local (0..63). Vorher crashte alles >64 Verts mit "Unhandled OP code: 0x17" weil `dst = end - n` im Encoding überlief |
| FIX | Maze Complex (136 Verts) rendert jetzt korrekt; vorher schwarzer Screen + Engine-Crash |

### Geometrie-Shading

| Typ | Beschreibung |
|-----|-------------|
| FEATURE | Per-Wall-Palette im L-Shape (6 Wände, vivid colors) + Fake-Light-Shading (dot product mit `(0.4, 0.8, -0.4)` als Sonnenrichtung, `shade_strength=0.55`). Adjacent Walls bekommen unterschiedliche Töne damit Ecken sichtbar sind |
| FEATURE | Maze-Wände nutzen dieselbe Shading-Logik — outer perimeter cyan/blau/magenta/gelb, interior blocks orange/lime/etc. |
| FEATURE | Floor + Ceiling kriegen eigene Base-Colors + Shading (warm-grün / kühl-blaugrau) |

### Bug-Fixes Tooling

| Typ | Beschreibung |
|-----|-------------|
| FIX | L-Shape Perimeter war CW statt CCW gewickelt → Wände back-face-culled von innen + Collision-Normalen invertiert → Link fiel durch. Fixed durch Reverse der Walk-Direction |
| FIX | Door-Cutout-Wand: visuelles Loch in der Wand passt zur En_Door-Panel-Größe (60×100), Lintel-Panel oben schließt die View-Through-Lücke |
| FIX | Thick-Wall-Blocks 1 Unit von der Outer-Perimeter zurückgezogen (`-499` statt `-500`) — Face-Coincidence mit Outer-Walls erzeugte gestapelte Collision-Polys, Engine wurde verwirrt |

## Architektur-Erkenntnisse

### Thin vs Thick Walls — der Trade-off

Thin Single-Plane-Walls (v1 Maze) lassen die Tür perfekt bündig sitzen — En_Door's Panel ist null Z-Tiefe, also ist es egal ob die Wand 1 Unit oder 30 Units dick ist, das Panel ist nie versetzt zum Wand-Loch. Aber: thin walls haben Endpunkte. Wenn ein Endpunkt in offenem Raum liegt, sieht man die 2D-Ebenenkante von der Seite ("spitze Wand").

Thick Blocks (v2) lösen das mit vier Outward-Faces — keine Plane-Edge je sichtbar. Aber: die Tür sitzt in der Mitte der Block-Dicke, beim Reingucken durch das Loch sieht's wie eine eingerückte Türnische aus.

Lösung im Maze Complex: Mix. Alle Wände sind thick blocks, AUSSER die Tür-Wand — die ist eine einzige thin plane, deren Endpunkte 10 Units über die Outer-Perimeter rausragen und damit hinter den Outer-Walls verschwinden. Beste aus beiden Welten.

### VTX-Batching: `w1` ist Byte-Offset

`build_unindexed_dl` (für die Mario/Sonic/Hydrant-Asset-Loads) nutzt schon das Pattern: G_VTX_OTR_HASH's `w1`-Word ist ein **Byte-Offset** in die Vertex-Resource, nicht der Vertex-Index. Damit kann man eine große VTX-Resource in mehreren G_VTX-Aufrufen häppchenweise laden. Der bisherige `build_display_list` setzte `w1=0` und versuchte alles in einem Schub → bei >64 Verts knallte's. Jetzt rechnen wir pro Batch `byte_offset = batch_start_q * 4 * 16` und remappen die Triangle-Indices auf den 64-Vert-Buffer-Slot.

## Verzeichnisstruktur (generiert)

```
debug_rooms/
├── zzz_squadala_dungeon.o2r          (3-Raum Debug Room — unverändert)
├── zzz_mesh_lab_empty.o2r            (Sandbox: leerer Box)
├── zzz_mesh_lab_l_shape.o2r          (Sandbox: L-Shape)
├── zzz_mesh_lab_maze.o2r             (Sandbox: simple maze)
├── zzz_mesh_lab_maze_complex.o2r     (Sandbox: thick-walled complex maze)
└── zzz_squadala_custom_dungeon.o2r   (Custom Dungeon: empty 2000×800×3000)
```

## Nächste Schritte

- M8 (LLM-Mesh-Generation): Sidecar generiert Custom-Dungeon-Inhalte und schreibt sie in den `zzz_squadala_custom_dungeon.o2r`-Slot
- Title-Card-System für die Custom Dungeon Landung
- Exit-Warp im Custom Dungeon (auto-spawn aktuell deaktiviert)
