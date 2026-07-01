import pygame
import math
import random
from animator import Animator
from enemy_ai import EnemyNavigator, separation_delta

class EnemyBullet:
    def __init__(self, x, y, angle, speed=5, color=(255, 0, 0), radius=5, b_type="normal"):
        self.x = x
        self.y = y
        self.speed = speed
        self.radius = radius
        self.color = color
        self.b_type = b_type
        self.dx = math.cos(angle) * self.speed
        self.dy = math.sin(angle) * self.speed

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, surface, offset_x=0, offset_y=0):
        dx = self.x + offset_x
        dy = self.y + offset_y
        if self.b_type == "miniboss":
            # Examen reprobado (papel con 'F')
            pygame.draw.rect(surface, (240, 240, 240), (dx - 8, dy - 12, 16, 24))
            pygame.draw.rect(surface, (0, 0, 0), (dx - 8, dy - 12, 16, 24), 1)
            # Líneas simulando texto
            pygame.draw.line(surface, (150, 150, 150), (dx - 5, dy - 8), (dx + 5, dy - 8))
            pygame.draw.line(surface, (150, 150, 150), (dx - 5, dy - 4), (dx + 5, dy - 4))
            # Una 'F' roja gruesa
            pygame.draw.line(surface, (255, 0, 0), (dx - 4, dy + 2), (dx - 4, dy + 10), 2)
            pygame.draw.line(surface, (255, 0, 0), (dx - 4, dy + 2), (dx + 3, dy + 2), 2)
            pygame.draw.line(surface, (255, 0, 0), (dx - 4, dy + 6), (dx + 1, dy + 6), 2)
            
        elif self.b_type == "boss":
            # Tomo de tesis gruesa con sello dorado
            pygame.draw.rect(surface, (139, 0, 0), (dx - 12, dy - 16, 24, 32)) # Tapa roja
            pygame.draw.rect(surface, (255, 215, 0), (dx - 12, dy - 16, 24, 32), 2) # Borde dorado
            pygame.draw.rect(surface, (220, 220, 220), (dx + 8, dy - 14, 4, 28)) # Páginas blancas laterales
            # Texto cruzado o sello dorado en el centro
            pygame.draw.circle(surface, (255, 215, 0), (int(dx - 2), int(dy)), 6)
            
        else:
            pygame.draw.circle(surface, self.color, (int(dx), int(dy)), self.radius)
            pygame.draw.circle(surface, (255, 255, 255), (int(dx), int(dy)), self.radius, 1)

    def is_offscreen(self, w, h):
        return self.x < 0 or self.x > w or self.y < 0 or self.y > h

