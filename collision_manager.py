import math

import pygame


class CollisionManager:
    def __init__(self, colliders, metadata=None, max_step=8):
        self.max_step = max(1, max_step)
        self.colliders = []
        self.metadata = []

        metadata = metadata or []
        for index, collider in enumerate(colliders):
            rect = self._to_rect(collider)
            data = metadata[index].copy() if index < len(metadata) else {}
            if isinstance(collider, dict):
                data.update({k: v for k, v in collider.items() if k not in ("x", "y", "w", "h", "rect")})
            data.setdefault("name", f"collider_{index}")
            data.setdefault("type", "solid")
            data.setdefault("enabled", True)
            self.colliders.append(rect)
            self.metadata.append(data)

    def _to_rect(self, collider):
        if isinstance(collider, pygame.Rect):
            return collider.copy()
        if isinstance(collider, dict):
            if "rect" in collider:
                return self._to_rect(collider["rect"])
            return pygame.Rect(collider["x"], collider["y"], collider["w"], collider["h"])
        return pygame.Rect(collider)

    def _enabled_colliders(self):
        for rect, data in zip(self.colliders, self.metadata):
            if data.get("enabled", True):
                yield rect

    def check_collision(self, rect):
        for collider in self._enabled_colliders():
            if rect.colliderect(collider):
                return collider
        return None

    def get_collisions(self, rect):
        return [collider for collider in self._enabled_colliders() if rect.colliderect(collider)]

    def move_and_collide(self, entity, dx, dy):
        if not hasattr(entity, "rect"):
            raise AttributeError("Collision entities must expose a pygame.Rect as 'rect'.")

        if hasattr(entity, "sync_rect_to_position"):
            entity.sync_rect_to_position()

        steps = max(1, int(math.ceil(max(abs(dx), abs(dy)) / self.max_step)))
        step_dx = dx / steps
        step_dy = dy / steps
        blocked = {"x": False, "y": False}

        for _ in range(steps):
            if self._move_axis(entity, step_dx, "x"):
                blocked["x"] = True
            if self._move_axis(entity, step_dy, "y"):
                blocked["y"] = True

        if hasattr(entity, "sync_position_to_rect"):
            entity.sync_position_to_rect()

        return blocked

    def _move_axis(self, entity, amount, axis):
        if amount == 0:
            return False

        if axis == "x":
            if hasattr(entity, "x"):
                entity.x += amount
                entity.rect.centerx = int(round(entity.x))
            else:
                entity.rect.x += int(round(amount))
        else:
            if hasattr(entity, "y"):
                entity.y += amount
                entity.rect.centery = int(round(entity.y))
            else:
                entity.rect.y += int(round(amount))

        collided = False
        for collider in self._enabled_colliders():
            if not entity.rect.colliderect(collider):
                continue

            collided = True
            if axis == "x":
                if amount > 0:
                    entity.rect.right = collider.left
                else:
                    entity.rect.left = collider.right
                if hasattr(entity, "x"):
                    entity.x = float(entity.rect.centerx)
            else:
                if amount > 0:
                    entity.rect.bottom = collider.top
                else:
                    entity.rect.top = collider.bottom
                if hasattr(entity, "y"):
                    entity.y = float(entity.rect.centery)

        return collided

    def draw_debug(self, surface, camera=None):
        offset_x, offset_y = self._camera_offset(camera)
        for rect in self._enabled_colliders():
            debug_rect = rect.move(offset_x, offset_y)
            pygame.draw.rect(surface, (255, 220, 40), debug_rect, 2)

    def _camera_offset(self, camera):
        if camera is None:
            return 0, 0
        if isinstance(camera, (tuple, list)) and len(camera) >= 2:
            return int(camera[0]), int(camera[1])
        if hasattr(camera, "offset"):
            offset = camera.offset
            return int(offset[0]), int(offset[1])
        if hasattr(camera, "x") and hasattr(camera, "y"):
            return int(camera.x), int(camera.y)
        return 0, 0
