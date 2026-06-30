import pygame
import os
import math

pygame.init()
pygame.display.set_mode((1, 1), pygame.HIDDEN)

ASSETS_DIR = "assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

def create_spritesheet(filename, width, height, rows, cols, draw_fn):
    surface = pygame.Surface((width * cols, height * rows), pygame.SRCALPHA)
    for row in range(rows):
        for col in range(cols):
            rect = pygame.Rect(col * width, row * height, width, height)
            draw_fn(surface, rect, row, col)
    pygame.image.save(surface, os.path.join(ASSETS_DIR, filename))

# 1. Player (Hacker)
def draw_player(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    # Base body
    pygame.draw.circle(surface, (0, 200, 200), (cx, cy), 12)
    
    # Animation effects
    if row == 0: # Idle (breathing)
        offset = math.sin(col * math.pi/2) * 2
        pygame.draw.circle(surface, (0, 255, 255), (cx, int(cy + offset)), 10)
    elif row == 1: # Move (bobbing)
        offset = (col % 2) * 4 - 2
        pygame.draw.circle(surface, (0, 255, 255), (cx, int(cy + offset)), 10)
    elif row == 2: # Attack (typing/laptop glowing)
        pygame.draw.circle(surface, (0, 255, 255), (cx, cy), 10)
        pygame.draw.rect(surface, (255, 255, 255), (cx-6, cy+4, 12, 6)) # Laptop
        if col % 2 == 0:
            pygame.draw.rect(surface, (0, 255, 0), (cx-4, cy+5, 8, 4)) # Screen glow

# 2. Bug Enemy (Syntax Error)
def draw_bug(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    pygame.draw.ellipse(surface, (200, 50, 50), (cx-10, cy-14, 20, 28))
    # Legs moving
    leg_offset = (col % 2) * 4 - 2 if row == 1 else 0
    pygame.draw.line(surface, (255, 0, 0), (cx-10, cy-5), (cx-15, cy-5 + leg_offset), 2)
    pygame.draw.line(surface, (255, 0, 0), (cx+10, cy-5), (cx+15, cy-5 - leg_offset), 2)
    pygame.draw.line(surface, (255, 0, 0), (cx-10, cy+5), (cx-15, cy+5 - leg_offset), 2)
    pygame.draw.line(surface, (255, 0, 0), (cx+10, cy+5), (cx+15, cy+5 + leg_offset), 2)
    # Attack (mandibles)
    if row == 2:
        m = 4 if col % 2 == 0 else 8
        pygame.draw.line(surface, (255, 255, 0), (cx-5, cy-14), (cx-m, cy-20), 2)
        pygame.draw.line(surface, (255, 255, 0), (cx+5, cy-14), (cx+m, cy-20), 2)

# 3. Spaghetti Code
def draw_spaghetti(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    # Wobbly mess
    offset = math.sin(col * math.pi/2) * 3 if row != 0 else 0
    for i in range(5):
        r = 10 + i + (3 if col%2==0 and row==2 else 0)
        pygame.draw.circle(surface, (200, 200, 50), (int(cx + offset*math.cos(i)), int(cy + offset*math.sin(i))), r, 2)
    # Eyes
    pygame.draw.circle(surface, (255, 0, 0), (cx-5, cy-2), 3)
    pygame.draw.circle(surface, (255, 0, 0), (cx+5, cy-2), 3)

# 4. Memory Leak
def draw_leak(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    # Slime
    h = 24 if row != 1 else 24 + math.sin(col*math.pi)*4
    w = 28 if row != 1 else 28 - math.sin(col*math.pi)*4
    if row == 2: h += 6
    pygame.draw.ellipse(surface, (50, 50, 200), (cx-w//2, cy-h//2+4, w, h))
    pygame.draw.ellipse(surface, (100, 100, 255), (cx-w//2+4, cy-h//2+8, w-8, h-8))
    # Drips
    if row == 2:
        pygame.draw.circle(surface, (100, 100, 255), (cx, cy-h//2-col*2), 3)

# 5. Deadline
def draw_deadline(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    # Clock body
    pygame.draw.circle(surface, (200, 50, 50), (cx, cy), 14)
    pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 10)
    # Hands spinning (faster if move/attack)
    angle = col * math.pi/2
    if row == 1: angle *= 2
    if row == 2: angle *= 4
    ex = cx + math.cos(angle) * 8
    ey = cy + math.sin(angle) * 8
    pygame.draw.line(surface, (0, 0, 0), (cx, cy), (ex, ey), 2)
    
# 6. MiniBoss (Corrupted Server)
def draw_miniboss(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    pygame.draw.rect(surface, (50, 50, 50), (cx-20, cy-28, 40, 56))
    for i in range(3):
        color = (255, 0, 0) if (col+i)%2==0 else (100, 0, 0)
        if row == 2: color = (255, 255, 0) # Attack
        pygame.draw.rect(surface, color, (cx-15, cy-20 + i*16, 30, 8))

# 7. Boss (AI Mainframe)
def draw_boss(surface, rect, row, col):
    cx, cy = rect.centerx, rect.centery
    # Giant eye
    pygame.draw.circle(surface, (30, 30, 30), (cx, cy), 40)
    pygame.draw.circle(surface, (200, 0, 0), (cx, cy), 20)
    
    # Pulse
    pupil = 10
    if row == 1: pupil += math.sin(col*math.pi/2)*4
    if row == 2: pupil = 18 if col%2==0 else 6
    pygame.draw.circle(surface, (255, 255, 0), (cx, cy), int(pupil))

create_spritesheet("player_sheet.png", 32, 32, 3, 4, draw_player)
create_spritesheet("bug_sheet.png", 32, 32, 3, 4, draw_bug)
create_spritesheet("spaghetti_sheet.png", 32, 32, 3, 4, draw_spaghetti)
create_spritesheet("leak_sheet.png", 32, 32, 3, 4, draw_leak)
create_spritesheet("deadline_sheet.png", 32, 32, 3, 4, draw_deadline)
create_spritesheet("miniboss_sheet.png", 64, 64, 3, 4, draw_miniboss)
create_spritesheet("boss_sheet.png", 128, 128, 3, 4, draw_boss)

print("Spritesheets generados exitosamente!")
