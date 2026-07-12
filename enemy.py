import pygame
import math
import random
import audio
from animator import Animator
from animation_controller import AnimationClip, AnimationController
from enemy_ai import EnemyNavigator, separation_delta

_boss_projectile_sprite = None


def _get_boss_projectile_sprite():
    global _boss_projectile_sprite
    if _boss_projectile_sprite is None:
        try:
            _boss_projectile_sprite = pygame.image.load(
                "assets/images/projectiles/boss_corrupted_core.png"
            ).convert_alpha()
        except (pygame.error, FileNotFoundError):
            _boss_projectile_sprite = False
    return _boss_projectile_sprite

class EnemyBullet:
    def __init__(self, x, y, angle, speed=5, color=(255, 0, 0), radius=5, b_type="normal"):
        self.x = x
        self.y = y
        self.speed = speed
        self.radius = radius
        self.color = color
        self.b_type = b_type
        self.angle = angle
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
            # Núcleo de datos corrupto: sprite generado, rotado en pasos de 45°
            # para conservar píxeles nítidos en el ataque radial del jefe.
            sprite = _get_boss_projectile_sprite()
            if sprite:
                rotation = -round(math.degrees(self.angle) / 45.0) * 45
                image = pygame.transform.rotate(sprite, rotation)
                # Halo corto y contrastado: comunica energía hostil sobre el suelo oscuro.
                pulse = 5 + int((math.sin(pygame.time.get_ticks() / 90.0) + 1) * 2)
                glow = pygame.Surface((pulse * 4, pulse * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (38, 190, 255, 68), (pulse * 2, pulse * 2), pulse * 2)
                surface.blit(glow, glow.get_rect(center=(int(dx), int(dy))),
                             special_flags=pygame.BLEND_RGBA_ADD)
                surface.blit(image, image.get_rect(center=(int(dx), int(dy))))
            else:
                pygame.draw.circle(surface, (255, 55, 20), (int(dx), int(dy)), self.radius)
                pygame.draw.circle(surface, (255, 235, 190), (int(dx), int(dy)), self.radius // 2)
            
        else:
            pygame.draw.circle(surface, self.color, (int(dx), int(dy)), self.radius)
            pygame.draw.circle(surface, (255, 255, 255), (int(dx), int(dy)), self.radius, 1)

    def is_offscreen(self, w, h):
        return self.x < 0 or self.x > w or self.y < 0 or self.y > h

class Enemy:
    def __init__(self, x, y, radius, speed, hp, sheet_path, frame_width, frame_height=None, cols=4, rows=3, scale=1.0, collision_scale=1.0):
        self.x = x
        self.y = y
        self.radius = radius * scale
        self.collision_scale = collision_scale
        collision_size = max(8, int(round(self.radius * 2 * collision_scale)))
        self.rect = pygame.Rect(0, 0, collision_size, collision_size)
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
        self.hit_flash = 0  # frames de flash blanco al recibir un balazo
        self.knockback_x = 0.0
        self.knockback_y = 0.0
        self.ai_smartness = 0.85
        self.separation_weight = 0.55
        self.navigator = EnemyNavigator()
        self.ignores_map_collision = False
        
        
        if frame_height is None:
            frame_height = frame_width
        self.animator = Animator(
            sheet_path,
            int(frame_width * scale), int(frame_height * scale),
            rows, cols, 0.15,
            state_speeds={0: 0.08, 1: 0.14, 2: 0.22},
        )
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
        old_x, old_y = self.x, self.y
        if self.update_special_movement(player_x, player_y, width, height, collision_manager, pathfinder):
            self._update_cooldowns_and_bullets(width, height)
            self._sync_animation_base(old_x, old_y)
            return

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
        dx += self.knockback_x
        dy += self.knockback_y
        # Decaimiento rapido: el empujon debe ser un toque breve, no un
        # desplazamiento largo que deje al enemigo retrocediendo varios frames.
        self.knockback_x *= 0.4
        self.knockback_y *= 0.4
        if abs(self.knockback_x) < 0.1:
            self.knockback_x = 0.0
        if abs(self.knockback_y) < 0.1:
            self.knockback_y = 0.0

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
        self._sync_animation_base(old_x, old_y)

    def configure_standard_controller(self, base="move"):
        self.controller = AnimationController(self.animator, {
            "idle": AnimationClip(state=0, loop=True, priority=0),
            "move": AnimationClip(state=1, loop=True, priority=0),
            "attack": AnimationClip(state=2, loop=False, priority=30),
        }, base=base)

    def _sync_animation_base(self, old_x, old_y):
        controller = getattr(self, "controller", None)
        if controller is None:
            return
        moved = math.hypot(self.x - old_x, self.y - old_y) > 0.3
        controller.set_base("move" if moved else "idle")

    def take_damage(self, amount, source_x=None, source_y=None):
        self.hp -= amount
        self.hit_flash = 4
        if source_x is not None and source_y is not None:
            dx = self.x - source_x
            dy = self.y - source_y
            distance = max(1.0, math.hypot(dx, dy))
            strength = 0.8 if isinstance(self, (MiniBoss, Boss)) else 2.0
            self.knockback_x = dx / distance * strength
            self.knockback_y = dy / distance * strength
        return self.hp <= 0

    def _update_cooldowns_and_bullets(self, width, height):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
        if self.hit_flash > 0:
            self.hit_flash -= 1

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.is_offscreen(width, height):
                self.bullets.remove(b)

    def get_visual_y_offset(self):
        return 0.0

    def draw_movement_shadow(self, surface, offset_x=0, offset_y=0, visual_y_offset=0):
        pass

    def notify_attack(self):
        """El gameplay avisa que este enemigo conecto un golpe.

        En entidades migradas al AnimationController dispara el one-shot de
        ataque; en las demas no hace nada (siguen con el state numerico).
        """
        controller = getattr(self, "controller", None)
        if controller is not None:
            controller.play("attack")

    def move_logic(self, player_x, player_y):
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1 # Moving

    def draw(self, surface, offset_x=0, offset_y=0):
        controller = getattr(self, "controller", None)
        if controller is not None:
            # Entidad migrada: el controller decide el clip; el state numerico
            # que aun escriba la IA heredada se ignora.
            controller.update()
        else:
            self.animator.set_state(self.state)
            self.animator.update()
        image = self.animator.get_current_image()
        
        visual_y_offset = self.get_visual_y_offset()
        self.draw_movement_shadow(surface, offset_x, offset_y, visual_y_offset)
        dx = int(self.x + offset_x)
        dy = int(self.y + offset_y - visual_y_offset)
        
        if image:
            if self.hit_flash > 0:
                # Flash de impacto: tinte rojo apagado SEMITRANSPARENTE encima del
                # sprite (el enemigo se sigue viendo debajo). Se construye una
                # silueta roja solida, se le baja el alfa y se superpone.
                image = image.copy()
                tint = image.copy()
                tint.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)   # RGB->0, alfa intacto
                tint.fill((170, 40, 40, 0), special_flags=pygame.BLEND_RGB_ADD)    # silueta roja
                tint.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)  # ~59% de opacidad
                image.blit(tint, (0, 0))
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
    """Piloto de la migracion al AnimationController: su animacion la decide
    el controller (idle/move segun desplazamiento real, attack como one-shot
    al conectar un golpe), no el state numerico heredado."""

    def __init__(self, x, y, scale=1.0):
        # Tamaño escalado un poco más pequeño
        super().__init__(x, y, 20, 3.0, 20, "assets/images/enemies/bug_sheet_normalized.png", 54, cols=6, scale=scale, collision_scale=0.82)
        self.ai_smartness = 0.9
        self.animator.state_speeds = {0: 0.07, 1: 0.18, 2: 0.28}
        for state, name in enumerate(("idle", "walk", "attack")):
            self.animator.replace_state_from_sheet(
                state, f"assets/images/enemies/generated/bug_{name}_v2_alpha_master_normalized.png",
                rows=2, cols=4, frame_height=int(54 * scale),
            )
        self.configure_standard_controller()
class SpaghettiEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 29, 1.5, 40, "assets/images/enemies/spaghetti_sheet_normalized.png", 72, scale=scale, collision_scale=0.70)
        self.ai_smartness = 0.55
        self.separation_weight = 0.45
        self.animator.state_speeds = {0: 0.06, 1: 0.14, 2: 0.22}
        for state, name in enumerate(("idle", "walk", "attack")):
            self.animator.replace_state_from_sheet(
                state, f"assets/images/enemies/generated/spaghetti_{name}_v2_alpha_master_normalized.png",
                rows=2, cols=4, frame_height=int(72 * scale),
            )
        self.configure_standard_controller()
    def move_logic(self, player_x, player_y):
        # Erratic movement
        angle = math.atan2(player_y - self.y, player_x - self.x) + random.uniform(-0.5, 0.5)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1

class MemoryLeakEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 24, 2.0, 30, "assets/images/enemies/leak_sheet_normalized.png", 48, scale=scale, collision_scale=0.82)
        self.ai_smartness = 0.95
        self.animator.state_speeds = {0: 0.06, 1: 0.13, 2: 0.20}
        for state, name in enumerate(("idle", "walk", "attack")):
            self.animator.replace_state_from_sheet(
                state, f"assets/images/enemies/generated/leak_{name}_v2_alpha_master_normalized.png",
                rows=2, cols=4, frame_height=int(48 * scale),
            )
        self.configure_standard_controller()

