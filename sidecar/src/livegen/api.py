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
from livegen.dungeon_store import DungeonStore

app = FastAPI(title="LiveGen Sidecar", version="0.3.0")

_sessions: dict[str, Session] = {}
_agent = DungeonAgent(backend=create_backend())
_store = DungeonStore()


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

    # Auto-save completed dungeons
    if result.spec:
        stored = _store.save(result.spec)
        _sessions[session_id].stored_id = stored.id

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

    if result.spec:
        stored = _store.save(result.spec)
        session.stored_id = stored.id

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


class CompileRequest(BaseModel):
    session_id: str
    mods_path: str = ""  # If empty, auto-detect


@app.post("/compile")
def compile_dungeon(req: CompileRequest):
    """Compile a completed dungeon spec into a .o2r mod and install it."""
    session = _sessions.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.result:
        raise HTTPException(status_code=409, detail="No dungeon spec to compile")

    from livegen.compiler.scene_builder import build_dungeon_o2r

    # Auto-detect mods path
    mods_path = req.mods_path
    if not mods_path:
        import os
        # Try common SoH mod paths
        candidates = [
            os.path.expanduser("~/workspace/SoH/soh-source/build-cmake/soh/mods"),
            os.path.expanduser("~/Library/Application Support/com.shipofharkinian.soh/mods"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                mods_path = c
                break

    if not mods_path:
        raise HTTPException(status_code=500, detail="Could not find SoH mods folder")

    try:
        output_path = build_dungeon_o2r(session.result, Path(mods_path))
        return JSONResponse(content={
            "status": "compiled",
            "path": str(output_path),
            "dungeon_name": session.result.metadata.name,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compilation failed: {e}")


@app.get("/dungeons")
def list_dungeons():
    """List all saved dungeons."""
    dungeons = _store.list_all()
    active_id = _store.get_active_id()
    return JSONResponse(content={
        "dungeons": [d.to_dict() for d in dungeons],
        "active_id": active_id,
    })


@app.post("/dungeons/{dungeon_id}/activate")
def activate_dungeon(dungeon_id: str):
    """Set a dungeon as active and compile it."""
    dungeon = _store.get(dungeon_id)
    if not dungeon:
        raise HTTPException(status_code=404, detail="Dungeon not found")

    from livegen.compiler.scene_builder import build_dungeon_o2r
    from livegen.schema import DungeonSpec

    spec = DungeonSpec.model_validate(dungeon.spec)

    # Find mods path
    import os
    mods_path = None
    for c in [
        os.path.expanduser("~/workspace/SoH/soh-source/build-cmake/soh/mods"),
        os.path.expanduser("~/Library/Application Support/com.shipofharkinian.soh/mods"),
    ]:
        if os.path.isdir(c):
            mods_path = c
            break

    if not mods_path:
        raise HTTPException(status_code=500, detail="Mods folder not found")

    output = build_dungeon_o2r(spec, Path(mods_path))
    _store.set_active(dungeon_id)
    _store.mark_compiled(dungeon_id)

    return JSONResponse(content={
        "status": "activated",
        "dungeon_name": dungeon.name,
        "path": str(output),
        "message": "Restart SoH to enter this dungeon",
    })


@app.delete("/dungeons/{dungeon_id}")
def delete_dungeon(dungeon_id: str):
    if _store.delete(dungeon_id):
        return JSONResponse(content={"status": "deleted"})
    raise HTTPException(status_code=404, detail="Dungeon not found")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
