"""LLM agent that generates dungeon specs — structured JSON output, no tool-use."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from livegen.builder import DungeonBuilder, VALID_TEMPLATES, VALID_ENEMIES, VALID_DOOR_TYPES, VALID_THEMES
from livegen.llm import LLMBackend, create_backend
from livegen.schema import DungeonSpec, GenerationResult, PlayerQuestion

logger = logging.getLogger(__name__)

SCHEMA_SHAPE = """\
{
  "dungeon_name": "string (max 80 chars)",
  "theme": "forest|fire|water|shadow|spirit|ice|stone|generic",
  "difficulty": "easy|medium|hard",
  "rooms": [
    {
      "name": "string (lowercase, underscores, e.g. 'entrance_hall')",
      "template": "small_chamber_2exit|small_chamber_3exit|corridor_straight|corridor_l_bend|large_hall_4exit|block_push_room|pit_room|lava_bridge_room|water_room|boss_arena",
      "enemies": [{"type": "keese|skulltula|stalfos|lizalfos|wolfos|white_wolfos|freezard|iron_knuckle|dinolfos|gibdo|redead|poe|floormaster|wallmaster|armos|beamos|like_like|bubble|torch_slug|dodongo|tektite", "count": 1}],
      "chests": ["small_key|boss_key|map|compass|arrows_10|bombs_5|rupees_20|recovery_heart|piece_of_heart"]
    }
  ],
  "connections": [
    {"from": "room_name_a", "to": "room_name_b", "door_type": "open_door|small_key_door|boss_key_door|puzzle_door|one_way"}
  ],
  "boss": {"room": "room_name", "type": "enemy_type"}
}"""

SYSTEM_PROMPT = """\
You design Zelda OoT dungeons. Reply with ONLY a JSON object matching this schema. No text, no markdown fences.

{schema}

Templates: small_chamber_2exit, corridor_straight, large_hall_4exit, boss_arena, block_push_room, water_room, pit_room
Enemies: keese, stalfos, lizalfos, wolfos, freezard, iron_knuckle, redead, poe, gibdo
Door types: open_door, small_key_door, boss_key_door