class DeadlineEnemy(Enemy):
    SCALE_FACTOR = 0.9  # ajuste visual sobre la escala del nivel

    def __init__(self, x, y, scale=1.0):
        scale *= self.SCALE_FACTOR
        super().__init__(x, y, 36, 1.0, 25, "assets/images/enemies/deadline_sheet_normalized.png", 96, scale=scale, collision_scale=0.56)
        self.ai_smartness = 0.85
        self.animator.state_speeds = {0: 0.07, 1: 0.16, 2: 0.22}
        self.animator.replace_state_from_sheet(
            0,
            "assets/images/enemies/generated/deadline_idle_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(96 * scale),
        )
        self.animator.replace_state_from_sheet(
            1,
            "assets/images/enemies/generated/deadline_walk_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(96 * scale),
        )
        self.animator.replace_state_from_sheet(
            2,
            "assets/images/enemies/generated/deadline_attack_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(96 * scale),
        )
        self.configure_standard_controller()
    def move_logic(self, player_x, player_y):
        dist = math.hypot(player_x - self.x, player_y - self.y)
        speed = 4.0 if dist < 150 else 1.0
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * speed
        self.y += math.sin(angle) * speed
        self.state = 1 if speed == 1.0 else 2
        if speed > 1.0:
            self.controller.play("attack")

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
    ATTACK_ANIMATION_LEAD_FRAMES = 16  # frame de impacto 4 a velocidad 0.25
    SCALE_FACTOR = 1.15  # ajuste visual sobre la escala del nivel

    def __init__(self, x, y, scale=1.0):
        scale *= self.SCALE_FACTOR
        super().__init__(x, y, 90, 1.2, 150, "assets/images/enemies/miniboss_sheet_normalized.png", 192, scale=scale)
        self.ai_smartness = 0.75
        self.separation_weight = 0.25
        self.action_timer = 0
        self.animator.animation_speed = 0.08
        self.animator.state_speeds = {0: 0.07, 1: 0.16, 2: 0.25}
        self.animator.replace_state_from_sheet(
            0,
            "assets/images/enemies/generated/miniboss_idle_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(192 * scale),
        )
        self.animator.replace_state_from_sheet(
            1,
            "assets/images/enemies/generated/miniboss_walk_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(192 * scale),
        )
        self.animator.replace_state_from_sheet(
            2,
            "assets/images/enemies/generated/miniboss_attack_v2_alpha_master_normalized.png",
            rows=2,
            cols=4,
            frame_height=int(192 * scale),
        )
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
        self.area_attack_radius = max(80, int(120 * scale))
        self.area_attack_damage = 18
        self.area_attack_charge_duration = 45
        self.area_attack_flight_duration = 46
        self.area_attack_explosion_duration = 26
        self.area_attack_cooldown_duration = 210
        self.area_attack_cooldown = 0
        self.area_attack_charge_timer = 0
        self.area_attack_target = None
        self.area_attack_reason = "idle"
        self.area_attack_salvo_count = 3
        self.area_attack_salvo_delay = 28
        self.area_attack_round_count = 2
        self.area_attack_round_delay = 105
        self.area_attack_rounds_remaining = 0
        self.area_attack_next_round_timer = 0
        self.area_attack_latest_player = (self.x, self.y)
        self.area_fire_duration = 240
        self.area_fire_tick_interval = 30
        self.area_fire_damage = 5
        self.area_missiles = []
        self.area_explosions = []
        self.area_fires = []
        self.area_damage_events = []
        self.color = (255, 90, 40)
        self.configure_standard_controller()

    def update_special_movement(self, player_x, player_y, width, height, collision_manager=None, pathfinder=None):
        self.update_area_attacks(width, height, player_x, player_y)
        if self.jump_cooldown > 0:
            self.jump_cooldown -= 1
        if self.area_attack_cooldown > 0:
            self.area_attack_cooldown -= 1

        if self.area_attack_charge_timer > 0 or self.area_attack_next_round_timer > 0:
            self.navigator.clear_path()
            self.navigator.mode = "bombard_charge" if self.area_attack_charge_timer > 0 else "bombard_reload"
            self.state = 2
            countdown = self.area_attack_charge_timer or self.area_attack_next_round_timer
            if countdown <= self.ATTACK_ANIMATION_LEAD_FRAMES:
                self.controller.play("attack")
            return True

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
        self.controller.play("attack")

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
            audio.play_sfx("miniboss_land", "hit")
        return True

    def after_navigation_update(self, player_x, player_y, width, height, pathfinder=None):
        if self.jump_timer > 0 or self.jump_cooldown > 0 or self.area_attack_charge_timer > 0:
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
        self.jump_debug_start = (self.x, self.y)
        self.jump_debug_target = target
        self.jump_player_reference = (player_x, player_y)
        self.jump_landing_valid = was_valid
        self.jump_landing_fallback = used_fallback
        self.jump_landing_reason = reason

        if not was_valid:
            if self.start_area_attack(player_x, player_y, width, height, reason):
                return True
            self.jump_blocked_frames = 0
            self.navigator.mode = "holding_pressure"
            return False

        self.jump_start = (self.x, self.y)
        self.jump_target = target
        self.jump_timer = self.jump_duration
        self.jump_blocked_frames = 0
        self.navigator.clear_path()
        self.navigator.mode = "jumping"
        self.state = 2
        self.controller.play("attack")
        audio.play_sfx("miniboss_jump", "pause")
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

    def start_area_attack(self, player_x, player_y, width, height, reason="inaccessible"):
        if self.area_attack_cooldown > 0 or self.area_attack_charge_timer > 0:
            return False

        self.area_attack_target = self.clamp_area_attack_target((player_x, player_y), width, height)
        self.area_attack_latest_player = self.area_attack_target
        self.area_attack_reason = reason
        self.area_attack_charge_timer = self.area_attack_charge_duration
        self.area_attack_rounds_remaining = self.area_attack_round_count
        self.area_attack_next_round_timer = 0
        attack_duration = (
            self.area_attack_charge_duration
            + self.area_attack_round_delay * max(0, self.area_attack_round_count - 1)
            + self.area_attack_flight_duration
            + self.area_attack_salvo_delay * max(0, self.area_attack_salvo_count - 1)
        )
        self.area_attack_cooldown = max(self.area_attack_cooldown_duration, attack_duration + 45)
        self.jump_blocked_frames = 0
        self.jump_cooldown = max(self.jump_cooldown, 45)
        self.navigator.clear_path()
        self.navigator.mode = "bombard_charge"
        self.state = 2
        audio.play_sfx("missile_charge", "pause")
        return True

    def clamp_area_attack_target(self, target, width, height):
        margin = max(8, int(self.area_attack_radius * 0.25))
        x = max(margin, min(width - margin, target[0]))
        y = max(margin, min(height - margin, target[1]))
        return float(x), float(y)

    def update_area_attacks(self, width, height, player_x=None, player_y=None):
        if player_x is not None and player_y is not None:
            self.area_attack_latest_player = self.clamp_area_attack_target((player_x, player_y), width, height)

        if self.area_attack_charge_timer > 0:
            self.area_attack_charge_timer -= 1
            if self.area_attack_charge_timer <= 0:
                target = self.area_attack_target or self.area_attack_latest_player
                self.launch_area_missiles(width, height, target, round_index=0)
                self.area_attack_target = None
                self.area_attack_rounds_remaining = max(0, self.area_attack_rounds_remaining - 1)
                if self.area_attack_rounds_remaining > 0:
                    self.area_attack_next_round_timer = self.area_attack_round_delay

        if self.area_attack_next_round_timer > 0:
            self.area_attack_next_round_timer -= 1
            if self.area_attack_next_round_timer <= 0 and self.area_attack_rounds_remaining > 0:
                round_index = self.area_attack_round_count - self.area_attack_rounds_remaining
                self.launch_area_missiles(width, height, self.area_attack_latest_player, round_index=round_index)
                self.area_attack_rounds_remaining -= 1
                if self.area_attack_rounds_remaining > 0:
                    self.area_attack_next_round_timer = self.area_attack_round_delay

        for missile in self.area_missiles[:]:
            missile["timer"] -= 1
            if missile["timer"] <= 0:
                self.area_missiles.remove(missile)
                target = missile["target"]
                damage_center = missile.get("damage_center", target)
                self.area_explosions.append(
                    {
                        "x": target[0],
                        "y": target[1],
                        "radius": missile["radius"],
                        "timer": self.area_attack_explosion_duration,
                        "duration": self.area_attack_explosion_duration,
                    }
                )
                self.area_damage_events.append(
                    {
                        "kind": "impact",
                        "x": damage_center[0],
                        "y": damage_center[1],
                        "radius": missile["radius"],
                        "damage": missile["damage"],
                    }
                )
                audio.play_sfx("missile_impact", "hit")
                self.create_fire_zone(damage_center, missile["radius"])

        for explosion in self.area_explosions[:]:
            explosion["timer"] -= 1
            if explosion["timer"] <= 0:
                self.area_explosions.remove(explosion)

        for fire in self.area_fires[:]:
            fire["timer"] -= 1
            fire["tick_timer"] -= 1
            if fire["timer"] <= 0:
                self.area_fires.remove(fire)

    def launch_area_missiles(self, width, height, target_center=None, round_index=0):
        if target_center is None:
            if self.area_attack_target is None:
                return
            target_center = self.area_attack_target

        center = self.clamp_area_attack_target(target_center, width, height)
        targets = self.build_area_salvo_targets(center, width, height, round_index)
        dx = center[0] - self.x
        dy = center[1] - self.y
        distance = max(1.0, math.hypot(dx, dy))
        side_x, side_y = -dy / distance, dx / distance

        for index, target_center in enumerate(targets):
            side = -1 if (index + round_index) % 2 == 0 else 1
            start = (
                self.x + side_x * side * self.radius * 0.45,
                self.y + side_y * side * self.radius * 0.45 - self.radius * 0.2,
            )
            target = (
                target_center[0] + side_x * side * self.area_attack_radius * 0.12,
                target_center[1] + side_y * side * self.area_attack_radius * 0.12,
            )
            duration = self.area_attack_flight_duration + index * self.area_attack_salvo_delay
            self.area_missiles.append(
                {
                    "start": start,
                    "target": target,
                    "damage_center": target_center,
                    "radius": self.area_attack_radius,
                    "damage": self.area_attack_damage,
                    "timer": duration,
                    "duration": duration,
                    "salvo_index": index,
                    "round_index": round_index,
                }
            )

        self.navigator.mode = "bombard_launch"
        audio.play_sfx("missile_launch", "shoot")

    def build_area_salvo_targets(self, center, width, height, round_index=0):
        dx = center[0] - self.x
        dy = center[1] - self.y
        distance = max(1.0, math.hypot(dx, dy))
        forward_x, forward_y = dx / distance, dy / distance
        side_x, side_y = -forward_y, forward_x
        if round_index % 2 == 1:
            side_x, side_y = -side_x, -side_y
        spread = self.area_attack_radius * 0.55
        forward_spread = self.area_attack_radius * 0.25
        raw_targets = [center]
        raw_targets.append((center[0] + side_x * spread + forward_x * forward_spread, center[1] + side_y * spread + forward_y * forward_spread))
        raw_targets.append((center[0] - side_x * spread - forward_x * forward_spread, center[1] - side_y * spread - forward_y * forward_spread))
        return [self.clamp_area_attack_target(target, width, height) for target in raw_targets[: self.area_attack_salvo_count]]

    def create_fire_zone(self, center, radius):
        self.area_fires.append(
            {
                "x": center[0],
                "y": center[1],
                "radius": radius * 0.78,
                "timer": self.area_fire_duration,
                "duration": self.area_fire_duration,
                "tick_timer": self.area_fire_tick_interval,
                "tick_interval": self.area_fire_tick_interval,
                "damage": self.area_fire_damage,
            }
        )
        audio.play_sfx("fire_ignite", "enemy_die_bug", "hit")

    def collect_area_damage_events(self, player):
        hits = []
        for event in self.area_damage_events[:]:
            self.area_damage_events.remove(event)
            distance = math.hypot(player.x - event["x"], player.y - event["y"])
            if distance <= event["radius"] + player.radius * 0.35:
                hits.append({"damage": event["damage"], "x": player.x, "y": player.y, "kind": event.get("kind", "impact")})

        for fire in self.area_fires:
            if fire["tick_timer"] > 0:
                continue
            distance = math.hypot(player.x - fire["x"], player.y - fire["y"])
            if distance <= fire["radius"] + player.radius * 0.25:
                hits.append({"damage": fire["damage"], "x": player.x, "y": player.y, "kind": "fire"})
                fire["tick_timer"] = fire["tick_interval"]
        return hits

    def draw(self, surface, offset_x=0, offset_y=0):
        self.draw_artillery_charge(surface, offset_x, offset_y)
        super().draw(surface, offset_x, offset_y)
        self.draw_area_projectiles(surface, offset_x, offset_y)

    def draw_area_ground_effects(self, surface, offset_x=0, offset_y=0):
        self.draw_area_warnings(surface, offset_x, offset_y)
        for explosion in self.area_explosions:
            self.draw_area_explosion(surface, explosion, offset_x, offset_y)

    def draw_area_warnings(self, surface, offset_x=0, offset_y=0):
        for fire in self.area_fires:
            self.draw_fire_zone(surface, fire, offset_x, offset_y)

        if self.area_attack_target is not None:
            progress = 1.0 - (self.area_attack_charge_timer / max(1, self.area_attack_charge_duration))
            self.draw_ground_warning(surface, self.area_attack_target, self.area_attack_radius, progress, offset_x, offset_y)

        if self.area_attack_next_round_timer > 0 and self.area_attack_rounds_remaining > 0:
            progress = 1.0 - (self.area_attack_next_round_timer / max(1, self.area_attack_round_delay))
            self.draw_ground_warning(surface, self.area_attack_latest_player, self.area_attack_radius, progress, offset_x, offset_y)

        for missile in self.area_missiles:
            progress = 1.0 - (missile["timer"] / max(1, missile["duration"]))
            self.draw_ground_warning(surface, missile.get("damage_center", missile["target"]), missile["radius"], progress, offset_x, offset_y)

    def draw_pixel_disc(self, surface, center, radius, color, pixel_size=6, ring=False, ring_width=2, checker=False):
        radius = int(radius)
        pixel_size = max(2, int(pixel_size))
        cx, cy = int(center[0]), int(center[1])
        outer = radius * radius
        inner_radius = max(0, radius - pixel_size * ring_width)
        inner = inner_radius * inner_radius
        phase = (pygame.time.get_ticks() // 120) % 4

        for y in range(-radius, radius + pixel_size, pixel_size):
            for x in range(-radius, radius + pixel_size, pixel_size):
                distance = x * x + y * y
                if distance > outer:
                    continue
                if ring and distance < inner:
                    continue
                if checker and ((x // pixel_size + y // pixel_size + phase) % 5 == 0):
                    continue
                pygame.draw.rect(surface, color, (cx + x, cy + y, pixel_size, pixel_size))

    def draw_ground_warning(self, surface, center, radius, progress, offset_x=0, offset_y=0):
        pixel = 6
        radius = int(radius)
        size = int(radius * 2 + pixel * 5)
        warning = pygame.Surface((size, size), pygame.SRCALPHA)
        local = (size // 2, size // 2)
        progress = max(0.0, min(1.0, progress))
        fill_alpha = int(32 + 44 * progress)
        ring_alpha = int(130 + 90 * abs(math.sin(pygame.time.get_ticks() / 90.0)))

        self.draw_pixel_disc(warning, local, radius, (255, 55, 35, fill_alpha), pixel_size=pixel, checker=True)
        self.draw_pixel_disc(warning, local, radius, (255, 210, 80, ring_alpha), pixel_size=pixel, ring=True, ring_width=2)
        inner_radius = max(8, int(radius * (1.0 - progress * 0.72)))
        self.draw_pixel_disc(warning, local, inner_radius, (255, 70, 45, 190), pixel_size=5, ring=True, ring_width=1)

        mark = max(8, int(radius * 0.18))
        pygame.draw.rect(warning, (255, 230, 120, 160), (local[0] - 3, local[1] - radius, 6, mark))
        pygame.draw.rect(warning, (255, 230, 120, 160), (local[0] - 3, local[1] + radius - mark, 6, mark))
        pygame.draw.rect(warning, (255, 230, 120, 160), (local[0] - radius, local[1] - 3, mark, 6))
        pygame.draw.rect(warning, (255, 230, 120, 160), (local[0] + radius - mark, local[1] - 3, mark, 6))

        x = int(center[0] + offset_x - size / 2)
        y = int(center[1] + offset_y - size / 2)
        surface.blit(warning, (x, y))

    def draw_fire_zone(self, surface, fire, offset_x=0, offset_y=0):
        radius = int(fire["radius"])
        pixel = 6
        size = int(radius * 2 + pixel * 5)
        fire_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        local = (size // 2, size // 2)
        life = max(0.0, min(1.0, fire["timer"] / max(1, fire["duration"])))
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 95.0)

        self.draw_pixel_disc(fire_surf, local, radius, (165, 35, 16, int(70 * life + pulse * 28)), pixel_size=pixel, checker=True)
        self.draw_pixel_disc(fire_surf, local, radius * 0.72, (255, 82, 24, int(82 + pulse * 44)), pixel_size=pixel, checker=True)
        self.draw_pixel_disc(fire_surf, local, radius * 0.42, (255, 174, 44, int(70 + pulse * 60)), pixel_size=5, checker=True)
        self.draw_pixel_disc(fire_surf, local, radius, (95, 20, 10, int(95 * life)), pixel_size=pixel, ring=True, ring_width=1)

        ember_count = 12
        for index in range(ember_count):
            angle = (math.tau / ember_count) * index + pygame.time.get_ticks() / 650.0
            ember_radius = radius * (0.18 + 0.72 * ((index * 37) % 100) / 100.0)
            ember_x = local[0] + math.cos(angle) * ember_radius
            ember_y = local[1] + math.sin(angle * 1.35) * ember_radius * 0.72
            ember_size = 3 + (index % 2) * 2
            pygame.draw.rect(fire_surf, (255, 220, 80, int(90 * life)), (int(ember_x), int(ember_y), ember_size, ember_size))

        surface.blit(fire_surf, (int(fire["x"] + offset_x - size / 2), int(fire["y"] + offset_y - size / 2)))

    def draw_artillery_charge(self, surface, offset_x=0, offset_y=0):
        if self.area_attack_charge_timer <= 0:
            return
        progress = 1.0 - (self.area_attack_charge_timer / max(1, self.area_attack_charge_duration))
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 80.0)
        radius = int(self.radius * (0.85 + progress * 0.55 + pulse * 0.12))
        glow = pygame.Surface((radius * 2 + 18, radius * 2 + 18), pygame.SRCALPHA)
        center = (glow.get_width() // 2, glow.get_height() // 2)
        self.draw_pixel_disc(glow, center, radius, (255, 95, 30, int(48 + progress * 82)), pixel_size=7, checker=True)
        self.draw_pixel_disc(glow, center, max(8, int(radius * 0.62)), (255, 230, 90, int(105 + pulse * 90)), pixel_size=6, ring=True, ring_width=1)
        surface.blit(glow, (int(self.x + offset_x - center[0]), int(self.y + offset_y - center[1])))

        for side in (-1, 1):
            launcher_x = int(self.x + offset_x + side * self.radius * 0.45)
            launcher_y = int(self.y + offset_y - self.radius * 0.2)
            pygame.draw.rect(surface, (95, 58, 36), (launcher_x - 9, launcher_y - 7, 18, 14))
            pygame.draw.rect(surface, (255, 175, 60), (launcher_x - 6, launcher_y - 4, 12, 8))
            pygame.draw.rect(surface, (255, 255, 180), (launcher_x - 3, launcher_y - 2, 6, 4))

    def draw_area_projectiles(self, surface, offset_x=0, offset_y=0):
        for missile in self.area_missiles:
            self.draw_rocket(surface, missile, offset_x, offset_y)

    def missile_position(self, missile):
        progress = 1.0 - (missile["timer"] / max(1, missile["duration"]))
        progress = max(0.0, min(1.0, progress))
        sx, sy = missile["start"]
        tx, ty = missile["target"]
        x = sx + (tx - sx) * progress
        y = sy + (ty - sy) * progress
        lift = math.sin(progress * math.pi) * max(80, missile["radius"] * 1.05)
        return x, y - lift, progress

    def draw_rocket(self, surface, missile, offset_x=0, offset_y=0):
        x, y, progress = self.missile_position(missile)
        sx, sy = missile["start"]
        tx, ty = missile["target"]
        angle = math.atan2(ty - sy, tx - sx)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        side_x, side_y = -sin_a, cos_a
        origin_x = x + offset_x
        origin_y = y + offset_y

        def block(local_forward, local_side, w, h, color):
            center_x = origin_x + cos_a * local_forward + side_x * local_side
            center_y = origin_y + sin_a * local_forward + side_y * local_side
            pygame.draw.rect(surface, color, (int(center_x - w / 2), int(center_y - h / 2), int(w), int(h)))

        block(10, 0, 8, 8, (230, 45, 36))
        block(3, 0, 12, 8, (255, 207, 95))
        block(-5, 0, 12, 10, (190, 38, 34))
        block(-8, 7, 7, 6, (120, 32, 38))
        block(-8, -7, 7, 6, (120, 32, 38))
        block(-15, 0, 10, 8, (255, 120, 34))
        block(-20, 0, 7, 6, (255, 226, 88))

        trail_steps = 5
        for step in range(1, trail_steps + 1):
            t = max(0.0, progress - step * 0.045)
            trail_x = sx + (tx - sx) * t
            trail_y = sy + (ty - sy) * t - math.sin(t * math.pi) * max(80, missile["radius"] * 1.05)
            size = max(3, 10 - step * 2)
            pygame.draw.rect(
                surface,
                (255, max(70, 150 - step * 16), 38),
                (int(trail_x + offset_x - size / 2), int(trail_y + offset_y - size / 2), size, size),
            )

    def draw_area_explosion(self, surface, explosion, offset_x=0, offset_y=0):
        progress = 1.0 - (explosion["timer"] / max(1, explosion["duration"]))
        radius = int(explosion["radius"] * (0.35 + progress * 0.85))
        pixel = 7
        size = int(explosion["radius"] * 2.5 + pixel * 4)
        boom = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        alpha = max(0, int(210 * (1.0 - progress)))
        self.draw_pixel_disc(boom, center, radius, (255, 175, 42, alpha), pixel_size=pixel, checker=True)
        self.draw_pixel_disc(boom, center, max(8, int(radius * 0.72)), (255, 68, 32, max(0, alpha - 26)), pixel_size=pixel, ring=True, ring_width=1)
        self.draw_pixel_disc(boom, center, max(6, int(radius * 0.34)), (255, 236, 112, max(0, alpha - 12)), pixel_size=5, checker=True)
        shard_count = 10
        for index in range(shard_count):
            angle = (math.tau / shard_count) * index + progress * 1.4
            shard_distance = radius * (0.35 + progress * 0.55)
            shard_size = max(3, int(8 * (1.0 - progress)))
            shard_x = center[0] + math.cos(angle) * shard_distance
            shard_y = center[1] + math.sin(angle) * shard_distance
            pygame.draw.rect(boom, (255, 102, 34, max(0, alpha - 30)), (int(shard_x), int(shard_y), shard_size, shard_size))
        surface.blit(boom, (int(explosion["x"] + offset_x - size / 2), int(explosion["y"] + offset_y - size / 2)))

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
            if self.action_timer >= 150 - self.ATTACK_ANIMATION_LEAD_FRAMES:
                self.controller.play("attack")
        else:
            # Shoot
            angle = math.atan2(player_y - self.y, player_x - self.x)
            self.bullets.append(EnemyBullet(self.x, self.y, angle, speed=6, radius=10, b_type="miniboss"))
            audio.play_sfx("enemy_shoot", "shoot")
            self.action_timer = 0
            self.state = 0

class Boss(Enemy):
    SCALE_FACTOR = 1.15  # ajuste visual sobre la escala del nivel
    PHASE_TWO_HEALTH_RATIO = 0.5
    PHASE_TRANSITION_FRAMES = 90
    FAN_SPREAD_DEGREES = (-18, -6, 6, 18)
    ATTACK_ANIMATION_LEAD_FRAMES = 16  # frame de cañón cargado antes del disparo

    def __init__(self, x, y, scale=1.0):
        scale *= self.SCALE_FACTOR
        super().__init__(x, y, 105, 0.8, 500, "assets/images/enemies/boss_sheet_normalized.png", 288, cols=8, rows=4, scale=scale)
        self.ai_smartness = 0.7
        self.separation_weight = 0.2
        self.ignores_map_collision = True
        self.animator.state_speeds = {0: 0.06, 1: 0.12, 2: 0.25}
        for state, name in enumerate(("idle", "walk", "attack")):
            self.animator.replace_state_from_sheet(
                state, f"assets/images/enemies/generated/boss_{name}_v2_alpha_master_normalized.png",
                rows=2, cols=4, frame_height=int(288 * scale),
            )
        self.configure_standard_controller()
        self.action_timer = 0
        self.phase = 1
        self.phase_transition_timer = 0
        self.next_attack = "radial"
        self.telegraph_angle = 0.0
        self.fan_salvos_remaining = 0
        self.fan_salvo_timer = 0
        

    def get_visual_y_offset(self):
        return 12 + math.sin(pygame.time.get_ticks() / 350.0) * 5

    def draw_movement_shadow(self, surface, offset_x=0, offset_y=0, visual_y_offset=0):
        shadow_w = max(32, int(self.radius * 1.45))
        shadow_h = max(12, int(self.radius * 0.38))
        shadow = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 95), shadow.get_rect())
        surface.blit(shadow, (int(self.x + offset_x - shadow_w / 2), int(self.y + offset_y + self.radius * 0.55 - shadow_h / 2)))

    def _start_phase_two(self):
        self.phase = 2
        self.phase_transition_timer = self.PHASE_TRANSITION_FRAMES
        self.action_timer = 0
        self.next_attack = "fan"
        self.fan_salvos_remaining = 0
        self.fan_salvo_timer = 0
        self.bullets.clear()
        self.state = 2
        self.controller.play("attack", restart=True)
        audio.play_sfx("boss_phase2_voice")

    def _fire_radial_attack(self):
        for i in range(8):
            angle = i * (math.pi / 4)
            self.bullets.append(EnemyBullet(self.x, self.y, angle, speed=4, radius=12, b_type="boss"))
        audio.play_sfx("enemy_shoot", "shoot")

    def _begin_fan_attack(self, player_x, player_y):
        self.telegraph_angle = math.atan2(player_y - self.y, player_x - self.x)
        self.fan_salvos_remaining = 3
        self.fan_salvo_timer = 0

    def _update_fan_salvos(self, player_x, player_y):
        self.state = 2
        if self.fan_salvo_timer > 0:
            self.fan_salvo_timer -= 1
            return

        center_angle = math.atan2(player_y - self.y, player_x - self.x)
        self.telegraph_angle = center_angle
        for spread in self.FAN_SPREAD_DEGREES:
            angle = center_angle + math.radians(spread)
            self.bullets.append(EnemyBullet(self.x, self.y, angle, speed=5.5, radius=12, b_type="boss"))
        audio.play_sfx("enemy_shoot", "shoot")
        self.fan_salvos_remaining -= 1
        if self.fan_salvos_remaining > 0:
            self.fan_salvo_timer = 14
        else:
            self.action_timer = 0

    def _move_towards_player(self, player_x, player_y):
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1

    def move_logic(self, player_x, player_y):
        if self.phase == 1 and self.hp <= self.max_hp * self.PHASE_TWO_HEALTH_RATIO:
            self._start_phase_two()
            return

        if self.phase_transition_timer > 0:
            self.phase_transition_timer -= 1
            self.state = 2
            self.controller.play("attack")
            return

        if self.fan_salvos_remaining > 0:
            self._update_fan_salvos(player_x, player_y)
            return

        self.action_timer += 1

        move_frames = 150 if self.phase == 1 else 90
        telegraph_end = move_frames + (40 if self.phase == 1 else 35)
        if self.action_timer < move_frames:
            self._move_towards_player(player_x, player_y)
        elif self.action_timer < telegraph_end:
            self.state = 2
            if self.action_timer >= telegraph_end - self.ATTACK_ANIMATION_LEAD_FRAMES:
                self.controller.play("attack")
            self.telegraph_angle = math.atan2(player_y - self.y, player_x - self.x)
        else:
            if self.phase == 2 and self.next_attack == "fan":
                self._begin_fan_attack(player_x, player_y)
                self.next_attack = "radial"
            else:
                self._fire_radial_attack()
                if self.phase == 2:
                    self.next_attack = "fan"
            self.action_timer = 0
            self.state = 0

    def draw(self, surface, offset_x=0, offset_y=0):
        cx = int(self.x + offset_x)
        cy = int(self.y + offset_y - self.get_visual_y_offset())
        fx = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        if self.phase_transition_timer > 0:
            progress = 1.0 - self.phase_transition_timer / self.PHASE_TRANSITION_FRAMES
            radius = int(75 + progress * 125)
            alpha = max(20, int(180 * (1.0 - progress)))
            pygame.draw.circle(fx, (40, 205, 255, alpha), (cx, cy), radius, 4)
            pygame.draw.circle(fx, (218, 42, 255, alpha // 2), (cx, cy), max(12, radius - 14), 3)

        move_frames = 150 if self.phase == 1 else 90
        telegraph_end = move_frames + (40 if self.phase == 1 else 35)
        fan_telegraph = (self.phase == 2 and self.next_attack == "fan" and
                         move_frames <= self.action_timer < telegraph_end)
        if fan_telegraph:
            for spread in (-24, 0, 24):
                angle = self.telegraph_angle + math.radians(spread)
                end = (cx + math.cos(angle) * 420, cy + math.sin(angle) * 420)
                pygame.draw.line(fx, (55, 215, 255, 105), (cx, cy), end, 2)

        surface.blit(fx, (0, 0))
        super().draw(surface, offset_x, offset_y)


# Todos los tipos que pueden aparecer en combate (enemigos + jefes).
COMBAT_ENEMY_CLASSES = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy, MiniBoss, Boss]


def preload_combat_assets(scales=(1.0,)):
    """Precalienta el caché de sprites de todos los enemigos y jefes.

    Instancia una vez cada clase (objetos desechables) para forzar la carga y el
    corte de sus spritesheets, evitando el tirón la primera vez que aparecen en
    combate. Como el corte nativo se cachea de forma independiente de la escala,
    basta con una escala; las demás solo pagan un reescalado barato en su primer uso.
    """
    for scale in scales:
        for enemy_cls in COMBAT_ENEMY_CLASSES:
            try:
                enemy_cls(0, 0, scale=scale)
            except Exception as e:
                print(f"Preload fallo para {enemy_cls.__name__}: {e}")
