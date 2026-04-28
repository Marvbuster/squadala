"""LLM agent that generates dungeon specs via tool-use conversation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from livegen.llm import LLMBackend, ToolCall, create_backend
from livegen.schema import DungeonSpec, GenerationResult, PlayerQuestion

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 3

SYSTEM_PROMPT = """\
You are a dungeon architect for The Legend of Zelda: Ocarina of Time.
The player will describe a dungeon they want. You may ask up to {max_questions} \
clarifying questions using the ask_player tool, then you MUST call submit_dungeon \
with a complete dungeon specification.

Rules:
- Every dungeon needs at least an entrance room and a boss room.
- The number of small_key chests must be >= the number of small_key_door connections.
- If there is a boss, there should be a boss_key_door before the boss room \
and a boss_key chest somewhere reachable without crossing that door.
- Room templates available: {templates}
- Keep dungeons between 3-8 rooms for now.
- Use the exact JSON schema expected by submit_dungeon — no extra fields.
"""

AVAILABLE_TEMPLATES = [
    "small_chamber_2exit",
    "small_chamber_3exit",
    "corridor_straight",
    "corridor_l_bend",
    "large_hall_4exit",
    "block_push_room",
    "pit_room",
    "lava_bridge_room",
    "water_room",
    "boss_arena",
]

TOOLS = [
    {
        "name": "ask_player",
        "description": (
            "Ask the player a clarifying question about the dungeon they want. "
            "You may call this at most {max_questions} times before you must submit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the player.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for the player.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "submit_dungeon",
        "description": "Submit the final dungeon specification. Call this exactly once.",
        "input_schema": DungeonSpec.model_json_schema(),
    },
]


@dataclass
class Session:
    """Tracks a single dungeon generation conversation."""

    session_id: str
    messages: list[dict] = field(default_factory=list)
    questions_asked: int = 0
    finished: bool = False
    result: DungeonSpec | None = None

    def _system_prompt(self) -> str:
        remaining = MAX_QUESTIONS - self.questions_asked
        return SYSTEM_PROMPT.format(
            max_questions=remaining,
            templates=", ".join(AVAILABLE_TEMPLATES),
        )


class DungeonAgent:
    """Drives the LLM tool-use loop for dungeon generation.

    Supports any backend: Anthropic Claude, Ollama, LM Studio, or any
    OpenAI-compatible API.
    """

    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend = backend or create_backend()

    def start(self, session: Session, player_prompt: str) -> GenerationResult:
        """Begin a new generation session with the player's initial prompt."""
        session.messages.append({"role": "user", "content": player_prompt})
        return self._run_turn(session)

    def reply(self, session: Session, player_answer: str) -> GenerationResult:
        """Continue the conversation with a player's answer to a question."""
        if session.finished:
            return GenerationResult(
                status="error",
                error="Session is already finished.",
            )
        session.messages.append({"role": "user", "content": player_answer})
        return self._run_turn(session)

    def _run_turn(self, session: Session) -> GenerationResult:
        """Execute one LLM turn, processing any tool calls."""
        tools = self._build_tools(session)

        response = self.backend.chat(
            system=session._system_prompt(),
            messages=session.messages,
            tools=tools,
        )

        # Store assistant response
        session.messages.append(self.backend.format_assistant_response(response))

        # Process tool calls
        for tc in response.tool_calls:
            if tc.name == "ask_player":
                return self._handle_ask(session, tc)
            if tc.name == "submit_dungeon":
                return self._handle_submit(session, tc)

        # No tool call — force the model to use a tool
        if not session.finished:
            session.messages.append({
                "role": "user",
                "content": (
                    "Please use either ask_player or submit_dungeon. "
                    "You must produce a dungeon spec."
                ),
            })
            return self._run_turn(session)

        return GenerationResult(status="error", error="Unexpected state")

    def _handle_ask(self, session: Session, tc: ToolCall) -> GenerationResult:
        """Process an ask_player tool call."""
        session.questions_asked += 1
        question = PlayerQuestion(
            question=tc.input["question"],
            options=tc.input.get("options"),
        )
        session.messages.append(
            self.backend.format_tool_result(
                tc.id, "Question delivered to player. Waiting for response."
            )
        )
        return GenerationResult(status="questions", question=question)

    def _handle_submit(self, session: Session, tc: ToolCall) -> GenerationResult:
        """Validate and accept a dungeon submission."""
        try:
            spec = DungeonSpec.model_validate(tc.input)
        except Exception as e:
            error_msg = f"Invalid dungeon spec: {e}"
            logger.warning("LLM produced invalid spec: %s", e)
            session.messages.append(
                self.backend.format_tool_result(tc.id, error_msg, is_error=True)
            )
            return self._run_turn(session)

        session.finished = True
        session.result = spec
        session.messages.append(
            self.backend.format_tool_result(tc.id, "Dungeon accepted! Compiling scene...")
        )
        return GenerationResult(status="complete", spec=spec)

    def _build_tools(self, session: Session) -> list[dict]:
        """Build the tool list, removing ask_player if quota exhausted."""
        tools = []
        if session.questions_asked < MAX_QUESTIONS:
            tools.append(TOOLS[0])
        tools.append(TOOLS[1])
        return tools
