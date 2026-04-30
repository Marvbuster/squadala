---
title: "Mesh Generation Research — MeshLLM + ArtLLM"
created: 2026-04-30
updated: 2026-04-30
category: architecture
tags: [mesh, llm, geometry, 3d, generation, research, WICHTIG]
status: current
related:
  - architecture/o2r-reverse-engineering
  - architecture/soh-scene-format
---

# Mesh Generation Research — MeshLLM + ArtLLM

> **WICHTIG:** Diese Paper zeigen wie wir eigene Dungeon-Geometrie generieren können.

## Paper 1: MeshLLM (Aug 2025, ICCV)

**"Empowering Large Language Models to Progressively Understand and Generate 3D Mesh"**

### Kern-Idee

LLMs können 3D-Meshes **als Text** verstehen und generieren. Kein spezieller 3D-Encoder nötig — das Mesh wird direkt als OBJ-Format-Text serialisiert:

```
v 32 12 11
v 32 21 13
v 28 51 23
...
f 1 3 2
f 4 3 5
...
```

### Wie es funktioniert

1. **Quantisierung**: Vertex-Koordinaten werden auf Integer [0, 64] gemappt
2. **Sortierung**: Vertices nach z-y-x sortiert, Faces nach kleinstem Vertex-Index
3. **Text-Serialisierung**: Standard OBJ-Format als String
4. **Primitive-Mesh Decomposition**: Große Meshes werden in kleine Subunits zerteilt (KNN + semantische Segmentierung)

### Training (3 Phasen, progressiv)

1. **Phase 1**: Training auf KNN-basierten Primitive-Meshes (1.5M+ Samples!)
   - Task: Vertex → Face Prediction (aus Vertices Faces ableiten)
   - Task: Mesh Assembly (aus Teilen ganzes Mesh zusammenbauen)
2. **Phase 2**: Training auf semantisch segmentierten Primitives (100K+)
3. **Phase 3**: Fine-Tuning auf Mesh-Generierung + Mesh-Verständnis

### Key Technical Details

- **Basis-Modell**: LLaMA-8B-Instruct
- **Max Context**: 8192 Tokens
- **Max Faces**: 800 pro Mesh (Token-Limit)
- **Quantisierung**: [0, 64] Range (65 mögliche Werte pro Achse)
- **Training**: 128× A800 GPUs, ~6 Tage
- **Dataset**: Objaverse-XL + ShapeNet (1.5M+ Primitive-Meshes)

### Relevanz für Squadala

**SEHR HOCH.** Wir könnten:

1. **Gemma 4 direkt nutzen** um einfache Raum-Meshes als OBJ-Text zu generieren
   - Prompt: "Generate a rectangular dungeon room with 2 doorways, OBJ format, quantized to [0,64]"
   - Output: `v 0 0 0 v 64 0 0 v 64 0 64 ... f 1 2 3 ...`

2. **OoT-Räume als Training/Few-Shot verwenden**
   - Wir haben `deku_tree_collision.obj` mit 1399 Vertices, 2321 Faces
   - Das als Few-Shot-Beispiel im Prompt für Gemma

3. **Quantisierung passt perfekt** zu OoT
   - OoT nutzt int16 Koordinaten (-32768 bis 32767)
   - MeshLLM quantisiert auf [0, 64]
   - Wir können auf [-500, 500] quantisieren für Raum-Größe

4. **800 Faces Limit** reicht für einfache Dungeon-Räume
   - Ein Box-Raum hat 12 Faces
   - Ein Raum mit Säulen/Treppen: ~100-200 Faces
   - Ein komplexer Raum: ~500 Faces

### Einschränkungen

- Braucht Fine-Tuning für gute Ergebnisse (128 GPUs, 6 Tage)
- Ohne Fine-Tuning: Gemma könnte trotzdem einfache Meshes generieren (Zero-Shot/Few-Shot)
- Max 800 Faces — für detaillierte Räume evtl. zu wenig
- Keine Texturen — nur Geometrie

---

## Paper 2: ArtLLM (Mar 2026)

**"Generating Articulated Assets via 3D LLM"**

### Kern-Idee

Ein 3D LLM das **gegliederte Objekte** (Türen, Schubladen, Maschinen) generiert — mit korrekten Gelenken und Bewegungsmechaniken. Nutzt URDF (Unified Robotics Description Format) als Textformat.

### Wie es funktioniert

1. **Input**: Point Cloud eines Objekts
2. **ArtLLM** (3D LLM): Predicts tokenized "blueprint" mit:
   - Part Layouts (wo ist jedes Teil)
   - Joint Parameters (Rotation/Translation Achsen)
   - Kinematische Struktur (welche Teile bewegen sich zusammen)
3. **Part Generator**: Synthesiert hochauflösende 3D-Geometrie pro Teil
4. **Physics Correction**: Optimiert Joint-Limits für kollisionsfreie Bewegung

### Key Technical Details

- **Input**: Point Cloud (quantisiert)
- **Output**: URDF-artiges Token-Format für Artikulation
- **Part Layout**: Bounding Box + Pose pro Teil (quantisiert auf [0, 255])
- **Joint Prediction**: Typ (revolute/prismatic), Achse, Position, Limits
- **Basis-Modell**: 3D LLM (wahrscheinlich LLaMA-basiert)
- **Training Data**: PartNet-Mobility Dataset + prozedural generierte Objekte

### Relevanz für Squadala

**MITTEL.** Interessant für:

1. **Tür-Generierung**: Türen sind artikulierte Objekte (Scharnier = revolute joint)
2. **Interaktive Objekte**: Schalter, Hebel, Truhen — alles artikuliert
3. **URDF-Format**: Könnte als Intermediate-Representation dienen

Aber: weniger relevant als MeshLLM für die Raum-Geometrie selbst.

---

## Strategie für Squadala Custom Geometry

### Phase 1: Einfache Box-Räume (JETZT machbar)

Ohne LLM, rein prozedural:
- Box-Raum Generator in Python
- Parameter: Breite, Höhe, Tiefe, Tür-Positionen
- Output: Vertices + Faces → Display List → .o2r

### Phase 2: LLM-generierte Raum-Layouts (MeshLLM-Ansatz)

Mit Gemma 4 (oder fine-tuned Modell):
- Prompt beschreibt Raumform + Features
- Gemma generiert OBJ-Text (quantisierte Vertices + Faces)
- Pipeline konvertiert OBJ → N64 Display List → .o2r

### Phase 3: Texturierte Räume (Zukunft)

- MeshLLM für Geometrie
- Stable Diffusion für Texturen (haben wir schon!)
- Kombination: generierter Raum mit KI-Texturen

### OoT-Räume als Referenz

Wir haben bereits:
- `deku_tree_collision.obj` (1399 Vertices, 2321 Faces) — exportiert!
- 218 Raum-Templates katalogisiert
- Vertex/Face Format der Display Lists verstanden

Diese können als **Few-Shot Beispiele** im LLM-Prompt dienen:
"Here is an example OoT dungeon room: [OBJ data]. Generate a similar room with [description]."

### Konversion OBJ → N64 Display List

```
OBJ (v + f) → Quantize → N64 Vtx Format → GBI Commands → TLDO Resource → .o2r
```

Der schwierigste Schritt ist OBJ → GBI Display List. Aber:
- Fast64 (Blender Plugin) macht genau das
- Wir könnten Fast64's Export-Code als Referenz nutzen
- Oder einen minimalen Python-Konverter schreiben für einfache Geometrie
