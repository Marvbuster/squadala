Release Wrap: Versionierung, Release Notes und Commit für OoT Live Dungeon.

## Schritte

1. **Änderungen seit letztem Release identifizieren:**
   - Git log seit dem letzten Release-Commit / Tag
   - Identifiziere alle Features, Fixes und Breaking Changes
   - Prüfe welche Milestones betroffen sind (M1–M6)

2. **Version bestimmen:**
   - Lies aktuelle Version aus `sidecar/pyproject.toml`
   - Entscheide ob Bump nötig (neue Features = Minor, nur Fixes = Patch)
   - Version in pyproject.toml updaten

3. **Release Notes erstellen/updaten:**
   - **Sidecar:** `release_notes/v{VERSION}/sidecar_build_{N}.md`
   - **SoH-Fork:** `release_notes/v{VERSION}/soh_build_{N}.md` (wenn SoH-Änderungen)
   - **Version-README:** `release_notes/v{VERSION}/README.md` Builds-Tabelle updaten
   - **Root-README:** `release_notes/README.md` Versionsübersicht updaten
   - Format: Tabelle mit Typ (FEATURE/FIX/ENHANCEMENT) + Beschreibung + Feature-Datei
   - Status auf "Abgeschlossen" setzen für abgeschlossene Builds

4. **Feature-Dateien updaten:**
   - Wenn neue Features hinzukamen: `release_notes/features/{feature}.md` anlegen oder aktualisieren
   - Cross-Referenzen aus Build-Files müssen funktionieren

5. **CLAUDE.md updaten:**
   - Milestone-Status-Tabelle aktualisieren
   - Neue Kommandos oder Architektur-Änderungen dokumentieren

6. **Memory updaten:**
   - Relevante Projekt-Erkenntnisse in Memory speichern

7. **Git Commit + Push:**
   - `git add -A && git commit -m "docs: v{VERSION} — {Zusammenfassung}"`
   - Nur committen und pushen wenn es Änderungen gibt
