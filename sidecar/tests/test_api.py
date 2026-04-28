"""E2E tests for the FastAPI endpoints with a mock Anthropic client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from livegen.api import app


def _make_mock_response(tool_name: str, tool_input: dict, tool_id: str = "toolu_test"):
    """Create a mock Anthropic API response with a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input

    response = MagicMock()
    response.content = [block]
    return response


def _make_text_response(text: str):
    """Create a mock Anthropic API response with just text."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.content = [block]
    return response


VALID_DUNGEON = {
    "metadata": {"name": "Test Dungeon", "theme": "ice", "difficulty": "easy"},
    "rooms": [
        {"id": "entrance", "template": "small_chamber_2exit", "actors": [], "chests": []},
        {
            "id": "boss_room",
            "template": "boss_arena",
            "actors": [{"type": "stalfos", "count": 1}],
            "chests": [],
        },
    ],
    "connections": [{"from": "entrance", "to": "boss_room", "type": "open_door"}],
    "logic": {"boss": {"type": "stalfos", "room": "boss_room"}},
}


@pytest.fixture
def client():
    from livegen.api import _sessions
    _sessions.clear()
    return TestClient(app)


class TestCreateSession:
    @patch("livegen.api._agent")
    def test_creates_session_with_question(self, mock_agent, client):
        from livegen.schema import GenerationResult, PlayerQuestion

        mock_agent.start.return_value = GenerationResult(
            status="questions",
            question=PlayerQuestion(
                question="What theme?",
                options=["fire", "ice", "shadow"],
            ),
        )
        resp = client.post("/sessions", json={"prompt": "Make a cool dungeon"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["result"]["status"] == "questions"
        assert data["result"]["question"]["question"] == "What theme?"

    @patch("livegen.api._agent")
    def test_creates_session_direct_submit(self, mock_agent, client):
        from livegen.schema import DungeonSpec, GenerationResult

        spec = DungeonSpec.model_validate(VALID_DUNGEON)
        mock_agent.start.return_value = GenerationResult(status="complete", spec=spec)

        resp = client.post("/sessions", json={"prompt": "Simple 2-room dungeon"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"] == "complete"
        assert data["result"]["spec"]["metadata"]["name"] == "Test Dungeon"


class TestPostMessage:
    @patch("livegen.api._agent")
    def test_reply_to_question(self, mock_agent, client):
        from livegen.schema import DungeonSpec, GenerationResult, PlayerQuestion

        # First call: agent asks a question
        mock_agent.start.return_value = GenerationResult(
            status="questions",
            question=PlayerQuestion(question="How many rooms?"),
        )
        resp = client.post("/sessions", json={"prompt": "Make a dungeon"})
        session_id = resp.json()["session_id"]

        # Second call: player answers, agent submits
        spec = DungeonSpec.model_validate(VALID_DUNGEON)
        mock_agent.reply.return_value = GenerationResult(status="complete", spec=spec)

        resp = client.post(
            f"/sessions/{session_id}/message",
            json={"message": "5 rooms"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "complete"

    def test_unknown_session(self, client):
        resp = client.post(
            "/sessions/nonexistent/message",
            json={"message": "hello"},
        )
        assert resp.status_code == 404


class TestGetSession:
    @patch("livegen.api._agent")
    def test_get_completed_session(self, mock_agent, client):
        from livegen.schema import DungeonSpec, GenerationResult

        spec = DungeonSpec.model_validate(VALID_DUNGEON)
        mock_agent.start.return_value = GenerationResult(status="complete", spec=spec)

        resp = client.post("/sessions", json={"prompt": "Make a dungeon"})
        session_id = resp.json()["session_id"]

        # Mark session as finished (the mock doesn't do this automatically)
        from livegen.api import _sessions
        _sessions[session_id].finished = True
        _sessions[session_id].result = spec

        resp = client.get(f"/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    def test_get_unknown_session(self, client):
        resp = client.get("/sessions/nonexistent")
        assert resp.status_code == 404


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
