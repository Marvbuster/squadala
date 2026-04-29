"""LLM backend abstraction — supports Anthropic API and OpenAI-compatible local LLMs."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Normalized tool call from any LLM backend."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized LLM response."""

    tool_calls: list[ToolCall]
    text: str | None = None
    raw: Any = None


class LLMBackend(ABC):
    """Abstract base for LLM backends."""

    @abstractmethod
    def chat(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request and return normalized response."""

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, content: str, is_error: bool = False) -> dict:
        """Format a tool result message for the conversation history."""

    @abstractmethod
    def format_assistant_response(self, response: LLMResponse) -> dict:
        """Format the assistant response for the conversation history."""


class AnthropicBackend(LLMBackend):
    """Claude via Anthropic API."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250514", api_key: str | None = None):
        import anthropic

        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, *, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 4096) -> LLMResponse:
        # Anthropic uses input_schema for tools
        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=anthropic_tools,
        )

        tool_calls = []
        text = None
        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
            elif block.type == "text":
                text = block.text

        return LLMResponse(tool_calls=tool_calls, text=text, raw=response)

    def format_tool_result(self, tool_call_id: str, content: str, is_error: bool = False) -> dict:
        result: dict = {"type": "tool_result", "tool_use_id": tool_call_id, "content": content}
        if is_error:
            result["is_error"] = True
        return {"role": "user", "content": [result]}

    def format_assistant_response(self, response: LLMResponse) -> dict:
        return {"role": "assistant", "content": response.raw.content}


class OpenAICompatibleBackend(LLMBackend):
    """Local LLMs via OpenAI-compatible API (Ollama, LM Studio, vLLM, etc.)."""

    def __init__(
        self,
        model: str = "llama3",
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        from openai import OpenAI

        self.model = model
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, *, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 4096) -> LLMResponse:
        # Convert to OpenAI tool format
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        # Convert messages: Anthropic format → OpenAI format
        openai_messages = [{"role": "system", "content": system}]
        for msg in messages:
            openai_messages.append(self._convert_message(msg))

        kwargs = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": max_tokens,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
        response = self.client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        tool_calls = []
        text = choice.message.content or ""

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id or f"call_{len(tool_calls)}", name=tc.function.name, input=args))

            # If no text content but tool calls exist and we didn't ask for tools,
            # the model might have put the JSON in a tool call argument
            if not text and not openai_tools:
                # Extract text from tool call arguments (Gemma quirk)
                for tc in choice.message.tool_calls:
                    text = tc.function.arguments or ""
                    if text.strip().startswith("{"):
                        tool_calls = []  # These aren't real tool calls
                        break

        return LLMResponse(
            tool_calls=tool_calls,
            text=text,
            raw=response,
        )

    def format_tool_result(self, tool_call_id: str, content: str, is_error: bool = False) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }

    def format_assistant_response(self, response: LLMResponse) -> dict:
        choice = response.raw.choices[0]
        msg: dict = {"role": "assistant", "content": choice.message.content or ""}
        if choice.message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id or f"call_{i}",
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                }
                for i, tc in enumerate(choice.message.tool_calls)
            ]
        return msg

    def _convert_message(self, msg: dict) -> dict:
        """Convert Anthropic-style message to OpenAI-style."""
        role = msg["role"]
        content = msg["content"]

        # Simple string content
        if isinstance(content, str):
            return {"role": role, "content": content}

        # Tool result (Anthropic format: list with tool_result blocks)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    return {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block.get("content", ""),
                    }

        # Assistant with tool calls (Anthropic raw content)
        if role == "assistant" and hasattr(content, "__iter__"):
            # This is Anthropic's raw content blocks — skip for OpenAI
            return {"role": "assistant", "content": str(content)}

        return {"role": role, "content": str(content)}


def create_backend(provider: str | None = None, **kwargs) -> LLMBackend:
    """Factory function to create the appropriate LLM backend.

    Reads from LIVEGEN_LLM_PROVIDER env var if not specified.
    Supported: "anthropic", "openai", "ollama", "lmstudio"
    """
    provider = provider or os.environ.get("LIVEGEN_LLM_PROVIDER", "anthropic")

    if provider == "anthropic":
        return AnthropicBackend(
            model=kwargs.get("model", os.environ.get("LIVEGEN_MODEL", "claude-sonnet-4-5-20250514")),
            api_key=kwargs.get("api_key"),
        )
    elif provider in ("openai", "ollama"):
        return OpenAICompatibleBackend(
            model=kwargs.get("model", os.environ.get("LIVEGEN_MODEL", "llama3")),
            base_url=kwargs.get("base_url", os.environ.get("LIVEGEN_BASE_URL", "http://localhost:11434/v1")),
            api_key=kwargs.get("api_key", os.environ.get("LIVEGEN_API_KEY", "ollama")),
        )
    elif provider == "lmstudio":
        return OpenAICompatibleBackend(
            model=kwargs.get("model", os.environ.get("LIVEGEN_MODEL", "local-model")),
            base_url=kwargs.get("base_url", os.environ.get("LIVEGEN_BASE_URL", "http://localhost:1234/v1")),
            api_key=kwargs.get("api_key", os.environ.get("LIVEGEN_API_KEY", "lm-studio")),
        )
    else:
        msg = f"Unknown LLM provider: {provider}. Use 'anthropic', 'ollama', or 'lmstudio'."
        raise ValueError(msg)
