# OoT Live Dungeon v0.4 — Custom 3D Geometry Rendering

**Zeitraum:** Mai 2026
**Fokus:** Erste eigene 3D-Geometrie in Ship of Harkinian — Custom Display Lists rendern korrekt

## Highlights

🎉 **Custom Geometry Rendering funktioniert!** Vier farbige Triangles (Rot/Grün/Blau/Gelb) rendern in unserem Custom-Raum. Damit ist die komplette Pipeline bewiesen: Custom Scene → Custom Room → Custom Display List → Custom Vertices via CRC64-Hash → sichtbare Pixel auf dem Bildschirm.

Der entscheidende Bug war ein einziges Bit-Shift: `G_MDSFT_RENDERMODE = 3`, nicht `0`. Der Render-Mode wurde 3 Bits zu niedrig in das OtherMode-Register geschrieben — mit `sft=3` wurde er sofort sichtbar.

## Builds

### Sidecar
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 03.05.2026 | Abgeschlossen |

### SoH-Fork
| Build | Datum | Status |
|-------|-------|--------|
| 1 | 03.05.2026 | Abgeschlossen |

## Milestones

- **M5 (Hot-Swap):** Komplett funktionsfähig — Custom .o2r wird zur Laufzeit geladen, Resources werden korrekt evicted/preloaded
- **M5+ (Custom Geometry):** Bonus-Milestone erreicht — erste eigene 3D-Geometrie rendert!

## Verzeichnisstruktur

```
v0.4/
├── README.md
├── sidecar_build_1.md
└── soh_build_1.md
```