class Enemy:
    def __init__(self, x, y, radius, speed, hp, sheet_path, frame_width, frame_height=None, cols=4, rows=3, scale=1.0):
        self.x = x
        self.y = y
        self.radius = radius * scale
        self.rect = pygame.Rect(0, 0, self.radius * 2, self.radius * 2)
        self.sync_rect_to_position()
        self.last_collision = {"x": False, "y": False}
        self.speed = speed
        self.hp = hp
        self.max_hp = hp
        self.attack_cooldown = 0
        self.state = 1 # 1: Move
        self.bullets = []
        self.evasion_dir = random.choice([-1, 1])
        self.evasion_timer = 0
        self.ai_smartness = 0.85
        self.separation_weight = 0.55
        self.navigator = EnemyNavigator()
        self.ignores_map_collision = False
        
        
        if frame_height is None:
            frame_height = frame_width
        self.animator = Animator(sheet_path, int(frame_width * scale), int(frame_height * scale), rows, cols, 0.15)
        self.color = (255, 50, 50)

    def sync_rect_to_position(self):
        self.rect.center = (int(round(self.x)), int(round(self.y)))

    def sync_position_to_rect(self):
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)

    def update_special_movement(self, player_x, player_y, width, height, collision_manager=None, pathfinder=None):
        return False

    def after_navigation_update(self, player_x, player_y, width, height, pathfinder=None):
        pass

    def update(self, player_x, player_y, width, height, collision_manager=None, pathfinder=None, nearby_enemies=None):
        if self.update_special_movement(player_x, player_y, width, height, collision_manager, pathfinder):
            self._update_cooldowns_and_bullets(width, height)
            return

        old_x, old_y = self.x, self.y
        self.move_logic(player_x, player_y)

        dx = self.x - old_x
        dy = self.y - old_y
        self.x, self.y = old_x, old_y
        self.sync_rect_to_position()

        ignores_map = getattr(self, "ignores_map_collision", False)
        if pathfinder and not ignores_map:
            dx, dy = self.navigator.plan_movement(self, (player_x, player_y), (dx, dy), pathfinder)
        elif ignores_map:
            self.navigator.clear_path()
            self.navigator.mode = "flying"
        else:
            # Fallback historico: evasion local si no hay PathFinder disponible.
            if self.last_collision.get("x") or self.last_collision.get("y"):
                if self.evasion_timer <= 0:
                    self.evasion_timer = 40
                    self.evasion_dir = random.choice([-1, 1])

            if self.evasion_timer > 0:
                self.evasion_timer -= 1
                if self.last_collision.get("x"):
                    dy += 3.0 * self.evasion_dir if abs(player_y - old_y) < 25 else (3.0 if player_y >= old_y else -3.0)
                if self.last_collision.get("y"):
                    dx += 3.0 * self.evasion_dir if abs(player_x - old_x) < 25 else (3.0 if player_x >= old_x else -3.0)

        sep_x, sep_y = separation_delta(self, nearby_enemies)
        dx += sep_x
        dy += sep_y

        if ignores_map:
            self.x, self.y = old_x + dx, old_y + dy
            self.sync_rect_to_position()
            self.rect.clamp_ip(pygame.Rect(0, 0, width, height))
            self.sync_position_to_rect()
            self.last_collision = {"x": False, "y": False}
        elif collision_manager:
            self.x, self.y = old_x, old_y
            self.sync_rect_to_position()
            self.last_collision = collision_manager.move_and_collide(self, dx, dy)
        else:
            self.x, self.y = old_x + dx, old_y + dy
            self.sync_rect_to_position()
            self.last_collision = {"x": False, "y": False}

        if pathfinder and not ignores_map:
            self.navigator.record_result((old_x, old_y), (self.x, self.y), (dx, dy), self.last_collision)

        self.after_navigation_update(player_x, player_y, width, height, pathfinder)
        self._update_cooldowns_and_bullets(width, height)

    def _update_cooldowns_and_bullets(self, width, height):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.is_offscreen(width, height):
                self.bullets.remove(b)

    def get_visual_y_offset(self):
        return 0.0

    def draw_movement_shadow(self, surface, offset_x=0, offset_y=0, visual_y_offset=0):
        pass

    def move_logic(self, player_x, player_y):
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1 # Moving

    def draw(self, surface, offset_x=0, offset_y=0):
        self.animator.set_state(self.state)
        self.animator.update()
        image = self.animator.get_current_image()
        
        visual_y_offset = self.get_visual_y_offset()
        self.draw_movement_shadow(surface, offset_x, offset_y, visual_y_offset)
        dx = int(self.x + offset_x)
        dy = int(self.y + offset_y - visual_y_offset)
        
        if image:
            rect = image.get_rect(center=(dx, dy))
            surface.blit(image, rect)
        else:
            pygame.draw.rect(surface, self.color, (dx - self.radius, dy - self.radius, self.radius*2, self.radius*2))
        
        # Barra de vida eliminada (ahora se mostrarán números de daño)
        # Dibujar balas enemigas
        for b in self.bullets:
            b.draw(surface, offset_x, offset_y)

    def collides_with_bullet(self, bullet):
        dist = math.hypot(self.x - bullet.x, self.y - bullet.y)
        return dist < (self.radius + bullet.radius)

    def collides_with_player(self, player):
        dist = math.hypot(self.x - player.x, self.y - player.y)
        return dist < (self.radius + player.radius)

