import pygame
import math
import random
from animator import Animator

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
        
        
        if frame_height is None:
            frame_height = frame_width
        self.animator = Animator(sheet_path, int(frame_width * scale), int(frame_height * scale), rows, cols, 0.15)
        self.color = (255, 50, 50)

    def sync_rect_to_position(self):
        self.rect.center = (int(round(self.x)), int(round(self.y)))

    def sync_position_to_rect(self):
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)

    def update(self, player_x, player_y, width, height, collision_manager=None):
        old_x, old_y = self.x, self.y
        self.move_logic(player_x, player_y)
        
        # Evasión general de obstáculos para todos los enemigos
        if self.last_collision.get("x") or self.last_collision.get("y"):
            if self.evasion_timer <= 0:
                self.evasion_timer = 40
                self.evasion_dir = random.choice([-1, 1])

        if self.evasion_timer > 0:
            self.evasion_timer -= 1
            if self.last_collision.get("x"):
                if abs(player_y - self.y) < 25:
                    self.y += 3.0 * self.evasion_dir
                else:
                    self.y += 3.0 if player_y >= self.y else -3.0
            if self.last_collision.get("y"):
                if abs(player_x - self.x) < 25:
                    self.x += 3.0 * self.evasion_dir
                else:
                    self.x += 3.0 if player_x >= self.x else -3.0
            
        dx = self.x - old_x
        dy = self.y - old_y

        if collision_manager:
            self.x, self.y = old_x, old_y
            self.sync_rect_to_position()
            self.last_collision = collision_manager.move_and_collide(self, dx, dy)
        else:
            self.sync_rect_to_position()
            self.last_collision = {"x": False, "y": False}
        
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        # Update bullets
        for b in self.bullets[:]:
            b.update()
            if b.is_offscreen(width, height):
                self.bullets.remove(b)

    def move_logic(self, player_x, player_y):
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1 # Moving

    def draw(self, surface, offset_x=0, offset_y=0):
        self.animator.set_state(self.state)
        self.animator.update()
        image = self.animator.get_current_image()
        
        dx = int(self.x + offset_x)
        dy = int(self.y + offset_y)
        
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
        self.animator.animation_speed = 0.08
class SpaghettiEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 29, 1.5, 40, "assets/images/enemies/spaghetti_sheet.png", 72, scale=scale)
    def move_logic(self, player_x, player_y):
        # Erratic movement
        angle = math.atan2(player_y - self.y, player_x - self.x) + random.uniform(-0.5, 0.5)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1

class MemoryLeakEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 24, 2.0, 30, "assets/images/enemies/leak_sheet.png", 48, scale=scale)

class DeadlineEnemy(Enemy):
    def __init__(self, x, y, scale=1.0):
        super().__init__(x, y, 36, 1.0, 25, "assets/images/enemies/deadline_sheet.png", 96, scale=scale)
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
        self.action_timer = 0
        self.animator.animation_speed = 0.08 # Animación un poco más lenta
        
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
        self.action_timer = 0
        
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
