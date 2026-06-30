import pygame
import math
import random

font_bullet = None
BULLET_0_IMG = None
BULLET_1_IMG = None

def init_player_assets():
    global font_bullet, BULLET_0_IMG, BULLET_1_IMG
    try:
        font_bullet = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 32)
    except:
        font_bullet = pygame.font.SysFont("Consolas", 24)
        
    try:
        b0 = pygame.image.load("assets/images/player/0.png").convert_alpha()
        BULLET_0_IMG = pygame.transform.scale(b0, (24, 24))
    except:
        BULLET_0_IMG = None
    try:
        b1 = pygame.image.load("assets/images/player/1.png").convert_alpha()
        BULLET_1_IMG = pygame.transform.scale(b1, (24, 24))
    except Exception as e:
        print("No se pudieron cargar los sprites de bala:", e)

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 30 # Escalado 1.5x
        self.rect = pygame.Rect(0, 0, 51, 57)
        self.sync_rect_to_position()
        self.speed = 5
        self.hp = 100
        self.max_hp = 100
        self.max_energy = 6
        self.energy = 6
        self.color = (0, 255, 255)
        self.bullets = []
        self.shoot_cooldown = 0
        
        from animator import Animator
        # Tamaño escalado 1.5x (96x96)
        self.animator = Animator("assets/images/player/player_sheet.png", 96, 96, rows=3, cols=4, animation_speed=0.10)
        self.state = 0 # 0: Idle, 1: Walk, 2: Attack
        self.flip = False

    def sync_rect_to_position(self):
        self.rect.center = (int(round(self.x)), int(round(self.y)))

    def sync_position_to_rect(self):
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)

    def move(self, keys, width, height, collision_manager=None):
        moved = False
        dx = 0
        dy = 0

        if keys[pygame.K_w]:
            dy -= 1
            moved = True
        if keys[pygame.K_s]:
            dy += 1
            moved = True
        if keys[pygame.K_a]:
            dx -= 1
            moved = True
            self.flip = True # Mirar a la izquierda
        if keys[pygame.K_d]:
            dx += 1
            moved = True
            self.flip = False # Mirar a la derecha

        if dx != 0 and dy != 0:
            diagonal_factor = 1 / math.sqrt(2)
            dx *= diagonal_factor
            dy *= diagonal_factor

        dx *= self.speed
        dy *= self.speed

        if collision_manager:
            collision_manager.move_and_collide(self, dx, dy)
        else:
            self.x += dx
            self.y += dy
            self.sync_rect_to_position()
            self.rect.clamp_ip(pygame.Rect(0, 0, width, height))
            self.sync_position_to_rect()

        if moved and self.shoot_cooldown == 0:
            self.state = 1 # Walk
        elif self.shoot_cooldown == 0:
            self.state = 0 # Idle

    def shoot(self, target_x, target_y):
        if self.shoot_cooldown == 0:
            angle = math.atan2(target_y - self.y, target_x - self.x)
            self.bullets.append(Bullet(self.x, self.y, angle))
            self.shoot_cooldown = 15
            self.state = 2 # Attack

    def shoot_angle(self, angle):
        if self.shoot_cooldown == 0:
            self.bullets.append(Bullet(self.x, self.y, angle))
            self.shoot_cooldown = 15
            self.state = 2 # Attack

    def update_bullets(self, width, height):
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
            if self.shoot_cooldown == 0:
                self.state = 0 # Volver a Idle al terminar de atacar
                
        for b in self.bullets[:]:
            b.update()
            if b.is_offscreen(width, height):
                self.bullets.remove(b)

    def draw(self, surface, offset_x=0, offset_y=0):
        self.animator.set_state(self.state)
        self.animator.update()
        image = self.animator.get_current_image()
        
        if image:
            if getattr(self, 'flip', False):
                image = pygame.transform.flip(image, True, False)
            rect = image.get_rect(center=(int(self.x + offset_x), int(self.y + offset_y)))
            surface.blit(image, rect)
        else:
            pygame.draw.circle(surface, self.color, (int(self.x + offset_x), int(self.y + offset_y)), self.radius)
            
        # Dibujar balas (lágrimas)
        for b in self.bullets:
            b.draw(surface, offset_x, offset_y)

class Bullet:
    def __init__(self, x, y, angle):
        self.x = x
        self.y = y
        self.speed = 10
        self.radius = 8 # Slightly larger radius for collision
        self.dx = math.cos(angle) * self.speed
        self.dy = math.sin(angle) * self.speed
        
        global BULLET_0_IMG, BULLET_1_IMG
        if BULLET_0_IMG and BULLET_1_IMG:
            self.image = random.choice([BULLET_0_IMG, BULLET_1_IMG])
        else:
            self.image = None
            self.text = random.choice(["0", "1"])
            self.color = (0, 255, 255) # Cyan color to match player

    def update(self):
        self.x += self.dx
        self.y += self.dy

    def draw(self, surface, offset_x=0, offset_y=0):
        if hasattr(self, 'image') and self.image:
            rect = self.image.get_rect(center=(int(self.x + offset_x), int(self.y + offset_y)))
            surface.blit(self.image, rect)
        else:
            pygame.draw.circle(surface, self.color, (int(self.x + offset_x), int(self.y + offset_y)), self.radius)
            if font_bullet:
                text_surf = font_bullet.render(self.text, True, self.color)
                shadow = font_bullet.render(self.text, True, (0, 50, 50))
                text_rect = text_surf.get_rect(center=(int(self.x + offset_x), int(self.y + offset_y)))
                
                surface.blit(shadow, (text_rect.x + 2, text_rect.y + 2))
                surface.blit(text_surf, text_rect)

    def is_offscreen(self, w, h):
        return self.x < 0 or self.x > w or self.y < 0 or self.y > h