# ---- Normal Enemies ----

class BugEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        # Tamaño escalado un poco más pequeño
        super().__init__(x, y, 20, 3.0, 20, "assets/images/enemies/bug_sheet.png", 54, cols=6, scale=scale)
        self.ai_smartness = 0.9
        self.animator.animation_speed = 0.08
class SpaghettiEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 29, 1.5, 40, "assets/images/enemies/spaghetti_sheet.png", 72, scale=scale)
        self.ai_smartness = 0.55
        self.separation_weight = 0.45
    def move_logic(self, player_x, player_y):
        # Erratic movement
        angle = math.atan2(player_y - self.y, player_x - self.x) + random.uniform(-0.5, 0.5)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1

class MemoryLeakEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 24, 2.0, 30, "assets/images/enemies/leak_sheet.png", 48, scale=scale)
        self.ai_smartness = 0.95

class DeadlineEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 36, 1.0, 25, "assets/images/enemies/deadline_sheet.png", 96, scale=scale)
        self.ai_smartness = 0.85
    def move_logic(self, player_x, player_y):
        dist = math.hypot(player_x - self.x, player_y - self.y)
        speed = 4.0 if dist < 150 else 1.0
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * speed
        self.y += math.sin(angle) * speed
        self.state = 1 if speed == 1.0 else 2

    def draw(self, surface, offset_x=0, offset_y=0):
        # Efecto visual de enfado / aceleración (aura roja pulsante)
        if self.state == 2:
            pulse = (math.sin(pygame.time.get_ticks() / 100.0) + 1) / 2.0
            glow_radius = int(self.radius * (1.2 + 0.5 * pulse))
            glow_surf = pygame.Surface((glow_radius*2, glow_radius*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 50, 50, int(150 * pulse)), (glow_radius, glow_radius), glow_radius)
            surface.blit(glow_surf, (int(self.x + offset_x - glow_radius), int(self.y + offset_y - glow_radius)))
            
        super().draw(surface, offset_x, offset_y)

# ---- Bosses ----

