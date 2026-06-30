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

    def draw(self, surface):
        if self.b_type == "miniboss":
            # Examen reprobado (papel con 'F')
            pygame.draw.rect(surface, (240, 240, 240), (self.x - 8, self.y - 12, 16, 24))
            pygame.draw.rect(surface, (0, 0, 0), (self.x - 8, self.y - 12, 16, 24), 1)
            # Líneas simulando texto
            pygame.draw.line(surface, (150, 150, 150), (self.x - 5, self.y - 8), (self.x + 5, self.y - 8))
            pygame.draw.line(surface, (150, 150, 150), (self.x - 5, self.y - 4), (self.x + 5, self.y - 4))
            # Una 'F' roja gruesa
            pygame.draw.line(surface, (255, 0, 0), (self.x - 4, self.y + 2), (self.x - 4, self.y + 10), 2)
            pygame.draw.line(surface, (255, 0, 0), (self.x - 4, self.y + 2), (self.x + 3, self.y + 2), 2)
            pygame.draw.line(surface, (255, 0, 0), (self.x - 4, self.y + 6), (self.x + 1, self.y + 6), 2)
            
        elif self.b_type == "boss":
            # Tomo de tesis gruesa con sello dorado
            pygame.draw.rect(surface, (139, 0, 0), (self.x - 12, self.y - 16, 24, 32)) # Tapa roja
            pygame.draw.rect(surface, (255, 215, 0), (self.x - 12, self.y - 16, 24, 32), 2) # Borde dorado
            pygame.draw.rect(surface, (220, 220, 220), (self.x + 8, self.y - 14, 4, 28)) # Páginas blancas laterales
            # Texto cruzado o sello dorado en el centro
            pygame.draw.circle(surface, (255, 215, 0), (int(self.x - 2), int(self.y)), 6)
            
        else:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 1)

    def is_offscreen(self, w, h):
        return self.x < 0 or self.x > w or self.y < 0 or self.y > h

class Enemy:
    def __init__(self, x, y, radius, speed, hp, sheet_path, frame_size, cols=4, rows=3):
        self.x = x
        self.y = y
        self.radius = radius
        self.speed = speed
        self.hp = hp
        self.max_hp = hp
        self.attack_cooldown = 0
        self.state = 1 # 1: Move
        self.bullets = []
        
        self.animator = Animator(sheet_path, frame_size, frame_size, rows, cols, 0.15)
        self.color = (255, 50, 50)

    def update(self, player_x, player_y, width, height):
        self.move_logic(player_x, player_y)
        
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

    def draw(self, surface):
        self.animator.set_state(self.state)
        self.animator.update()
        image = self.animator.get_current_image()
        
        if image:
            rect = image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(image, rect)
        else:
            pygame.draw.rect(surface, self.color, (int(self.x - self.radius), int(self.y - self.radius), self.radius*2, self.radius*2))
        
        # Barra de vida
        hp_ratio = max(0, self.hp / self.max_hp)
        bar_w = self.radius * 2
        pygame.draw.rect(surface, (255, 0, 0), (int(self.x - self.radius), int(self.y - self.radius - 10), bar_w, 4))
        pygame.draw.rect(surface, (0, 255, 0), (int(self.x - self.radius), int(self.y - self.radius - 10), bar_w * hp_ratio, 4))

        # Dibujar balas enemigas
        for b in self.bullets:
            b.draw(surface)

    def collides_with_bullet(self, bullet):
        dist = math.hypot(self.x - bullet.x, self.y - bullet.y)
        return dist < (self.radius + bullet.radius)

    def collides_with_player(self, player):
        dist = math.hypot(self.x - player.x, self.y - player.y)
        return dist < (self.radius + player.radius)

# ---- Normal Enemies ----

class BugEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 24, 3.0, 20, "assets/bug_sheet.png", 64, cols=6)
        self.animator.animation_speed = 0.08
class SpaghettiEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 26, 1.5, 40, "assets/spaghetti_sheet.png", 64)
    def move_logic(self, player_x, player_y):
        # Erratic movement
        angle = math.atan2(player_y - self.y, player_x - self.x) + random.uniform(-0.5, 0.5)
        self.x += math.cos(angle) * self.speed
        self.y += math.sin(angle) * self.speed
        self.state = 1

class MemoryLeakEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 16, 2.0, 30, "assets/leak_sheet.png", 32)

class DeadlineEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 24, 1.0, 25, "assets/deadline_sheet.png", 64)
    def move_logic(self, player_x, player_y):
        dist = math.hypot(player_x - self.x, player_y - self.y)
        speed = 4.0 if dist < 150 else 1.0
        angle = math.atan2(player_y - self.y, player_x - self.x)
        self.x += math.cos(angle) * speed
        self.y += math.sin(angle) * speed
        self.state = 1 if speed == 1.0 else 2

    def draw(self, surface):
        # Efecto visual de enfado / aceleración (aura roja pulsante)
        if self.state == 2:
            pulse = (math.sin(pygame.time.get_ticks() / 100.0) + 1) / 2.0
            glow_radius = int(self.radius * (1.2 + 0.5 * pulse))
            glow_surf = pygame.Surface((glow_radius*2, glow_radius*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 50, 50, int(150 * pulse)), (glow_radius, glow_radius), glow_radius)
            surface.blit(glow_surf, (int(self.x - glow_radius), int(self.y - glow_radius)))
            
        super().draw(surface)

# ---- Bosses ----

class MiniBoss(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 60, 1.2, 150, "assets/miniboss_sheet.png", 128)
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
    def __init__(self, x, y):
        super().__init__(x, y, 70, 0.8, 500, "assets/boss_sheet.png", 192, cols=8, rows=4)
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
