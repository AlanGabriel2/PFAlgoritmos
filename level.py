import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from collision_manager import CollisionManager


BASE_DIR = Path(__file__).resolve().parent
LEVELS_DIR = BASE_DIR / "levels"
DEFAULT_COMBAT_LEVEL = "combat_default"
BACKGROUND_DIR = BASE_DIR / "assets" / "images" / "backgrounds"
DEFAULT_HAZARD_DAMAGE = 8
DEFAULT_HAZARD_DAMAGE_COOLDOWN = 45


def resolve_asset_path(path_value):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def get_image_size(path_value, fallback_size=(1280, 720)):
    try:
        image = pygame.image.load(str(resolve_asset_path(path_value)))
        return image.get_size()
    except Exception:
        return tuple(fallback_size)


def level_key_from_room_id(room_id):
    if not room_id:
        return None
    if isinstance(room_id, int):
        return f"s{room_id}"

    text = str(room_id)
    direct = text.lower()
    if re.fullmatch(r"s\d+", direct):
        return direct

    match = re.search(r"TIP(\d{2})", text.upper())
    if match:
        return f"s{int(match.group(1))}"
    return None


@dataclass
class Level:
    name: str
    background: str
    size: tuple
    player_spawn: tuple
    colliders: list = field(default_factory=list)
    collider_metadata: list = field(default_factory=list)
    hazard_zones: list = field(default_factory=list)
    hazard_metadata: list = field(default_factory=list)
    triggers: list = field(default_factory=list)
    enemy_spawns: list = field(default_factory=list)
    interactables: list = field(default_factory=list)
    doors: list = field(default_factory=list)
    walkable_zones: list = field(default_factory=list)
    walkable_metadata: list = field(default_factory=list)
    character_scale: float = 1.0
    pathfinding_cell_size: int = 24

    @classmethod
    def from_dict(cls, data, fallback_size=(1280, 720)):
        background = data.get("background", "")
        size = tuple(data.get("size") or get_image_size(background, fallback_size))
        player_spawn = tuple(data.get("player_spawn", (size[0] // 2, size[1] // 2)))
        character_scale = float(data.get("character_scale", 0.7))
        pathfinding_cell_size = int(data.get("pathfinding_cell_size", 24))

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

        hazard_zones = []
        hazard_metadata = []
        for index, item in enumerate(data.get("hazard_zones", [])):
            rect = pygame.Rect(item["x"], item["y"], item["w"], item["h"])
            hazard_zones.append(rect)
            hazard_metadata.append(
                {
                    "name": item.get("name", f"hazard_{index}"),
                    "type": item.get("type", "hazard"),
                    "enabled": item.get("enabled", True),
                    "damage": item.get("damage", DEFAULT_HAZARD_DAMAGE),
                    "damage_cooldown": item.get("damage_cooldown", DEFAULT_HAZARD_DAMAGE_COOLDOWN),
                }
            )
            
        walkable_zones = []
        walkable_metadata = []
        for index, item in enumerate(data.get("walkable_zones", [])):
            rect = pygame.Rect(item["x"], item["y"], item["w"], item["h"])
            walkable_zones.append(rect)
            walkable_metadata.append(
                {
                    "name": item.get("name", f"walkable_{index}"),
                    "type": item.get("type", "walkable"),
                    "enabled": item.get("enabled", True),
                }
            )

        return cls(
            name=data.get("name", "unnamed_level"),
            background=background,
            size=size,
            player_spawn=player_spawn,
            character_scale=character_scale,
            pathfinding_cell_size=pathfinding_cell_size,
            colliders=colliders,
            collider_metadata=collider_metadata,
            hazard_zones=hazard_zones,
            hazard_metadata=hazard_metadata,
            triggers=data.get("triggers", []),
            enemy_spawns=[tuple(spawn) for spawn in data.get("enemy_spawns", [])],
            interactables=data.get("interactables", []),
            doors=data.get("doors", []),
            walkable_zones=walkable_zones,
            walkable_metadata=walkable_metadata,
        )

    @property
    def width(self):
        return int(self.size[0])

    @property
    def height(self):
        return int(self.size[1])

    @property
    def rect(self):
        return pygame.Rect(0, 0, self.width, self.height)

    def create_collision_manager(self):
        return CollisionManager(
            self.colliders,
            self.collider_metadata,
            walkable_zones=self.walkable_zones,
            walkable_metadata=self.walkable_metadata,
        )

    def iter_hazard_hits(self, rect):
        for hazard_rect, data in zip(self.hazard_zones, self.hazard_metadata):
            if data.get("enabled", True) and rect.colliderect(hazard_rect):
                yield hazard_rect, data

    def draw_hazard_debug(self, surface, camera=None, font=None, show_names=False):
        offset_x, offset_y = 0, 0
        if isinstance(camera, (tuple, list)) and len(camera) >= 2:
            offset_x, offset_y = int(camera[0]), int(camera[1])
        for rect, data in zip(self.hazard_zones, self.hazard_metadata):
            if not data.get("enabled", True):
                continue
            debug_rect = rect.move(offset_x, offset_y)
            pygame.draw.rect(surface, (255, 60, 220), debug_rect, 2)
            if show_names and font:
                text = font.render(str(data.get("name", "hazard")), True, (255, 180, 255))
                surface.blit(text, (debug_rect.x + 3, debug_rect.y + 3))

    def load_background(self):
        if not self.background:
            return None
        image = pygame.image.load(str(resolve_asset_path(self.background)))
        if pygame.display.get_init() and pygame.display.get_surface():
            image = image.convert()
        if image.get_size() != tuple(self.size):
            image = pygame.transform.scale(image, tuple(self.size))
        return image

    def save_to_file(self):
        import shutil
        path = resolve_level_path(self.name)
        
        # Build new lists
        new_colliders = []
        for r, md in zip(self.colliders, self.collider_metadata):
            item = {"x": int(r.x), "y": int(r.y), "w": int(r.w), "h": int(r.h)}
            for k, v in md.items():
                if k not in ("x", "y", "w", "h"):
                    item[k] = v
            new_colliders.append(item)
            
        new_hazards = []
        for r, md in zip(self.hazard_zones, self.hazard_metadata):
            item = {"x": int(r.x), "y": int(r.y), "w": int(r.w), "h": int(r.h)}
            for k, v in md.items():
                if k not in ("x", "y", "w", "h"):
                    item[k] = v
            new_hazards.append(item)
            
        new_walkables = []
        for r, md in zip(self.walkable_zones, self.walkable_metadata):
            item = {"x": int(r.x), "y": int(r.y), "w": int(r.w), "h": int(r.h)}
            for k, v in md.items():
                if k not in ("x", "y", "w", "h"):
                    item[k] = v
            new_walkables.append(item)

        data = {}
        if path.exists():
            # Backup
            backup_path = path.with_suffix(".json.bak")
            shutil.copy2(path, backup_path)
            try:
                with path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        
        if not data:
            data = {
                "name": self.name,
                "background": self.background,
                "size": list(self.size),
                "player_spawn": list(self.player_spawn),
                "enemy_spawns": [list(s) for s in self.enemy_spawns],
                "triggers": self.triggers,
                "interactables": self.interactables,
                "doors": self.doors
            }
            
        data["colliders"] = new_colliders
        data["hazard_zones"] = new_hazards
        data["walkable_zones"] = new_walkables
        data["pathfinding_cell_size"] = int(self.pathfinding_cell_size)
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)



def resolve_level_path(level_name_or_path):
    path = Path(level_name_or_path)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    if path.is_absolute():
        return path
    if path.parent == Path("."):
        return LEVELS_DIR / path
    return BASE_DIR / path


def load_level(level_name_or_path, fallback_size=(1280, 720)):
    path = resolve_level_path(level_name_or_path)
    if not path.exists():
        return build_default_combat_level(fallback_size)

    with path.open("r", encoding="utf-8") as f:
        return Level.from_dict(json.load(f), fallback_size=fallback_size)


def load_combat_level(room_id=None, fallback_size=(1280, 720), variant_suffix=None, variant_fallback=None):
    candidates = []
    if room_id:
        semester_key = level_key_from_room_id(room_id)
        if variant_suffix:
            candidates.append(f"{room_id}_{variant_suffix}")
            if semester_key:
                candidates.append(f"{semester_key}_{variant_suffix}")
            if variant_fallback:
                candidates.append(variant_fallback)
        candidates.append(room_id)
        if semester_key:
            candidates.append(semester_key)
    candidates.append(DEFAULT_COMBAT_LEVEL)

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        path = resolve_level_path(candidate)
        if path.exists():
            return load_level(path, fallback_size)
    return build_default_combat_level(fallback_size)


def build_default_combat_level(size=(1280, 720)):
    width, height = size
    data = {
        "name": DEFAULT_COMBAT_LEVEL,
        "background": None,
        "size": [width, height],
        "player_spawn": [width // 2, height // 2],
        "pathfinding_cell_size": 24,
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
        "hazard_zones": [],
        "triggers": [],
    }
    return Level.from_dict(data, fallback_size=size)