class MiniBoss(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 90, 1.2, 150, "assets/images/enemies/miniboss_sheet.png", 192, scale=scale)
        self.ai_smartness = 0.75
        self.separation_weight = 0.25
        self.action_timer = 0
        self.animator.animation_speed = 0.08 # Animacion un poco mas lenta
        self.jump_timer = 0
        self.jump_duration = 38
        self.jump_cooldown = 0
        self.jump_cooldown_duration = 90
        self.jump_trigger_frames = 10
        self.jump_blocked_frames = 0
        self.jump_start = (self.x, self.y)
        self.jump_target = (self.x, self.y)
        self.jump_height = max(70, int(120 * scale))
        self.min_jump_distance = max(120, int(220 * scale))
        self.max_jump_distance = max(260, int(520 * scale))
        self.min_landing_player_distance = max(self.radius + 35, int(140 * scale))
        self.jump_landing_valid = True
        self.jump_landing_fallback = False
        self.jump_landing_reason = "idle"
        self.jump_landing_candidates = []
        self.jump_debug_start = self.jump_start
        self.jump_debug_target = self.jump_target
        self.jump_player_reference = (self.x, self.y)
        self.color = (255, 90, 40)

    def update_special_movement(self, player_x, player_y, width, height, collision_manager=None, pathfinder=None):
        if self.jump_cooldown > 0:
            self.jump_cooldown -= 1
        if self.jump_timer <= 0:
            return False

        elapsed = self.jump_duration - self.jump_timer
        progress = min(1.0, max(0.0, elapsed / self.jump_duration))
        ease = progress * progress * (3 - 2 * progress)
        self.x = self.jump_start[0] + (self.jump_target[0] - self.jump_start[0]) * ease
        self.y = self.jump_start[1] + (self.jump_target[1] - self.jump_start[1]) * ease
        self.sync_rect_to_position()
        self.last_collision = {"x": False, "y": False, "jump": True}
        self.navigator.clear_path()
        self.navigator.mode = "jumping"
        self.state = 2

        self.jump_timer -= 1
        if self.jump_timer <= 0:
            self.revalidate_landing_target(player_x, player_y, width, height, pathfinder)
            self.x, self.y = self.jump_target
            self.sync_rect_to_position()
            self.rect.clamp_ip(pygame.Rect(0, 0, width, height))
            self.sync_position_to_rect()
            self.jump_debug_target = self.jump_target
            self.jump_cooldown = self.jump_cooldown_duration
            self.jump_blocked_frames = 0
            self.navigator.force_repath = True
            self.navigator.mode = "landed"
            self.action_timer = 0
        return True

    def after_navigation_update(self, player_x, player_y, width, height, pathfinder=None):
        if self.jump_timer > 0 or self.jump_cooldown > 0:
            return

        collided = self.last_collision.get("x") or self.last_collision.get("y")
        path_failed = self.navigator.mode == "fallback" or (
            not self.navigator.last_result_found and self.navigator.no_path_frames > 0
        )
        if collided or path_failed:
            self.jump_blocked_frames += 1
        else:
            self.jump_blocked_frames = max(0, self.jump_blocked_frames - 2)

        if self.jump_blocked_frames >= self.jump_trigger_frames:
            self.start_obstacle_jump(player_x, player_y, width, height, pathfinder)

    def start_obstacle_jump(self, player_x, player_y, width, height, pathfinder=None):
        target, was_valid, used_fallback, reason = self.choose_jump_target(player_x, player_y, width, height, pathfinder)
        if target is None:
            return False
        self.jump_start = (self.x, self.y)
        self.jump_target = target
        self.jump_debug_start = self.jump_start
        self.jump_debug_target = self.jump_target
        self.jump_player_reference = (player_x, player_y)
        self.jump_landing_valid = was_valid
        self.jump_landing_fallback = used_fallback
        self.jump_landing_reason = reason
        self.jump_timer = self.jump_duration
        self.jump_blocked_frames = 0
        self.navigator.clear_path()
        self.navigator.mode = "jumping"
        self.state = 2
        return True

    def choose_jump_target(self, player_x, player_y, width, height, pathfinder=None):
        dx = player_x - self.x
        dy = player_y - self.y
        distance = math.hypot(dx, dy)
        if distance <= 8:
            return None, False, True, "too_close"

        nx, ny = dx / distance, dy / distance
        side_x, side_y = -ny, nx
        landing_gap = self.min_landing_player_distance
        desired_distance = min(self.max_jump_distance, max(self.min_jump_distance, distance - self.radius * 0.6))
        primary = (self.x + nx * desired_distance, self.y + ny * desired_distance)

        candidates = [primary]
        candidates.extend(self.build_jump_landing_candidates(primary, player_x, player_y, nx, ny, side_x, side_y, landing_gap, desired_distance))

        self.jump_landing_candidates = []
        best_point = None
        best_score = float("inf")
        best_reason = "no_candidate"

        for candidate in candidates:
            point = self.clamp_jump_target(candidate, width, height)
            valid, reason = self.is_valid_landing_point(point, player_x, player_y, width, height, pathfinder)
            score = self.score_landing_point(point, primary, player_x, player_y, reason)
            self.jump_landing_candidates.append({"point": point, "valid": valid, "reason": reason})
            if valid:
                return point, True, False, "valid"
            if score < best_score:
                best_point = point
                best_score = score
                best_reason = reason

        fallback = best_point if best_point is not None else self.clamp_jump_target(primary, width, height)
        return fallback, False, True, best_reason

    def build_jump_landing_candidates(self, primary, player_x, player_y, nx, ny, side_x, side_y, landing_gap, desired_distance):
        candidates = [
            (player_x - nx * landing_gap, player_y - ny * landing_gap),
            (player_x + side_x * landing_gap, player_y + side_y * landing_gap),
            (player_x - side_x * landing_gap, player_y - side_y * landing_gap),
        ]

        for distance_scale in (0.55, 0.75, 1.0, 1.2):
            jump_distance = max(self.min_jump_distance, min(self.max_jump_distance, desired_distance * distance_scale))
            center_x = self.x + nx * jump_distance
            center_y = self.y + ny * jump_distance
            candidates.append((center_x, center_y))
            candidates.append((center_x + side_x * self.radius, center_y + side_y * self.radius))
            candidates.append((center_x - side_x * self.radius, center_y - side_y * self.radius))

        search_radii = (self.radius * 0.75, self.radius * 1.25, self.radius * 1.8, self.radius * 2.4)
        for radius in search_radii:
            for step in range(12):
                angle = (math.tau / 12) * step
                candidates.append((primary[0] + math.cos(angle) * radius, primary[1] + math.sin(angle) * radius))

        return candidates

    def is_valid_landing_point(self, point, player_x, player_y, width, height, pathfinder=None):
        rect = pygame.Rect(0, 0, int(self.rect.w), int(self.rect.h))
        rect.center = (int(round(point[0])), int(round(point[1])))
        map_rect = pygame.Rect(0, 0, width, height)
        if not map_rect.contains(rect):
            return False, "outside_map"
        if math.hypot(point[0] - player_x, point[1] - player_y) < self.min_landing_player_distance:
            return False, "too_close_to_player"

        if pathfinder:
            if any(rect.colliderect(collider) for collider in pathfinder.colliders):
                return False, "solid_collider"
            if pathfinder.walkable_zones and not any(zone.collidepoint(rect.center) for zone in pathfinder.walkable_zones):
                return False, "outside_walkable"
            return True, "valid"

        return True, "valid_no_pathfinder"

    def score_landing_point(self, point, primary, player_x, player_y, reason):
        distance_to_primary = math.hypot(point[0] - primary[0], point[1] - primary[1])
        distance_to_player = math.hypot(point[0] - player_x, point[1] - player_y)
        player_penalty = max(0.0, self.min_landing_player_distance - distance_to_player) * 4.0
        reason_penalties = {
            "too_close_to_player": 120.0,
            "outside_walkable": 220.0,
            "solid_collider": 360.0,
            "outside_map": 520.0,
        }
        return distance_to_primary + player_penalty + reason_penalties.get(reason, 0.0)

    def clamp_jump_target(self, target, width, height):
        half_w = self.rect.w / 2
        half_h = self.rect.h / 2
        x = max(half_w, min(width - half_w, target[0]))
        y = max(half_h, min(height - half_h, target[1]))
        return float(x), float(y)

    def revalidate_landing_target(self, player_x, player_y, width, height, pathfinder=None):
        valid, reason = self.is_valid_landing_point(self.jump_target, player_x, player_y, width, height, pathfinder)
        if valid:
            self.jump_landing_valid = True
            self.jump_landing_fallback = False
            self.jump_landing_reason = "valid"
            return

        primary = self.jump_target
        candidates = [primary]
        for radius in (self.radius * 0.7, self.radius * 1.2, self.radius * 1.8, self.radius * 2.5):
            for step in range(16):
                angle = (math.tau / 16) * step
                candidates.append((primary[0] + math.cos(angle) * radius, primary[1] + math.sin(angle) * radius))

        best_point = self.clamp_jump_target(primary, width, height)
        best_score = float("inf")
        best_reason = reason
        repair_debug = []
        for candidate in candidates:
            point = self.clamp_jump_target(candidate, width, height)
            point_valid, point_reason = self.is_valid_landing_point(point, player_x, player_y, width, height, pathfinder)
            repair_debug.append({"point": point, "valid": point_valid, "reason": point_reason})
            if point_valid:
                self.jump_target = point
                self.jump_landing_valid = True
                self.jump_landing_fallback = False
                self.jump_landing_reason = "valid_repaired"
                self.jump_landing_candidates = repair_debug
                return
            score = self.score_landing_point(point, primary, player_x, player_y, point_reason)
            if score < best_score:
                best_point = point
                best_score = score
                best_reason = point_reason

        self.jump_target = self.clamp_jump_target(best_point, width, height)
        self.jump_landing_valid = False
        self.jump_landing_fallback = True
        self.jump_landing_reason = best_reason
        self.jump_landing_candidates = repair_debug

    def get_visual_y_offset(self):
        if self.jump_timer <= 0:
            return 0.0
        progress = 1.0 - (self.jump_timer / self.jump_duration)
        return math.sin(progress * math.pi) * self.jump_height

    def draw_movement_shadow(self, surface, offset_x=0, offset_y=0, visual_y_offset=0):
        if self.jump_timer <= 0:
            return
        progress = 1.0 - (self.jump_timer / self.jump_duration)
        lift = math.sin(progress * math.pi)
        shadow_scale = max(0.45, 1.0 - lift * 0.35)
        shadow_w = max(24, int(self.radius * 1.55 * shadow_scale))
        shadow_h = max(10, int(self.radius * 0.45 * shadow_scale))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, int(115 * (1.0 - lift * 0.45))), shadow.get_rect())
        surface.blit(shadow, (int(self.x + offset_x - shadow_w / 2), int(self.y + offset_y + self.radius * 0.55 - shadow_h / 2)))

    def move_logic(self, player_x, player_y):
        self.action_timer += 1
        
        if self.action_timer < 120:
            # Move towards player
            angle = math.atan2(player_y - self.y, player_x - self.x)
            self.x += math.cos(angle) * self.speed
            self.y += math.sin(angle) * self.speed
            self.state = 1
        elif self.action_timer < 150:
            # Telegraph attack
            self.state = 2
        else:
            # Shoot
            angle = math.atan2(player_y - self.y, player_x - self.x)
            self.bullets.append(EnemyBullet(self.x, self.y, angle, speed=6, radius=10, b_type="miniboss"))
            self.action_timer = 0
            self.state = 0

