"""Layout solver — places rooms on a grid and validates spatial consistency."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import networkx as nx

from livegen.schema import DungeonSpec


@dataclass
class RoomPlacement:
    room_id: str
    grid_x: int
    grid_y: int


@dataclass
class LayoutResult:
    placements: list[RoomPlacement]
    graph: nx.Graph
    is_valid: bool
    errors: list[str] = field(default_factory=list)


def solve_layout(spec: DungeonSpec) -> LayoutResult:
    """Place dungeon rooms on a 2D grid ensuring no overlaps and all
    connections are between adjacent cells.

    Uses a simple BFS placement starting from the first room.
    """
    graph = nx.Graph()
    for room in spec.rooms:
        graph.add_node(room.id)
    for conn in spec.connections:
        graph.add_edge(conn.from_room, conn.to_room, type=conn.type.value)

    # BFS placement from first room
    placements: dict[str, tuple[int, int]] = {}
    occupied: set[tuple[int, int]] = set()
    errors: list[str] = []

    # Direction vectors for adjacent cells
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

    start = spec.rooms[0].id
    placements[start] = (0, 0)
    occupied.add((0, 0))

    queue = [start]
    visited = {start}

    while queue:
        current = queue.pop(0)
        cx, cy = placements[current]

        neighbors = list(graph.neighbors(current))
        random.shuffle(neighbors)
        dir_idx = 0

        for neighbor in neighbors:
            if neighbor in visited:
                continue
            visited.add(neighbor)

            # Find an unoccupied adjacent cell
            placed = False
            for attempt in range(len(directions)):
                d = directions[(dir_idx + attempt) % len(directions)]
                nx_, ny = cx + d[0], cy + d[1]
                if (nx_, ny) not in occupied:
                    placements[neighbor] = (nx_, ny)
                    occupied.add((nx_, ny))
                    queue.append(neighbor)
                    placed = True
                    dir_idx = (dir_idx + attempt + 1) % len(directions)
                    break

            if not placed:
                # Try expanding further out
                for dist in range(2, 10):
                    for d in directions:
                        nx_, ny = cx + d[0] * dist, cy + d[1] * dist
                        if (nx_, ny) not in occupied:
                            placements[neighbor] = (nx_, ny)
                            occupied.add((nx_, ny))
                            queue.append(neighbor)
                            placed = True
                            break
                    if placed:
                        break

                if not placed:
                    errors.append(f"Could not place room '{neighbor}' adjacent to '{current}'")

    # Check all rooms are placed
    for room in spec.rooms:
        if room.id not in placements:
            errors.append(f"Room '{room.id}' was not placed (disconnected graph?)")

    result_placements = [
        RoomPlacement(room_id=rid, grid_x=pos[0], grid_y=pos[1])
        for rid, pos in placements.items()
    ]

    return LayoutResult(
        placements=result_placements,
        graph=graph,
        is_valid=len(errors) == 0,
        errors=errors,
    )
