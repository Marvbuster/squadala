# LLM Agent

Claude-basierter Dungeon-Architekt mit Tool-Use-Konversation.

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Dateien | `sidecar/src/livegen/agent.py` |
| Modell | claude-sonnet-4-5 |
| SDK | Anthropic Python SDK |

## Funktionsweise

Der Agent führt eine Tool-Use-Konversation mit dem Spieler:

1. Spieler beschreibt gewünschten Dungeon
2. Agent stellt 0–3 Rückfragen via `ask_player`
3. Agent submitted fertigen DungeonSpec via `submit_dungeon`
4. Schema-Validierung bei Submit — bei Fehler bekommt der Agent einen Tool-Error und kann korrigieren

## Tools

| Tool | Beschreibung | Max Aufrufe |
|------|-------------|-------------|
| `ask_player` | Rückfrage an den Spieler mit optionalen Antwort-Optionen | 3 |
| `submit_dungeon` | Finalen DungeonSpec einreichen | 1 |

## Session-Tracking

- Jede Generation hat eine eigene `Session` mit Message-History
- Fragen-Zähler verhindert endlose Rückfrage-Schleifen
- Nach Quota-Erschöpfung wird `ask_player` aus der Tool-Liste entfernt