class Boss(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 105, 0.8, 500, "assets/images/enemies/boss_sheet.png", 288, cols=8, rows=4, scale=scale)
        self.ai_smartness = 0.7
        self.separation_weight = 0.2
        self.ignores_map_collision = True
        self.action_timer = 0
        

    def get_visual_y_offset(self):
        return 12 + math.sin(pygame.time.get_ticks() / 350.0) * 5

    def draw_movement_shadow(self, surface, offset_x=0, offset_y=0, visual_y_offset=0):
        shadow_w = max(32, int(self.radius * 1.45))
        shadow_h = max(12, int(self.radius * 0.38))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 95), shadow.get_rect())
        surface.blit(shadow, (int(self.x + offset_x - shadow_w / 2), int(self.y + offset_y + self.radius * 0.55 - shadow_h / 2)))

    def move_logic(self, player_x, player_y):
        self.action_timer += 1
        
        if self.action_timer < 150:
            # Move slowly
            angle = math.atan2(player_y - self.y, player_x - self.x)
            self.x += math.cos(angle) * self.speed
            self.y += math.sin(angle) * self.speed
            self.state = 1
        elif self.action_timer < 190:
            # Telegraph
            self.state = 2
        else:
            # Shoot ring of 8 bullets (Null Pointers)
            for i in range(8):
                angle = i * (math.pi / 4)
                self.bullets.append(EnemyBullet(self.x, self.y, angle, speed=4, radius=12, b_type="boss"))
            self.action_timer = 0
            self.state = 0
