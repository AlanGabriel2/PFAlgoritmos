import pygame
import math
import random

PLAYER_IMG = None
font_bullet = None
BULLET_0_IMG = None
BULLET_1_IMG = None

def init_player_assets():
    global PLAYER_IMG, font_bullet, BULLET_0_IMG, BULLET_1_IMG
    try:
        PLAYER_IMG = pygame.image.load("assets/player.png").convert_alpha()
        PLAYER_IMG = pygame.transform.scale(PLAYER_IMG, (64, 64))
    except Exception as e:
        print("No se pudo cargar la imagen del jugador:", e)
        
    try:
        font_bullet = pygame.font.Font("assets/VT323-Regular.ttf", 32)
    except:
        font_bullet = pygame.font.SysFont("Consolas", 24)
        
    try:
        b0 = pygame.image.load("assets/0.png").convert_alpha()
        BULLET_0_IMG = pygame.transform.scale(b0, (24, 24))
        
        b1 = pygame.image.load("assets/1.png").convert_alpha()
        BULLET_1_IMG = pygame.transform.scale(b1, (24, 24))
    except Exception as e:
        print("No se pudieron cargar los sprites de bala:", e)

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 24 # Aumentamos el radio de colisión porque el sprite es más grande
        self.speed = 5
        self.hp = 100
        self.max_hp = 100
        self.max_energy = 6
        self.energy = 6
        self.color = (0, 255, 255)
        self.bullets = []
        self.shoot_cooldown = 0
        
        from animator import Animator
        # Volvemos a la configuración original de 3 estados sin transpose
        self.animator = Animator("assets/player_sheet.png", 64, 64, rows=3, cols=4, animation_speed=0.10)
        self.state = 0 # 0: Idle, 1: Move, 2: Attack
        self.flip = False

    def move(self, keys, width, height):
        moved = False
        if keys[pygame.K_w]:
            self.y -= self.speed
            moved = True
        if keys[pygame.K_s]:
            self.y += self.speed
            moved = True
        if keys[pygame.K_a]:
            self.x -= self.speed
            moved = True
            self.flip = True # Mirar a la izquierda
        if keys[pygame.K_d]:
            self.x += self.speed
            moved = True
            self.flip = False # Mirar a la derecha

        if moved and self.shoot_cooldown == 0:
            self.state = 1 # Walk
        elif self.shoot_cooldown == 0:
            self.state = 0 # Idle

        # Restringir a los límites de la habitación
        if self.x < self.radius: self.x = self.radius
        if self.y < self.radius: self.y = self.radius
        if self.x > width - self.radius: self.x = width - self.radius
        if self.y > height - self.radius: self.y = height - self.radius

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

    def draw(self, surface):
        self.animator.set_state(self.state)
        self.animator.update()
        image = self.animator.get_current_image()
        
        if image:
            if getattr(self, 'flip', False):
                image = pygame.transform.flip(image, True, False)
            rect = image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(image, rect)
        else:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
            
        # Dibujar balas (lágrimas)
        for b in self.bullets:
            b.draw(surface)

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

    def draw(self, surface):
        if hasattr(self, 'image') and self.image:
            rect = self.image.get_rect(center=(int(self.x), int(self.y)))
            surface.blit(self.image, rect)
        else:
            global font_bullet
            if font_bullet is None:
                font_bullet = pygame.font.SysFont("Consolas", 24)
                
            text_surf = font_bullet.render(self.text, True, self.color)
            
            # Sombra para que resalte
            shadow = font_bullet.render(self.text, True, (0, 50, 50))
            text_rect = text_surf.get_rect(center=(int(self.x), int(self.y)))
            
            surface.blit(shadow, (text_rect.x + 2, text_rect.y + 2))
            surface.blit(text_surf, text_rect)

    def is_offscreen(self, w, h):
        return self.x < 0 or self.x > w or self.y < 0 or self.y > h
