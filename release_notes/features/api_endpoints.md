# API Endpoints

FastAPI-basierte HTTP-Schnittstelle zwischen SoH und dem Sidecar.

## Übersicht

| Eigenschaft | Wert |
|-------------|------|
| Dateien | `sidecar/src/livegen/api.py` |
| Framework | FastAPI |
| Port | 7777 (localhost) |

## Endpoints

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| POST | `/sessions` | Neue Dungeon-Generation starten |
| POST | `/sessions/{id}/message` | Spieler-Antwort auf Rückfrage senden |
| GET | `/sessions/{id}` | Aktuellen Status einer Session abrufen |
| GET | `/health` | Health-Check |

## Request/Response

### POST /sessions
```json
// Request
{ "prompt": "Ein Eis-Dungeon mit drei Räumen und einem Mini-Boss" }

// Response
{
  "session_id": "a1b2c3d4e5f6",
  "result": {
    "status": "questions",
    "question": { "question": "Welches Theme?", "options": ["ice", "fire"] }
  }
}
```

### POST /sessions/{id}/message
```json
// Request
{ "message": "Ice bitte" }

// Response
{
  "result": {
    "status": "complete",
    "spec": { "metadata": { "name": "..." }, "rooms": [...] }
  }
}
```

## Status-Werte

| Status | Bedeutung |
|--------|-----------|
| `questions` | Agent hat eine Rückfrage |
| `complete` | DungeonSpec ist fertig |
| `error` | Fehler aufgetreten |
