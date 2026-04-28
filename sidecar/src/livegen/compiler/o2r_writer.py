"""Compile a DungeonSpec into a SoH-compatible .o2r scene file.

Strategy: Copy existing room data from the base game's .o2r and assemble
them into a new scene with custom transition actors (doors) connecting
the rooms according to the DungeonSpec graph.
"""

from __future__ import annotations

import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

from livegen.schema import DungeonSpec


@dataclass
class Vec3s:
    x: int
    y: int
    z: int

    def pack(self) -> bytes:
        return struct.pack("<hhh", self.x, self.y, self.z)


@dataclass
class TransitionActor:
    """A door connecting two rooms."""

    front_room: int
    back_room: int
    actor_id: int  # Door actor type
    pos: Vec3s
    rot_y: int
    params: int

    def pack(self) -> bytes:
        return struct.pack(
            "<bbbbhhhhhH",
            self.front_room,
            0,  # front effects
            self.back_room,
            0,  # back effects
            self.actor_id,
            self.pos.x,
            self.pos.y,
            self.pos.z,
            self.rot_y,
            self.params,
        )


@dataclass
class SceneCompiler:
    """Compiles DungeonSpec + room templates into a .o2r file."""

    base_o2r_path: Path
    output_dir: Path

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compile(self, spec: DungeonSpec, scene_name: str = "livegen_dungeon") -> Path:
        """Compile a DungeonSpec into a .o2r file.

        Returns path to the generated .o2r file.
        """
        output_path = self.output_dir / f"{scene_name}.o2r"

        with zipfile.ZipFile(str(self.base_o2r_path), "r") as base_z:
            with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_STORED) as out_z:
                self._write_scene(out_z, base_z, spec, scene_name)

        return output_path

    def _write_scene(
        self,
        out_z: zipfile.ZipFile,
        base_z: zipfile.ZipFile,
        spec: DungeonSpec,
        scene_name: str,
    ) -> None:
        """Write all scene data to the output archive."""
        scene_path = f"scenes/shared/{scene_name}_scene"

        # Map spec rooms to source room templates
        room_mapping = self._map_rooms(spec)

        # Copy room data from source templates
        for room_idx, (source_scene, source_room) in enumerate(room_mapping):
            self._copy_room(out_z, base_z, source_scene, source_room, scene_path, scene_name, room_idx)

        # Build transition actor list from connections
        transitions = self._build_transitions(spec)

        # Write scene header with commands
        scene_header = self._build_scene_header(
            scene_name=scene_name,
            scene_path=scene_path,
            num_rooms=len(room_mapping),
            transitions=transitions,
            spec=spec,
        )
        out_z.writestr(f"{scene_path}/{scene_name}_scene", scene_header)

        # Copy collision from first room's source dungeon
        if room_mapping:
            source_scene = room_mapping[0][0]
            self._copy_collision(out_z, base_z, source_scene, scene_path, scene_name)

    def _map_rooms(self, spec: DungeonSpec) -> list[tuple[str, int]]:
        """Map DungeonSpec rooms to source (scene, room_id) pairs.

        For now, uses a simple mapping based on template names.
        The template field in each Room should reference a scene_room format
        like 'ydan_scene_0' or just a template type like 'small_chamber_2exit'.
        """
        mapping = []
        for room in spec.rooms:
            template = room.template
            if "_scene_" in template:
                # Direct reference: 'ydan_scene_3'
                parts = template.rsplit("_", 1)
                scene = parts[0]
                room_id = int(parts[1])
            else:
                # Template type — use defaults for now
                defaults = {
                    "small_chamber_2exit": ("ydan_scene", 4),
                    "small_chamber_3exit": ("ydan_scene", 7),
                    "corridor_straight": ("ydan_scene", 1),
                    "corridor_l_bend": ("ddan_scene", 5),
                    "large_hall_4exit": ("ydan_scene", 3),
                    "block_push_room": ("Bmori1_scene", 8),
                    "pit_room": ("ddan_scene", 6),
                    "lava_bridge_room": ("HIDAN_scene", 5),
                    "water_room": ("MIZUsin_scene", 5),
                    "boss_arena": ("ydan_scene", 11),
                }
                scene, room_id = defaults.get(template, ("ydan_scene", 0))
            mapping.append((scene, room_id))
        return mapping

    def _copy_room(
        self,
        out_z: zipfile.ZipFile,
        base_z: zipfile.ZipFile,
        source_scene: str,
        source_room: int,
        dest_path: str,
        dest_scene: str,
        dest_room: int,
    ) -> None:
        """Copy all room data (DL, Vtx, Tex, etc.) from source to destination."""
        # Find source entries
        source_prefix = f"scenes/nonmq/{source_scene}/{source_scene.replace('_scene', '')}_room_{source_room}"
        dest_prefix = f"{dest_path}/{dest_scene}_room_{dest_room}"

        for name in base_z.namelist():
            if not name.startswith(source_prefix.rsplit("_room_", 1)[0]):
                continue
            entry_name = name.split("/")[-1]
            src_room_prefix = f"{source_scene.replace('_scene', '')}_room_{source_room}"
            if not entry_name.startswith(src_room_prefix):
                continue

            # Rename to destination
            suffix = entry_name[len(src_room_prefix):]
            dest_name = f"{dest_path}/{dest_scene}_room_{dest_room}{suffix}"

            data = base_z.read(name)
            out_z.writestr(dest_name, data)

    def _copy_collision(
        self,
        out_z: zipfile.ZipFile,
        base_z: zipfile.ZipFile,
        source_scene: str,
        dest_path: str,
        dest_scene: str,
    ) -> None:
        """Copy collision header from source scene."""
        for name in base_z.namelist():
            if source_scene in name and "CollisionHeader" in name:
                data = base_z.read(name)
                suffix = name.split("/")[-1].split("CollisionHeader")[1]
                out_z.writestr(
                    f"{dest_path}/{dest_scene}_sceneCollisionHeader{suffix}",
                    data,
                )
                break

    def _build_transitions(self, spec: DungeonSpec) -> list[TransitionActor]:
        """Build transition actors from DungeonSpec connections."""
        transitions = []
        room_id_map = {room.id: idx for idx, room in enumerate(spec.rooms)}

        # Standard door actor ID
        DOOR_SHUTTER = 0x0009  # Standard dungeon door
        DOOR_LOCKED = 0x0015  # Locked door (requires small key)
        BOSS_DOOR = 0x002E  # Boss door

        for conn in spec.connections:
            front = room_id_map.get(conn.from_room, 0)
            back = room_id_map.get(conn.to_room, 0)

            # Choose door type based on connection type
            if conn.type.value == "small_key_door":
                actor_id = DOOR_LOCKED
            elif conn.type.value == "boss_key_door":
                actor_id = BOSS_DOOR
            else:
                actor_id = DOOR_SHUTTER

            transitions.append(
                TransitionActor(
                    front_room=front,
                    back_room=back,
                    actor_id=actor_id,
                    pos=Vec3s(0, 0, 0),  # Will need real positions from room geometry
                    rot_y=0,
                    params=0,
                )
            )
        return transitions

    def _build_scene_header(
        self,
        scene_name: str,
        scene_path: str,
        num_rooms: int,
        transitions: list[TransitionActor],
        spec: DungeonSpec,
    ) -> bytes:
        """Build the binary scene header with all scene commands."""
        # MORO header (0x40 bytes)
        header = bytearray(0x40)
        header[4:8] = b"MORO"
        struct.pack_into("<I", header, 0x08, 0xDEADBEEF)
        struct.pack_into("<I", header, 0x0C, 0xDEADBEEF)

        # Commands will be serialized after the header
        commands = bytearray()

        # Count commands (we'll fill this in later)
        cmd_count = 0

        # Command 4: RoomList
        commands += struct.pack("<I", 4)  # cmd_id
        commands += struct.pack("<I", num_rooms)
        for i in range(num_rooms):
            room_path = f"{scene_path}/{scene_name}_room_{i}"
            path_bytes = room_path.encode("utf-8") + b"\x00"
            commands += struct.pack("<I", len(path_bytes))
            commands += path_bytes
            commands += struct.pack("<II", 0, 0)  # vrom start/end (unused in o2r)
        cmd_count += 1

        # Command 14: TransitionActorList
        if transitions:
            commands += struct.pack("<I", 14)
            commands += struct.pack("<I", len(transitions))
            for t in transitions:
                commands += t.pack()
            cmd_count += 1

        # Command 20: EndMarker
        commands += struct.pack("<I", 20)
        cmd_count += 1

        # Write command count
        header += struct.pack("<I", cmd_count)
        return bytes(header) + bytes(commands)
