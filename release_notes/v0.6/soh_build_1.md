# OoT Live Dungeon SoH-Fork v0.6.0 Build 1

**Datum:** 04.05.2026 | **Status:** Abgeschlossen | **Milestone:** M6

## Zusammenfassung

Defensive 1-Liner-Schutz in `Item_Give` gegen `ITEM_NONE`-OOB-Reads. Ansonsten keine SoH-Code-Änderungen in v0.6 — alle M6-Erweiterungen (Spec-Bridge, ACTOR_LIBRARY, Item-Showcase, längerer Box-Raum) leben sidecar- und tooling-seitig und brauchten kein neues Engine-Verhalten.

Gegenüber v0.5 wird durch die größere Default-`.o2r` mehr aus den existierenden v0.5-Hooks (LiveGenItemRegistry, LiveGenDecoration, ItemTableManager::SetItemEntry) gezogen, ohne dass diese sich ändern mussten.

## Features & Änderungen

### z_parameter.c

| Typ | Beschreibung |
|-----|-------------|
| FIX | `Item_Give(ITEM_NONE)` Null-Item-Guard ganz oben in der Funktion. Schützt vor OOB-Read bei `gItemSlots[0xFF]` (Array hat nur 56 Einträge, 0xFF ist undefiniert) und dem nachfolgenden OOB-Schreibzugriff auf `gSaveContext.inventory.items[<garbage_slot>]`. Generic Safety Guard, nicht LiveGen-spezifisch — schützt alle Aufrufer. |

## Wirkung auf bekannte v0.5-Limitations

Der "bekannte Restpunkt" aus den v0.5 Release Notes — `Item_Give(ITEM_NONE)` läuft am Ende des Get-Item-Flows und ist OOB-Read aber in der Praxis stabil — ist jetzt sauber abgesichert. Custom Spectacle-Items mit `itemId=ITEM_NONE` (LiveGen-Pattern) reichen den Get-Item-Flow ohne Inventar-Side-Effekt durch.

## Architektur-Erkenntnisse

### Defensive Guard vs. VB-Hook

Alternativ hätten wir einen neuen `VB_GIVE_ITEM_FROM_GET_ITEM_FLOW`-Hook in `z_player.c::func_8084DFF4` einbauen können, gated by gating LiveGen über die VB-Hook-Mechanik. Das wäre LiveGen-spezifischer, hätte aber zwei upstream-Stellen geändert (Hook-Call + neuer Enum-Value in `GIVanillaBehavior.h`). Der Null-Check in `Item_Give` ist:

- **Eine Stelle, ein Liner.**
- **Generic** — beschützt nicht nur LiveGen, sondern jeden zukünftigen Aufrufer der unwitting `ITEM_NONE` reichen würde.
- **Defensiv** — ändert vanilla-Verhalten nur für undefined-behavior-Inputs, alle gültigen Items bleiben unangetastet.

## Bekannte Limitationen

(Keine neuen — die v0.5-Limitations zu Cupcake/Multi-Room/Texturen sind in M7-M9 geplant.)
