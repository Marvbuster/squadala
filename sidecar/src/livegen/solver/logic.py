"""Logic validator — checks if a dungeon is solvable (all keys reachable)."""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from livegen.schema import ChestContent, DoorType, DungeonSpec


@dataclass
class LogicResult:
    is_solvable: bool
    errors: list[str] = field(default_factory=list)
    reachable_rooms: list[str] = field(default_factory=list)
    unreachable_rooms: list[str] = field(default_factory=list)


def validate_logic(spec: DungeonSpec) -> LogicResult:
    """Check if the dungeon is solvable — all locked doors can be opened
    with available keys, and the boss room is reachable.

    Uses a BFS simulation: start at entrance, collect keys from reachable
    chests, unlock doors, repeat until no more progress.
    """
    errors: list[str] = []

    # Build room graph
    room_ids = {r.id for r in spec.rooms}
    entrance = spec.rooms[0].id

    # Map rooms to their chests
    room_chests: dict[str, list[str]] = {}
    for room in spec.rooms:
        room_chests[room.id] = [c.contents.value for c in room.chests]

    # Build adjacency with door types
    edges: list[tuple[str, str, str]] = []
    for conn in spec.connections:
        edges.append((conn.from_room, conn.to_room, conn.type.value))

    # BFS with key simulation
    small_keys = 0
    has_boss_key = False
    reachable: set[str] = set()
    collected_chests: set[str] = set()

    changed = True
    while changed:
        changed = False

        # BFS from entrance through unlockable doors
        queue = [entrance]
        visited: set[str] = set()

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            if current not in reachable:
                reachable.add(current)
                changed = True

            # Collect keys from this room
            for room in spec.rooms:
                if room.id != current:
                    continue
                for chest in room.chests:
                    chest_ref = f"{room.id}.{chest.id}"
                    if chest_ref in collected_chests:
                        continue
                    collected_chests.add(chest_ref)
                    if chest.contents == ChestContent.small_key:
                        small_keys += 1
                        changed = True
                    elif chest.contents == ChestContent.boss_key:
                        has_boss_key = True
                        changed = True

            # Try to traverse edges
            for from_r, to_r, door_type in edges:
                for src, dst in [(from_r, to_r), (to_r, from_r)]:
                    if src != current or dst in visited:
                        continue

                    if door_type == "open_door" or door_type == "one_way" or door_type == "puzzle_door":
                        queue.append(dst)
                    elif door_type == "small_key_door" and small_keys > 0:
                        small_keys -= 1
                        queue.append(dst)
                        # Mark this door as permanently unlocked
                        edges = [
                            (f, t, "open_door") if (f == from_r and t == to_r) else (f, t, dt)
                            for f, t, dt in edges
                        ]
                        changed = True
                    elif door_type == "boss_key_door" and has_boss_key:
                        queue.append(dst)

    unreachable = room_ids - reachable

    if unreachable:
        errors.append(f"Unreachable rooms: {sorted(unreachable)}")

    # Check boss room reachability
    if spec.logic.boss and spec.logic.boss.room not in reachable:
        errors.append(f"Boss room '{spec.logic.boss.room}' is not reachable")

    return LogicResult(
        is_solvable=len(errors) == 0,
        errors=errors,
        reachable_rooms=sorted(reachable),
        unreachable_rooms=sorted(unreachable),
    )