Keep it short: 2-8 rooms, lowercase names with underscores."""


@dataclass
class Session:
    session_id: str
    messages: list[dict] = field(default_factory=list)
    finished: bool = False
    result: DungeonSpec | None = None
    stored_id: str | None = None


class DungeonAgent:
    """Generates dungeons via structured JSON output — no tool-use needed."""

    def __init__(self, backend: LLMBackend | None = None) -> None:
        self.backend = backend or create_backend()

    def start(self, session: Session, player_prompt: str) -> GenerationResult:
        session.messages.append({"role": "user", "content": player_prompt})
        return self._generate(session)

    def reply(self, session: Session, player_answer: str) -> GenerationResult:
        if session.finished:
            return GenerationResult(status="error", error="Session already finished.")
        session.messages.append({"role": "user", "content": player_answer})
        return self._generate(session)

    def _generate(self, session: Session, retry: bool = False) -> GenerationResult:
        system = SYSTEM_PROMPT.format(schema=SCHEMA_SHAPE)
        if retry:
            system += "\n\nLetzter Versuch war ungültig. Antworte JETZT mit reinem, gültigem JSON."

        # Use raw chat — no tools, just text completion
        response = self.backend.chat(
            system=system,
            messages=session.messages,
            tools=[],  # No tools!
            max_tokens=16000,  # Gemma 4 reasoning uses many tokens internally
        )

        raw_text = response.text or ""
        logger.info("LLM response length=%d, starts=%s", len(raw_text), repr(raw_text[:100]))
        session.messages.append({"role": "assistant", "content": raw_text})

        # Extract JSON from response
        parsed = self._extract_and_validate(raw_text)

        if isinstance(parsed, DungeonSpec):
            session.finished = True
            session.result = parsed
            return GenerationResult(status="complete", spec=parsed)

        if not retry:
            # One retry with explicit instruction
            logger.warning("First attempt failed: %s — retrying", parsed)
            session.messages.append({
                "role": "user",
                "content": f"That was not valid JSON. Error: {parsed}\nPlease respond with ONLY the JSON object, nothing else.",
            })
            return self._generate(session, retry=True)

        # Both attempts failed
        return GenerationResult(status="error", error=f"Could not parse dungeon: {parsed}")

    def _extract_and_validate(self, raw: str) -> DungeonSpec | str:
        """Extract JSON from LLM text, normalize, and validate."""
        # Strip code fences
        candidate = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", candidate)
        if fence_match:
            candidate = fence_match.group(1).strip()

        # Find first JSON object
        if not candidate.startswith("{"):
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end > start:
                candidate = candidate[start:end + 1]
            else:
                return "No JSON object found in response"

        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as e:
            return f"JSON parse error: {e}"

        # Unwrap if nested under a key like "dungeon"
        if "dungeon" in data and isinstance(data["dungeon"], dict):
            data = data["dungeon"]

        # Normalize to DungeonSpec format
        try:
            spec_data = self._normalize(data)
            spec = DungeonSpec.model_validate(spec_data)
            return spec
        except Exception as e:
            return f"Validation error: {e}"

    @staticmethod
    def _normalize(raw: dict) -> dict:
        """Convert the simple LLM schema to our DungeonSpec format."""
        VALID_DOOR_SET = {"open_door", "small_key_door", "boss_key_door", "puzzle_door", "one_way"}

        # Metadata
        metadata = {
            "name": str(raw.get("dungeon_name", raw.get("name", "Generated Dungeon")))[:80],
            "theme": raw.get("theme", "generic"),
            "difficulty": raw.get("difficulty", "medium"),
        }

        # Rooms
        rooms = []
        room_id_map = {}  # name -> sanitized id
        for i, room in enumerate(raw.get("rooms", [])):
            name = str(room.get("name", f"room_{i}")).lower().replace(" ", "_").replace("-", "_")
            rid = re.sub(r"[^a-z0-9_]", "", name)
            if not rid or not rid[0].isalpha():
                rid = f"room_{rid}" if rid else f"room_{i}"
            room_id_map[name] = rid
            room_id_map[str(i)] = rid

            actors = []
            for enemy in room.get("enemies", room.get("actors", [])):
                if isinstance(enemy, dict):
                    etype = enemy.get("type", "keese")
                    if etype in VALID_ENEMIES:
                        actors.append({"type": etype, "count": min(max(enemy.get("count", 1), 1), 10)})

            chests = []
            for j, chest in enumerate(room.get("chests", [])):
                if isinstance(chest, str) and chest in VALID_CHEST_CONTENTS:
                    chests.append({"id": f"c{i}_{j}", "contents": chest})
                elif isinstance(chest, dict):
                    contents = chest.get("contents", chest.get("item", "rupees_20"))
                    if contents in VALID_CHEST_CONTENTS:
                        chests.append({"id": f"c{i}_{j}", "contents": contents})

            template = room.get("template", "small_chamber_2exit")
            if template not in VALID_TEMPLATES:
                template = "small_chamber_2exit"

            rooms.append({"id": rid, "template": template, "actors": actors, "chests": chests})

        def _resolve(ref: str) -> str:
            ref = re.sub(r"[^a-z0-9_]", "", str(ref).lower().replace(" ", "_").replace("-", "_"))
            if ref in room_id_map:
                return room_id_map[ref]
            if not ref or not ref[0].isalpha():
                ref = f"room_{ref}" if ref else "room_0"
            return ref

        # Connections
        connections = []
        for conn in raw.get("connections", []):
            fr = conn.get("from", conn.get("from_room", conn.get("room_a", conn.get("source", ""))))
            to = conn.get("to", conn.get("to_room", conn.get("room_b", conn.get("target", ""))))
            dtype = conn.get("door_type", conn.get("type", "open_door"))
            if dtype not in VALID_DOOR_SET:
                dtype = "open_door"
            connections.append({"from": _resolve(str(fr)), "to": _resolve(str(to)), "type": dtype})

        # Auto-fix keys
        key_doors = sum(1 for c in connections if c["type"] == "small_key_door")
        key_chests = sum(1 for r in rooms for c in r["chests"] if c["contents"] == "small_key")
        if key_doors > key_chests and rooms:
            for r in rooms:
                if r["template"] != "boss_arena":
                    for k in range(key_doors - key_chests):
                        r["chests"].append({"id": f"auto_key_{k}", "contents": "small_key"})
                    break

        boss_doors = sum(1 for c in connections if c["type"] == "boss_key_door")
        boss_chests = sum(1 for r in rooms for c in r["chests"] if c["contents"] == "boss_key")
        if boss_doors > 0 and boss_chests == 0 and rooms:
            for r in rooms:
                if r["template"] != "boss_arena":
                    r["chests"].append({"id": "auto_boss_key", "contents": "boss_key"})
                    break

        # Logic
        logic = {}
        boss = raw.get("boss")
        if isinstance(boss, dict):
            btype = boss.get("type", "stalfos")
            broom = _resolve(str(boss.get("room", "")))
            if btype in VALID_ENEMIES:
                logic["boss"] = {"type": btype, "room": broom}

        return {"metadata": metadata, "rooms": rooms, "connections": connections, "logic": logic}


# Re-export for imports
from livegen.schema import ChestContent as _CC
VALID_CHEST_CONTENTS = [c.value for c in _CC]
