import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from collision_manager import CollisionManager


BASE_DIR = Path(__file__).resolve().parent
LEVELS_DIR = BASE_DIR / "levels"
DEFAULT_COMBAT_LEVEL = "combat_default"


@dataclass
class Level:
    name: str
    background: str
    size: tuple
    player_spawn: tuple
    colliders: list = field(default_factory=list)
    collider_metadata: list = field(default_factory=list)
    triggers: list = field(default_factory=list)
    enemy_spawns: list = field(default_factory=list)
    interactables: list = field(default_factory=list)
    doors: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        colliders = []
        collider_metadata = []
        for index, item in enumerate(data.get("colliders", [])):
            rect = pygame.Rect(item["x"], item["y"], item["w"], item["h"])
            colliders.append(rect)
            collider_metadata.append(
                {
                    "name": item.get("name", f"collider_{index}"),
                    "type": item.get("type", "solid"),
                    "enabled": item.get("enabled", True),
                }
            )

        return cls(
            name=data.get("name", "unnamed_level"),
            background=data.get("background", ""),
            size=tuple(data.get("size", (1024, 768))),
            player_spawn=tuple(data.get("player_spawn", (512, 384))),
            colliders=colliders,
            collider_metadata=collider_metadata,
            triggers=data.get("triggers", []),
            enemy_spawns=[tuple(spawn) for spawn in data.get("enemy_spawns", [])],
            interactables=data.get("interactables", []),
            doors=data.get("doors", []),
        )

    def create_collision_manager(self):
        return CollisionManager(self.colliders, self.collider_metadata)


def resolve_level_path(level_name_or_path):
    path = Path(level_name_or_path)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    if path.is_absolute():
        return path
    if path.parent == Path("."):
        return LEVELS_DIR / path
    return BASE_DIR / path


def load_level(level_name_or_path, fallback_size=(1024, 768)):
    path = resolve_level_path(level_name_or_path)
    if not path.exists():
        return build_default_combat_level(fallback_size)

    with path.open("r", encoding="utf-8") as f:
        return Level.from_dict(json.load(f))


def load_combat_level(room_id=None, fallback_size=(1024, 768)):
    if room_id:
        room_path = resolve_level_path(room_id)
        if room_path.exists():
            return load_level(room_path, fallback_size)
    return load_level(DEFAULT_COMBAT_LEVEL, fallback_size)


def build_default_combat_level(size=(1024, 768)):
    width, height = size
    data = {
        "name": DEFAULT_COMBAT_LEVEL,
        "background": "assets/floor_tile.png",
        "size": [width, height],
        "player_spawn": [width // 2, height // 2],
        "enemy_spawns": [
            [width // 2, 120],
            [width // 2, height - 120],
            [120, height // 2],
            [width - 120, height // 2],
        ],
        "colliders": [
            {"name": "top_boundary", "type": "boundary", "x": 0, "y": -32, "w": width, "h": 32},
            {"name": "bottom_boundary", "type": "boundary", "x": 0, "y": height, "w": width, "h": 32},
            {"name": "left_boundary", "type": "boundary", "x": -32, "y": 0, "w": 32, "h": height},
            {"name": "right_boundary", "type": "boundary", "x": width, "y": 0, "w": 32, "h": height},
        ],
        "triggers": [],
    }
    return Level.from_dict(data)
