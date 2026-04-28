"""FastAPI endpoints for the dungeon generation sidecar."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from livegen.agent import DungeonAgent, Session
from livegen.llm import create_backend
from livegen.schema import GenerationResult

app = FastAPI(title="LiveGen Sidecar", version="0.1.0")

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


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    """Start a new dungeon generation session with an initial prompt."""
    session_id = uuid.uuid4().hex[:12]
    session = Session(session_id=session_id)
    _sessions[session_id] = session

    result = _agent.start(session, req.prompt)
    return CreateSessionResponse(session_id=session_id, result=result)


@app.post("/sessions/{session_id}/message", response_model=MessageResponse)
def post_message(session_id: str, req: MessageRequest) -> MessageResponse:
    """Send a player response to continue the conversation."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.finished:
        raise HTTPException(status_code=409, detail="Session already finished")

    result = _agent.reply(session, req.message)
    return MessageResponse(result=result)


@app.get("/sessions/{session_id}", response_model=GenerationResult)
def get_session(session_id: str) -> GenerationResult:
    """Get the current state of a session."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.result:
        return GenerationResult(status="complete", spec=session.result)
    return GenerationResult(status="questions", question=None)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
