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

        collisions = [collider for collider in self._enabled_colliders() if entity.rect.colliderect(collider)]
        if not collisions:
            return False

        if axis == "x":
            if amount > 0:
                entity.rect.right = min(collider.left for collider in collisions)
            else:
                entity.rect.left = max(collider.right for collider in collisions)
            if hasattr(entity, "x"):
                entity.x = float(entity.rect.centerx)
        else:
            if amount > 0:
                entity.rect.bottom = min(collider.top for collider in collisions)
            else:
                entity.rect.top = max(collider.bottom for collider in collisions)
            if hasattr(entity, "y"):
                entity.y = float(entity.rect.centery)

        return True

    def draw_debug(self, surface, camera=None, font=None, show_names=False):
        offset_x, offset_y = self._camera_offset(camera)
        for rect, data in zip(self.colliders, self.metadata):
            if not data.get("enabled", True):
                continue
            debug_rect = rect.move(offset_x, offset_y)
            pygame.draw.rect(surface, (255, 70, 70), debug_rect, 2)
            if show_names and font:
                name = str(data.get("name", "collider"))
                text = font.render(name, True, (255, 190, 190))
                bg = pygame.Surface((text.get_width() + 6, text.get_height() + 4), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 155))
                label_x = debug_rect.x
                label_y = debug_rect.y - text.get_height() - 4
                if label_y < 0:
                    label_y = debug_rect.y + 2
                surface.blit(bg, (label_x, label_y))
                surface.blit(text, (label_x + 3, label_y + 2))

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
