"""FastAPI endpoints for the dungeon generation sidecar."""

from __future__ import annotations

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load .env before creating backend
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from livegen.agent import DungeonAgent, Session
from livegen.llm import create_backend
from livegen.schema import GenerationResult

app = FastAPI(title="LiveGen Sidecar", version="0.2.0")

# In-memory session store — fine for local sidecar, one game at a time
_sessions: dict[str, Session] = {}
_agent = DungeonAgent(backend=create_backend())


class CreateSessionRequest(BaseModel):
    prompt: str


class CreateSessionResponse(BaseModel):
    session_id: str
    result: GenerationResult


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    result: GenerationResult


@app.post("/sessions")
def create_session(req: CreateSessionRequest):
    """Start a new dungeon generation session with an initial prompt."""
    session_id = uuid.uuid4().hex[:12]
    session = Session(session_id=session_id)
    _sessions[session_id] = session

    result = _agent.start(session, req.prompt)
    resp = CreateSessionResponse(session_id=session_id, result=result)
    return JSONResponse(content=resp.model_dump(exclude_none=True))


@app.post("/sessions/{session_id}/message")
def post_message(session_id: str, req: MessageRequest):
    """Send a player response to continue the conversation."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.finished:
        raise HTTPException(status_code=409, detail="Session already finished")

    result = _agent.reply(session, req.message)
    resp = MessageResponse(result=result)
    return JSONResponse(content=resp.model_dump(exclude_none=True))


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get the current state of a session."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.result:
        result = GenerationResult(status="complete", spec=session.result)
    else:
        result = GenerationResult(status="questions")
    return JSONResponse(content=result.model_dump(exclude_none=True))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
