"""Tests for the DungeonSpec → custom-geometry .o2r bridge.

Smoke-tests the M6 closure: an abstract spec with abstract actor entries
should yield concrete placed actors and a complete .o2r archive.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from livegen.compiler import box_room_dungeon as bridge
from livegen.schema import (
    ActorType,
    Chest,
    ChestContent,
    Connection,
    DoorType,
    DungeonSpec,
    Logic,
    Metadata,
    Room,
)


def _minimal_spec(actors: list, chests: list) -> DungeonSpec:
    return DungeonSpec(
        metadata=Metadata(name="Bridge Test"),
        rooms=[
            Room(id="box_room", template="small_chamber_2exit",
                 actors=actors, chests=chests),
            Room(id="filler", template="boss_arena", actors=[], chests=[]),
        ],
        connections=[Connection.model_validate({
            "from": "box_room", "to": "filler", "type": "open_door",
        })],
        logic=Logic(),
    )


# ---------------------------------------------------------------------------
# Spec → placed-actor list
# ---------------------------------------------------------------------------

def test_keese_count_expands_to_circular_placement() -> None:
    spec = _minimal_spec(
        actors=[{"type": "keese", "count": 4}],
        chests=[],
    )
    placed = bridge.spec_to_actors(spec.rooms[0])
    assert len(placed) == 4
    assert all(p["name"] == "keese" for p in placed)
    # All on the floor at y = -100
    assert all(p["y"] == bridge.ROOM_FLOOR_Y for p in placed)
    # Spread on a circle: distinct (x, z)
    coords = {(p["x"], p["z"]) for p in placed}
    assert len(coords) == 4


def test_all_schema_actors_round_trip() -> None:
    # Every ActorType in the schema must round-trip through the bridge into
    # a known ACTOR_LIBRARY entry. Catches regressions when a new ActorType
    # is added without a corresponding library mapping.
    for actor_type in ActorType:
        assert actor_type.value in bridge.ACTOR_TYPE_TO_LIBRARY, (
            f"ActorType.{actor_type.name} has no ACTOR_LIBRARY mapping"
        )


def test_chest_contents_map_to_correct_gi() -> None:
    spec = _minimal_spec(
        actors=[],
        chests=[
            {"id": "c1", "contents": "piece_of_heart"},
            {"id": "c2", "contents": "livegen_mario"},
            {"id": "c3", "contents": "small_key"},
        ],
    )
    placed = bridge.spec_to_actors(spec.rooms[0])
    chests = [p for p in placed if p["name"] == "chest"]
    assert len(chests) == 3
    # Decode the GI bits (bits 5-11 of params)
    gis = [(p["params"] >> 5) & 0x7F for p in chests]
    assert gis == [
        bridge.CHEST_CONTENT_TO_GI[ChestContent.piece_of_heart.value],
        bridge.CHEST_CONTENT_TO_GI[ChestContent.livegen_mario.value],
        bridge.CHEST_CONTENT_TO_GI[ChestContent.small_key.value],
    ]


def test_livegen_mario_resolves_to_custom_gi_id() -> None:
    """The GI byte 0x7E is what soh-fork's LiveGenItemRegistry hooks on."""
    assert bridge.CHEST_CONTENT_TO_GI["livegen_mario"] == 0x7E


# ---------------------------------------------------------------------------
# End-to-end .o2r build
# ---------------------------------------------------------------------------

def _trimesh_available() -> bool:
    try:
        import trimesh  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "tooling" / "assets" / "3d" / "pizza.glb").exists(),
    reason="pizza.glb asset missing",
)
@pytest.mark.skipif(not _trimesh_available(), reason="trimesh not installed in this env")
def test_build_dungeon_o2r_writes_complete_archive(tmp_path: Path) -> None:
    spec = _minimal_spec(
        actors=[{"type": "keese", "count": 2}],
        chests=[{"id": "loot", "contents": "livegen_mario"}],
    )
    output = tmp_path / "dungeon.o2r"
    bridge.build_dungeon_o2r(spec, output)

    assert output.exists()
    with zipfile.ZipFile(output) as z:
        names = set(z.namelist())

    target = "scenes/nonmq/ydan_scene"
    expected = {
        f"{target}/squadala_box_DL",
        f"{target}/squadala_box_Vtx",
        f"{target}/squadala_mario_DL",
        f"{target}/squadala_mario_Vtx",
        f"{target}/squadala_pizza_DL",
        f"{target}/squadala_pizza_Vtx",
        f"{target}/ydan_room_0",
        f"{target}/ydan_sceneCollisionHeader_00B610",
        f"{target}/ydan_scene",
    }
    assert expected <= names
