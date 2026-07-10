import pygame
import sys
import random
import save_manager
import math
from transitions import render_transition

from dag_engine import DagEngine, NodeState
from map_generator import MapGenerator
from player import Player, init_player_assets
from enemy import BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy, MiniBoss, Boss, preload_combat_assets
from enemy_ai import draw_enemy_ai_debug
from pathfinding import PathFinder
from level import DEFAULT_HAZARD_DAMAGE, DEFAULT_HAZARD_DAMAGE_COOLDOWN, load_combat_level, level_key_from_room_id
from collision_editor import CollisionEditor
from menu import MainMenu, BestiaryMenu, PauseMenu, TitleScreen, OptionsMenu, DisclaimerScreen, PlaySubMenu, SlotSelectMenu
from tutorial import TutorialState
import audio

# Buffer chico (512) para que los efectos suenen sin retraso perceptible.
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

# Configurar Pantalla
WIDTH, HEIGHT = 1280, 720

# --- Limite de FPS (independiente de la resolucion, el aspecto y el escalado) ---
# La logica del juego SIEMPRE simula a 60 Hz (fixed timestep); el limite de FPS solo
# controla la frecuencia de RENDER. Asi el juego nunca se acelera ni se ralentiza.
FIXED_FPS = 60
FIXED_DT_MS = 1000.0 / FIXED_FPS
MAX_SIM_STEPS = 5  # Tope de pasos de simulacion por frame (evita "spiral of death").
VALID_FPS_LIMITS = [30, 60, 120, 144, 165, 240, "unlimited"]
DEFAULT_FPS_LIMIT = 60
FINAL_BOSS_ROOM_ID = "TIP10TEMTT1"
MINIBOSS_LEVEL_SUFFIX = "boss"
MINIBOSS_BOSS_LEVEL_KEYS = {"s1", "s4", "s9"}
DEFEAT_SEQUENCE_FRAMES = 150
VALID_NODE_STATES = {NodeState.LOCKED, NodeState.UNLOCKED, NodeState.CLEANED}


def sanitize_fps_limit(value):
    """Devuelve un limite de FPS valido de VALID_FPS_LIMITS; si es invalido, 60."""
    if value == "unlimited":
        return "unlimited"
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return DEFAULT_FPS_LIMIT
    return ivalue if ivalue in VALID_FPS_LIMITS else DEFAULT_FPS_LIMIT


def get_saved_display_mode():
    data = save_manager.load_global_save()
    saved_res = data.get("resolution", [WIDTH, HEIGHT])
    if isinstance(saved_res, (list, tuple)) and len(saved_res) >= 2:
        resolution = (int(saved_res[0]), int(saved_res[1]))
    else:
        resolution = (WIDTH, HEIGHT)
    fullscreen = bool(data.get("fullscreen", True))
    return resolution, fullscreen


def get_desktop_size():
    """Tamaño real del escritorio del monitor principal (sin depender del modo actual)."""
    try:
        return pygame.display.get_desktop_sizes()[0]
    except Exception:
        info = pygame.display.Info()
        return info.current_w, info.current_h


def apply_display_mode(resolution, fullscreen):
    """Crea/recrea la ventana real de forma robusta y devuelve la superficie.

    La lógica del juego siempre se dibuja sobre la superficie virtual de 1280x720
    y luego se escala con letterbox en present_virtual_surface(), por lo que la
    resolución elegida nunca deforma ni corta el contenido: solo define el tamaño
    real del framebuffer sobre el que se aplica el letterbox 16:9.

    - Pantalla completa: usa el tamano real del escritorio para que el calculo
      de fit/fill se haga con la relacion de aspecto del monitor. Esto evita que
      una resolucion guardada antigua (por ejemplo 800x600) provoque recortes
      excesivos antes de que SDL escale a la pantalla fisica.
    - Ventana: limita la resolución pedida al área útil del escritorio (descontando
      barra de título y barra de tareas) para que la ventana no quede fuera de pantalla.
    """
    req_w = int(resolution[0]) if resolution else WIDTH
    req_h = int(resolution[1]) if resolution else HEIGHT

    if fullscreen:
        desktop_w, desktop_h = get_desktop_size()
        try:
            return pygame.display.set_mode((desktop_w, desktop_h), pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            try:
                return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except pygame.error:
                return pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)

    desktop_w, desktop_h = get_desktop_size()
    # Margen para barra de título (~40 px) y barra de tareas (~60 px).
    max_w = max(640, desktop_w - 20)
    max_h = max(360, desktop_h - 80)
    win_w = min(req_w, max_w)
    win_h = min(req_h, max_h)
    try:
        return pygame.display.set_mode((win_w, win_h), 0)
    except pygame.error:
        return pygame.display.set_mode((WIDTH, HEIGHT), 0)


# Crear la ventana real y la superficie virtual para el juego
_initial_resolution, _initial_fullscreen = get_saved_display_mode()
real_screen = apply_display_mode(_initial_resolution, _initial_fullscreen)
screen = pygame.Surface((WIDTH, HEIGHT))
pygame.display.set_caption("Mega-Calabozo DAG")

# Inicializar assets del jugador
init_player_assets()

MAP_BG_IMG = None
try:
    MAP_BG_IMG = pygame.image.load("assets/images/backgrounds/map_bg.png").convert()
    MAP_BG_IMG = pygame.transform.scale(MAP_BG_IMG, (WIDTH, HEIGHT))
except Exception as e:
    print("No se pudo cargar el fondo del mapa:", e)

FLOOR_IMG = None
try:
    FLOOR_IMG = pygame.image.load("assets/images/backgrounds/floor_tile.png").convert()
    # Escalar para llenar la pantalla de combate
    FLOOR_IMG = pygame.transform.scale(FLOOR_IMG, (WIDTH, HEIGHT))
except Exception as e:
    print("No se pudo cargar el suelo:", e)

SAVE_ICON_IMG = None
try:
    SAVE_ICON_IMG = pygame.image.load("assets/images/ui/save.png").convert_alpha()
    # Forzar un aspecto cuadrado (40x40) para evitar que se vea muy ancha
    SAVE_ICON_IMG = pygame.transform.scale(SAVE_ICON_IMG, (40, 40))
except Exception as e:
    print("No se pudo cargar el icono de guardado:", e)

HEART_FRAMES = []
try:
    heart_sheet = pygame.image.load("assets/images/ui/vida_heart.png").convert_alpha()
    # La nueva imagen tiene 5 fotogramas en 1 fila
    hw = heart_sheet.get_width() // 5
    hh = heart_sheet.get_height() // 1

    for c in range(5):
        rect = pygame.Rect(c * hw, 0, hw, hh)
        frame = pygame.Surface((hw, hh), pygame.SRCALPHA)
        frame.blit(heart_sheet, (0, 0), rect)

        bbox = frame.get_bounding_rect()
        if bbox.width > 0 and bbox.height > 0:
            # Crear un cuadrado perfecto (400x400) para centrar y evitar deformación
            square = pygame.Surface((400, 400), pygame.SRCALPHA)
            offset_x = (400 - bbox.width) // 2
            offset_y = (400 - bbox.height) // 2
            square.blit(frame, (offset_x, offset_y), bbox)

            cropped = pygame.transform.scale(square, (28, 28)) # Tamaño reducido
            HEART_FRAMES.append(cropped)
except Exception as e:
    print("No se pudo cargar la animacion del corazon:", e)

# Fuentes
try:
    font_sm = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 20)
    font_md = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 28)
    font_lg = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 56)
    font_title = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 100)
except:
    font_sm = pygame.font.SysFont("Arial", 16)
    font_md = pygame.font.SysFont("Arial", 24)
    font_lg = pygame.font.SysFont("Arial", 48)
    font_title = pygame.font.SysFont("Arial", 80)

# --- Precarga de sprites de combate ---
# Corta y cachea AHORA (en el arranque) las hojas de todos los enemigos/jefes y del
# jugador, para que la primera aparición en combate no provoque un tirón de FPS.
# Es la parte cara (disco + decode + recorte por frame); hacerla una vez aquí evita
# repetirla en mitad de la partida.
try:
    real_screen.fill((0, 0, 0))
    _loading_txt = font_lg.render("Cargando...", False, (235, 180, 125))
    real_screen.blit(_loading_txt, _loading_txt.get_rect(center=(real_screen.get_width() // 2, real_screen.get_height() // 2)))
    pygame.display.flip()
    pygame.event.pump()  # mantiene la ventana responsiva mientras se cargan los sprites
except Exception:
    pass

preload_combat_assets()
try:
    Player(0, 0)  # calienta también el spritesheet del jugador
except Exception as e:
    print("Preload del jugador fallo:", e)

# Colores
BG_COLOR = (20, 20, 25)
TEXT_COLOR = (255, 255, 255)


ARENA_W = int(WIDTH * 1.5)
ARENA_H = int(HEIGHT * 1.5)


def draw_floor(surface, background, offset_x=0, offset_y=0):
    if background:
        surface.blit(background, (int(offset_x), int(offset_y)))
    elif FLOOR_IMG:
        surface.blit(FLOOR_IMG, (int(offset_x), int(offset_y)))
    else:
        pygame.draw.rect(surface, (40, 30, 30), (0, 0, WIDTH, HEIGHT))



def render_text_fit(font, text, color, max_width, antialias=False):
    text_surface = font.render(text, antialias, color)
    if text_surface.get_width() <= max_width:
        return text_surface

    scale = max_width / max(1, text_surface.get_width())
    new_width = max(1, int(text_surface.get_width() * scale))
    new_height = max(1, int(text_surface.get_height() * scale))
    return pygame.transform.scale(text_surface, (new_width, new_height))


def draw_centered_text_fit(surface, text, font, center, color, max_width, antialias=False):
    text_surface = render_text_fit(font, text, color, max_width, antialias)
    text_rect = text_surface.get_rect(center=center)
    surface.blit(text_surface, text_rect)
    return text_rect


def draw_defeat_sequence(surface, player, camera_x, camera_y, timer, total_frames):
    if not player or timer <= 0:
        return

    total = max(1, total_frames)
    elapsed = total - max(0, timer)
    progress = max(0.0, min(1.0, elapsed / total))
    pixel = 8
    block = 16

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((24, 0, 8, int(58 + 48 * progress)))

    # Scanlines discretas y quietas: efecto de derrota sin romper el estilo pixel-art.
    for y in range(0, HEIGHT, block * 3):
        pygame.draw.rect(overlay, (86, 0, 22, 18), (0, y, WIDTH, pixel))

    for i in range(4):
        y = (120 + i * 96 + (elapsed // 18 % 2) * pixel) % HEIGHT
        x = 90 + i * 250
        w = 80 + (i % 2) * 48
        pygame.draw.rect(overlay, (135, 18, 34, 28), (x, y - (y % pixel), w, pixel))

    center_x = int(player.x + camera_x)
    center_y = int(player.y + camera_y)
    center_x -= center_x % pixel
    center_y -= center_y % pixel

    # Pulso principal: diamantes escalonados en vez de circulos suaves.
    def draw_diamond_ring(radius, color):
        radius = max(pixel, (radius // pixel) * pixel)
        for dy in range(-radius, radius + pixel, pixel * 2):
            span = radius - abs(dy)
            for sx in (-span, span):
                pygame.draw.rect(overlay, color, (center_x + sx - pixel // 2, center_y + dy - pixel // 2, pixel, pixel))
        for dx in range(-radius, radius + pixel, pixel * 2):
            span = radius - abs(dx)
            for sy in (-span, span):
                pygame.draw.rect(overlay, color, (center_x + dx - pixel // 2, center_y + sy - pixel // 2, pixel, pixel))

    ring_a = int(24 + progress * 72)
    ring_b = 16 + ((elapsed // 12) % 3) * pixel
    draw_diamond_ring(ring_a, (210, 42, 52, max(28, int(120 * (1.0 - progress)))))
    draw_diamond_ring(ring_b, (255, 165, 105, 70))

    # Fragmentos cuadrados controlados, con direcciones fijas para no verse organico.
    directions = [
        (-1, 0), (1, 0), (0, -1), (0, 1),
        (-1, -1), (1, -1), (-1, 1), (1, 1),
    ]
    for i, (dx, dy) in enumerate(directions):
        length = max(1.0, math.hypot(dx, dy))
        dist = int((16 + progress * (34 + (i % 3) * 8)) // pixel) * pixel
        px = center_x + int(dx / length * dist)
        py = center_y + int(dy / length * dist)
        px -= px % pixel
        py -= py % pixel
        size = pixel
        alpha = max(30, int(140 * (1.0 - progress * 0.6)))
        color = (225, 54 + (i % 2) * 26, 50, alpha)
        pygame.draw.rect(overlay, color, (px, py, size, size))

    # Marca final sobre el jugador: una X hecha de bloques.
    for offset in range(-16, 17, pixel):
        pygame.draw.rect(overlay, (235, 180, 125, 120), (center_x + offset, center_y + offset, pixel, pixel))
        pygame.draw.rect(overlay, (220, 54, 58, 145), (center_x + offset, center_y - offset, pixel, pixel))

    surface.blit(overlay, (0, 0))

    title = font_lg.render("HAS MUERTO", False, (255, 92, 92))
    shadow = font_lg.render("HAS MUERTO", False, (45, 0, 0))
    subtitle = font_md.render("Regresando al mapa...", False, (245, 225, 225))

    panel_w = min(WIDTH - 80, max(560, title.get_width() + 72, subtitle.get_width() + 64))
    panel_h = 102
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 3 - 48
    pygame.draw.rect(surface, (20, 5, 10), (panel_x, panel_y, panel_w, panel_h))
    pygame.draw.rect(surface, (104, 24, 34), (panel_x, panel_y, panel_w, pixel))
    pygame.draw.rect(surface, (104, 24, 34), (panel_x, panel_y + panel_h - pixel, panel_w, pixel))
    pygame.draw.rect(surface, (104, 24, 34), (panel_x, panel_y, pixel, panel_h))
    pygame.draw.rect(surface, (104, 24, 34), (panel_x + panel_w - pixel, panel_y, pixel, panel_h))

    title_rect = title.get_rect(center=(WIDTH // 2, panel_y + 38))
    surface.blit(shadow, (title_rect.x + pixel, title_rect.y + pixel))
    surface.blit(title, title_rect)

    subtitle_rect = subtitle.get_rect(center=(WIDTH // 2, panel_y + 76))
    surface.blit(subtitle, subtitle_rect)

def get_viewport_transform(target_size, aspect_mode="fit"):
    target_w, target_h = target_size
    if target_w <= 0 or target_h <= 0:
        return 1.0, 0, 0, WIDTH, HEIGHT

    if aspect_mode == "fill":
        scale = max(target_w / WIDTH, target_h / HEIGHT)
    else:
        scale = min(target_w / WIDTH, target_h / HEIGHT)
    scaled_w = max(1, int(WIDTH * scale))
    scaled_h = max(1, int(HEIGHT * scale))
    offset_x = (target_w - scaled_w) // 2
    offset_y = (target_h - scaled_h) // 2
    return scale, offset_x, offset_y, scaled_w, scaled_h


def get_visible_virtual_rect(target_size, aspect_mode="fit"):
    scale, offset_x, offset_y, _, _ = get_viewport_transform(target_size, aspect_mode)
    if scale <= 0:
        return pygame.Rect(0, 0, WIDTH, HEIGHT)

    target_w, target_h = target_size
    left = max(0, int(math.ceil((0 - offset_x) / scale)))
    top = max(0, int(math.ceil((0 - offset_y) / scale)))
    right = min(WIDTH, int(math.floor((target_w - offset_x) / scale)))
    bottom = min(HEIGHT, int(math.floor((target_h - offset_y) / scale)))

    if right <= left or bottom <= top:
        return pygame.Rect(0, 0, WIDTH, HEIGHT)
    return pygame.Rect(left, top, right - left, bottom - top)


def window_to_virtual(pos, target_size, aspect_mode="fit"):
    scale, offset_x, offset_y, _, _ = get_viewport_transform(target_size, aspect_mode)
    if scale <= 0:
        return 0, 0

    x = int((pos[0] - offset_x) / scale)
    y = int((pos[1] - offset_y) / scale)
    return max(0, min(WIDTH - 1, x)), max(0, min(HEIGHT - 1, y))


def present_virtual_surface(virtual_surface, target_surface, aspect_mode="fit"):
    _, offset_x, offset_y, scaled_w, scaled_h = get_viewport_transform(target_surface.get_size(), aspect_mode)
    target_surface.fill((0, 0, 0))
    scaled_surface = pygame.transform.scale(virtual_surface, (scaled_w, scaled_h))
    target_surface.blit(scaled_surface, (offset_x, offset_y))


# ============================================================================
# Estilo visual del Mapa Curricular y su HUD.
# NOTA: esto es SOLO presentacion/render. No cambia posiciones de nodos,
# aristas, hitboxes ni ninguna logica del mapa.
# ============================================================================
MAP_UI = {
    "panel_top": (36, 31, 48),
    "panel_bot": (18, 15, 26),
    "edge_dark": (10, 8, 16),
    "edge_light": (120, 104, 150),
    "accent": (255, 208, 120),
    "text": (238, 233, 248),
    "text_dim": (170, 162, 188),
    "divider": (74, 66, 96),
}

_map_overlay_cache = None


def build_map_overlay(width, height):
    """Viñeteado + degradado ambiental SUAVE (se cachea una vez). No oscurece de mas."""
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    vy = int(height * 0.22)
    for i in range(vy):
        a = int(76 * (1 - i / vy))
        pygame.draw.line(overlay, (0, 0, 12, a), (0, i), (width, i))
        pygame.draw.line(overlay, (0, 0, 12, a), (0, height - 1 - i), (width, height - 1 - i))
    vx = int(width * 0.13)
    for i in range(vx):
        a = int(52 * (1 - i / vx))
        pygame.draw.line(overlay, (0, 0, 12, a), (i, 0), (i, height))
        pygame.draw.line(overlay, (0, 0, 12, a), (width - 1 - i, 0), (width - 1 - i, height))
    return overlay


def get_map_overlay():
    global _map_overlay_cache
    if _map_overlay_cache is None:
        _map_overlay_cache = build_map_overlay(WIDTH, HEIGHT)
    return _map_overlay_cache


def draw_pixel_panel(surface, rect, title_h=0, accent=None, fill=(30, 26, 42)):
    """Panel pixel-art: relleno PLANO, bordes duros con bisel y remaches. Sin degradados."""
    rect = pygame.Rect(rect)
    outer = (8, 6, 12)
    light = (78, 68, 100)
    dark = (16, 12, 24)
    # contorno exterior (2px) + relleno plano
    pygame.draw.rect(surface, outer, rect)
    inner = rect.inflate(-2, -2)
    pygame.draw.rect(surface, fill, inner)
    # bisel duro: claro arriba/izquierda, oscuro abajo/derecha
    pygame.draw.line(surface, light, (inner.left, inner.top), (inner.right - 1, inner.top))
    pygame.draw.line(surface, light, (inner.left, inner.top), (inner.left, inner.bottom - 1))
    pygame.draw.line(surface, dark, (inner.left, inner.bottom - 1), (inner.right - 1, inner.bottom - 1))
    pygame.draw.line(surface, dark, (inner.right - 1, inner.top), (inner.right - 1, inner.bottom - 1))
    # separador de titulo (linea hundida de 2px)
    if title_h > 0:
        ty = inner.top + title_h
        pygame.draw.line(surface, dark, (inner.left + 2, ty), (inner.right - 3, ty))
        pygame.draw.line(surface, light, (inner.left + 2, ty + 1), (inner.right - 3, ty + 1))
    # remaches en las esquinas (bloques pixelados)
    if accent:
        for (ax, ay) in [(rect.left + 3, rect.top + 3), (rect.right - 6, rect.top + 3),
                         (rect.left + 3, rect.bottom - 6), (rect.right - 6, rect.bottom - 6)]:
            pygame.draw.rect(surface, accent, (ax, ay, 3, 3))
            pygame.draw.rect(surface, dark, (ax, ay, 3, 3), 1)


def draw_energy_crystal(surface, cx, cy, filled):
    """Gema de energia PIXELADA (diamante escalonado). filled = energia disponible."""
    px = 2
    rows = [1, 3, 5, 7, 5, 3, 1]  # medio-ancho de cada fila (en unidades de pixel)
    if filled:
        body, hi = (86, 204, 250), (198, 240, 255)
        edge = (14, 44, 70)
    else:
        body, hi = (58, 60, 80), None
        edge = (34, 36, 50)
    top = cy - (len(rows) // 2) * px
    # contorno oscuro (una unidad mas ancho por lado)
    for i, hw in enumerate(rows):
        w = (hw + 1) * px
        pygame.draw.rect(surface, edge, (cx - w // 2, top + i * px, w, px))
    # cuerpo
    for i, hw in enumerate(rows):
        w = hw * px
        pygame.draw.rect(surface, body, (cx - w // 2, top + i * px, w, px))
    # brillo superior
    if hi:
        pygame.draw.rect(surface, hi, (cx - px, top + px, px, px))


def draw_map_hud(surface, semester, par, energy, max_energy, view=None):
    """HUD superior del mapa: barra plana pixel-art con bordes duros.

    Se ancla al área realmente visible (`view`) para que en modo 'fill' —que
    recorta los bordes de la superficie virtual— la barra no quede cortada.
    Los ejes X se reanclan proporcionalmente al ancho visible; el eje Y solo se
    desplaza hacia el borde superior visible.
    """
    HUD_H = 104
    left = view.left if view else 0
    top = view.top if view else 0
    right = view.right if view else WIDTH
    w = max(1, right - left)

    def X(x):  # coord de diseño (0..WIDTH) -> reanclada al ancho visible
        return left + x * w // WIDTH

    def Y(y):  # coord de diseño (0..HUD_H) -> desplazada al borde superior visible
        return top + y

    # relleno plano en 2 tonos duros (sin degradado)
    pygame.draw.rect(surface, (26, 22, 36), (left, top, w, HUD_H))
    pygame.draw.rect(surface, (20, 16, 28), (left, Y(HUD_H - 24), w, 24))
    pygame.draw.line(surface, (60, 52, 82), (left, top), (right, top))            # highlight superior 1px
    # borde inferior duro: oscuro (4px) + acento (1px)
    pygame.draw.rect(surface, (10, 8, 16), (left, Y(HUD_H - 4), w, 4))
    pygame.draw.line(surface, MAP_UI["accent"], (left, Y(HUD_H - 5)), (right, Y(HUD_H - 5)))

    surface.blit(font_md.render("MALLA CURRICULAR", False, MAP_UI["accent"]), (X(24), Y(14)))
    surface.blit(font_sm.render("Mapa DAG - grafo de materias", False, MAP_UI["text_dim"]), (X(24), Y(46)))

    def stat(cx, label, value_str):
        lab = font_sm.render(label, False, MAP_UI["text_dim"])
        surface.blit(lab, lab.get_rect(center=(X(cx), Y(26))))
        val = font_md.render(value_str, False, MAP_UI["text"])
        surface.blit(val, val.get_rect(center=(X(cx), Y(50))))

    # divisores duros (2px: oscuro + claro)
    for dx in (690, 862):
        pygame.draw.line(surface, (12, 10, 18), (X(dx), Y(16)), (X(dx), Y(62)))
        pygame.draw.line(surface, (60, 52, 82), (X(dx) + 1, Y(16)), (X(dx) + 1, Y(62)))
    stat(610, "SEMESTRE", str(semester))
    stat(776, "TIEMPO RECORD", str(par))

    # Energia como gemas pixeladas
    lab = font_sm.render("ENERGIA", False, MAP_UI["text_dim"])
    surface.blit(lab, lab.get_rect(center=(X(1040), Y(24))))
    gap = 22
    total = max(1, max_energy) * gap
    sx = X(1040) - total // 2 + gap // 2
    for i in range(max_energy):
        draw_energy_crystal(surface, sx + i * gap, Y(52), i < energy)

    controls = "WASD Mover   -   Flechas/Mouse Disparar   -   ENTER Entrar   -   ESPACIO Descansar"
    cs = font_sm.render(controls, False, MAP_UI["text_dim"])
    surface.blit(cs, cs.get_rect(center=(X(WIDTH // 2), Y(84))))


def draw_selection_highlight(surface, rect):
    """Marco de seleccion pixel-art: contorno duro parpadeante + corner brackets chunky."""
    blink = (math.sin(pygame.time.get_ticks() / 200.0) + 1) / 2.0
    accent = MAP_UI["accent"]
    col = accent if blink > 0.4 else (198, 162, 88)
    frame = rect.inflate(6, 6)
    # contorno duro (sin glow suave), casing oscuro + color, siguiendo el redondeo del nodo
    pygame.draw.rect(surface, (14, 10, 4), frame.inflate(4, 4), 3, border_radius=10)
    pygame.draw.rect(surface, col, frame, 3, border_radius=10)
    # corner brackets chunky (lineas duras)
    L, w = 12, 4
    for (cx, cy, sx, sy) in [
        (frame.left, frame.top, 1, 1),
        (frame.right, frame.top, -1, 1),
        (frame.left, frame.bottom, 1, -1),
        (frame.right, frame.bottom, -1, -1),
    ]:
        pygame.draw.line(surface, accent, (cx, cy), (cx + sx * L, cy), w)
        pygame.draw.line(surface, accent, (cx, cy), (cx, cy + sy * L), w)


def draw_subject_tooltip(surface, engine, selected_node, sel_rect):
    """Panel informativo de la materia (misma info y misma logica de posicion/volteo)."""
    name = engine.subjects[selected_node]['name']
    reqs = engine.subjects[selected_node]['reqs']
    entries = []  # (texto, color)
    if selected_node == FINAL_BOSS_ROOM_ID:
        cleaned = sum(1 for n in engine.nodes if engine.state[n] == NodeState.CLEANED)
        total = len(engine.nodes) - 1
        entries.append((f"- Completar todas las materias ({cleaned}/{total})", MAP_UI["text"]))
    elif not reqs:
        entries.append(("- Ninguno", MAP_UI["text_dim"]))
    else:
        for r in reqs:
            done = engine.state.get(r) == NodeState.CLEANED
            col = (150, 220, 150) if done else (232, 178, 128)
            entries.append((f"- {engine.subjects[r]['name']}", col))

    title_surf = font_sm.render(name, False, MAP_UI["accent"])
    header_surf = font_sm.render("Prerrequisitos:", False, MAP_UI["text_dim"])
    entry_surfs = [font_sm.render(txt, False, c) for (txt, c) in entries]
    line_h = font_sm.get_height()
    pad = 12
    title_h = line_h + 10
    body = [header_surf] + entry_surfs
    max_w = max([title_surf.get_width()] + [s.get_width() for s in body])
    tt_w = max_w + pad * 2
    tt_h = title_h + 6 + len(body) * line_h + pad

    # Misma logica que antes: al lado derecho del nodo y se voltea si no cabe.
    tt_x = sel_rect.right + 15
    tt_y = sel_rect.top
    if tt_x + tt_w > WIDTH:
        tt_x = sel_rect.left - tt_w - 15
    tt_x = max(8, tt_x)
    tt_y = max(8, min(tt_y, HEIGHT - 8 - tt_h))

    draw_pixel_panel(surface, (tt_x, tt_y, tt_w, tt_h), title_h=title_h, accent=MAP_UI["accent"])
    surface.blit(title_surf, (tt_x + pad, tt_y + 6))
    cy = tt_y + title_h + 5
    for s in body:
        surface.blit(s, (tt_x + pad, cy))
        cy += line_h


def main():
    save_mgr = save_manager
    global_data = save_mgr.load_global_save()
    global screen, real_screen
    clock = pygame.time.Clock()

    audio.init(global_data.get("volume", 100), global_data.get("music_volume", 100))
    audio.play_music("menu")

    # Inicializar Sistemas del Juego
    engine = DagEngine()
    map_gen = MapGenerator(engine)
    par_score = engine.get_par_score()

    # Variables de Estado del Juego
    game_state = "DISCLAIMER_SCREEN" # TITLE_SCREEN, MAIN_MENU, TUTORIAL, BESTIARY, MAP, COMBAT, WIN, GAME_OVER
    semester_counter = 1
    max_energy = 6
    energy = 6
    rest_animation_timer = 0

    title_screen = TitleScreen(WIDTH, HEIGHT, font_title, font_md)
    disclaimer_screen = DisclaimerScreen(WIDTH, HEIGHT, font_lg, font_md)
    play_sub_menu = PlaySubMenu(WIDTH, HEIGHT, font_lg, font_md)
    current_slot_mode = None
    slot_select_menu = None
    save_indicator_timer = 0
    current_slot = 1
    main_menu = MainMenu(WIDTH, HEIGHT, font_lg, font_md, global_data)
    bestiary_menu = BestiaryMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm, save_mgr)
    tutorial_state = TutorialState(WIDTH, HEIGHT, font_lg, font_md, font_sm, HEART_FRAMES)
    pause_menu = PauseMenu(WIDTH, HEIGHT, font_lg, font_md)
    options_menu = OptionsMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm, global_data)
    aspect_mode = global_data.get("aspect_mode", "fit")
    if aspect_mode not in ("fit", "fill"):
        aspect_mode = "fit"
    fps_limit = sanitize_fps_limit(global_data.get("fps_limit", DEFAULT_FPS_LIMIT))
    previous_state = None
    options_return_state = "MAIN_MENU"

    def ui_safe_rect():
        """Zona de la superficie virtual que realmente se ve tras el fit/fill.

        Todas las pantallas usan el modo elegido (fit/fill): en 'fill' el fondo llena
        la pantalla (recortar el fondo es inofensivo) y los elementos anclados a un
        borde (títulos de esquina, textos inferiores...) se reubican dentro de esta
        zona para que no se corten. En 'fit' equivale a toda la superficie, así que el
        anclaje es transparente. Ver cómo se aplica a los menús con `safe_rect`.
        """
        return get_visible_virtual_rect(real_screen.get_size(), aspect_mode)

    # Variables de la Cámara del Mapa
    camera_x, camera_y = 0, 0
    dragging = False
    last_mouse_pos = (0, 0)
    selected_node = None

    def map_view_rect():
        """Zona de la superficie virtual que realmente se ve tras el fit/fill.

        En modo 'fit' es todo 1280x720; en 'fill' es más pequeña porque el
        escalado recorta los bordes. La cámara y el HUD del mapa se anclan a esta
        zona para que ningún nodo ni el HUD queden fuera de pantalla en 'fill'.
        """
        return get_visible_virtual_rect(real_screen.get_size(), aspect_mode)

    def clamp_map_camera(cx, cy):
        """Limita el desplazamiento de la cámara para no arrastrar el mapa al vacío.

        Solo afecta a la cámara (offset de dibujo); no cambia posiciones de nodos,
        aristas ni hitboxes. Se permite un margen para poder ver los bordes del mapa
        con algo de aire, pero no desplazarse indefinidamente. Los límites se calculan
        sobre el área realmente visible (map_view_rect) para que el modo 'fill' no
        recorte los nodos de las orillas.
        """
        rooms = map_gen.rooms
        if not rooms:
            return cx, cy
        min_x = min(r.rect.left for r in rooms.values())
        max_x = max(r.rect.right for r in rooms.values())
        min_y = min(r.rect.top for r in rooms.values())
        max_y = max(r.rect.bottom for r in rooms.values())
        pad = 140      # aire permitido más allá de los bordes del mapa
        hud_h = 104    # franja del HUD superior dentro del área visible

        view = map_view_rect()
        view_left, view_right = view.left, view.right
        view_bottom = view.bottom
        view_w = view_right - view_left
        usable_top = view.top + hud_h   # borde inferior del HUD, ya dentro del área visible

        # Eje X: si el mapa cabe a lo ancho se mantiene casi centrado (con holgura pad).
        if (max_x - min_x) <= view_w:
            center_cx = (view_left + view_right - min_x - max_x) / 2
            cx_min, cx_max = center_cx - pad, center_cx + pad
        else:
            cx_min, cx_max = view_right - max_x - pad, view_left - min_x + pad

        # Eje Y: se considera el HUD para que la PRIMERA fila pueda bajar por debajo
        # de él y verse completa. El área útil vertical va de usable_top a view_bottom.
        usable_h = view_bottom - usable_top
        if (max_y - min_y) <= usable_h:
            center_cy = (usable_top + view_bottom) / 2 - (min_y + max_y) / 2
            cy_min, cy_max = center_cy - pad, center_cy + pad
        else:
            cy_min = view_bottom - pad - max_y
            cy_max = usable_top + pad - min_y

        return max(cx_min, min(cx_max, cx)), max(cy_min, min(cy_max, cy))

    def coerce_int(value, fallback, minimum=None, maximum=None):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = fallback
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    def normalize_engine_state(target_engine, saved_state):
        normalized = dict(target_engine.state)
        if isinstance(saved_state, dict):
            for node in target_engine.nodes:
                state = saved_state.get(node)
                if state in VALID_NODE_STATES:
                    normalized[node] = state
        target_engine.state = normalized
        target_engine.update_unlocks()

    def load_saved_game_data(data):
        nonlocal engine, map_gen, par_score, semester_counter, energy, max_energy, camera_x, camera_y, selected_node
        if not isinstance(data, dict):
            return False

        loaded_engine = DagEngine()
        normalize_engine_state(loaded_engine, data.get("nodes_state"))
        engine = loaded_engine
        map_gen = MapGenerator(engine)
        par_score = engine.get_par_score()

        semester_counter = coerce_int(data.get("semester_counter"), 1, minimum=1)
        max_energy = coerce_int(data.get("max_energy"), 6, minimum=1)
        energy = coerce_int(data.get("energy"), max_energy, minimum=0, maximum=max_energy)
        camera_x = coerce_int(data.get("camera_x"), 0)
        camera_y = coerce_int(data.get("camera_y"), 0)
        camera_x, camera_y = clamp_map_camera(camera_x, camera_y)
        selected_node = None
        return True

    current_room = None
    combat_player = None
    enemies = []
    current_level = load_combat_level(fallback_size=(ARENA_W, ARENA_H))
    collision_manager = current_level.create_collision_manager()
    pathfinder = PathFinder(current_level)
    combat_bg_img = FLOOR_IMG
    debug_collisions = False
    debug_collision_labels = False
    debug_enemy_paths = False
    editor_mode = False
    editor = CollisionEditor(current_level, collision_manager)

    combat_cam_x, combat_cam_y = 0, 0

    current_wave = 1
    max_waves = 1
    wave_timer = 0

    floating_texts = [] # Lista para almacenar los números de daño flotantes
    player_hazard_cooldown = 0

    trans_state = {
        "active": False,
        "progress": 0.0,
        "speed": 0.04,
        "type": "FADE",
        "old_surf": None
    }

    def music_candidates_for(target):
        """Pistas de música para cada estado, en orden de preferencia (fallbacks).

        None significa "mantener la música actual" (pausa, opciones, bestiario...),
        de modo que esas pantallas no interrumpen la ambientación de fondo.
        """
        if target in ("DISCLAIMER_SCREEN", "TITLE_SCREEN", "MAIN_MENU"):
            return ("menu",)
        if target == "MAP":
            return ("map", "menu")
        if target == "COMBAT":
            if current_room == FINAL_BOSS_ROOM_ID:
                return ("boss_final", "boss", "combat", "map", "menu")
            if is_miniboss_room(current_room):
                return ("boss", "combat", "map", "menu")
            return ("combat", "map", "menu")
        if target == "WIN":
            return ("win", "menu")
        return None

    def trigger_transition(target, t_type="FADE", speed=0.04):
        nonlocal game_state
        trans_state["active"] = True
        trans_state["progress"] = 0.0
        trans_state["speed"] = speed
        trans_state["type"] = t_type
        trans_state["old_surf"] = screen.copy()
        game_state = target
        candidates = music_candidates_for(target)
        if candidates:
            audio.play_music(*candidates)
        audio.set_music_duck(target == "PAUSE")

    def ui_action(menu_obj, event, *args):
        """handle_event de un menú + click sonoro cuando el jugador acciona algo."""
        action = menu_obj.handle_event(event, *args)
        if action and event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            audio.play_sfx("click")
        return action

    def finish_tutorial():
        global_data["tutorial_completed"] = True
        save_mgr.save_global_save(global_data)
        main_menu.tutorial_completed = True
        main_menu.options = ["Jugar", "Bestiario", "Tutorial", "Opciones", "Salir"]
        trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)

    def combat_world_size():
        return current_level.width, current_level.height

    def clamp_camera_axis(target, world_size, viewport_size):
        if world_size <= viewport_size:
            return (viewport_size - world_size) // 2
        return min(0, max(viewport_size - world_size, target))

    def update_combat_camera(smooth=True):
        nonlocal combat_cam_x, combat_cam_y
        if not combat_player:
            return
        world_w, world_h = combat_world_size()
        target_cam_x = WIDTH // 2 - combat_player.x
        target_cam_y = HEIGHT // 2 - combat_player.y
        target_cam_x = clamp_camera_axis(target_cam_x, world_w, WIDTH)
        target_cam_y = clamp_camera_axis(target_cam_y, world_h, HEIGHT)
        if smooth:
            combat_cam_x += (target_cam_x - combat_cam_x) * 0.1
            combat_cam_y += (target_cam_y - combat_cam_y) * 0.1
        else:
            combat_cam_x = target_cam_x
            combat_cam_y = target_cam_y

    def load_level_background(level):
        try:
            image = level.load_background()
            if image:
                return image
        except Exception as e:
            print(f"No se pudo cargar el fondo del nivel {level.name}: {e}")
        if FLOOR_IMG:
            return pygame.transform.scale(FLOOR_IMG, tuple(level.size))
        return None

    def is_miniboss_room(room_id):
        return bool(room_id and room_id in engine.critical_nodes and room_id != FINAL_BOSS_ROOM_ID)

    def miniboss_level_variant_for(room_id):
        if not is_miniboss_room(room_id):
            return None
        semester_key = level_key_from_room_id(room_id)
        if semester_key in MINIBOSS_BOSS_LEVEL_KEYS:
            return MINIBOSS_LEVEL_SUFFIX
        return None

    def load_room_level(room_id):
        nonlocal current_level, collision_manager, combat_bg_img, editor, pathfinder
        level_variant = miniboss_level_variant_for(room_id)
        current_level = load_combat_level(
            room_id,
            fallback_size=(ARENA_W, ARENA_H),
            variant_suffix=level_variant,
        )
        collision_manager = current_level.create_collision_manager()
        pathfinder = PathFinder(current_level)
        editor = CollisionEditor(current_level, collision_manager)
        combat_bg_img = load_level_background(current_level)

    def positive_int(value, fallback):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback

    def apply_player_hazard_damage():
        nonlocal player_hazard_cooldown
        if player_hazard_cooldown > 0:
            player_hazard_cooldown -= 1
            return
        if not current_level or not combat_player:
            return

        strongest_hit = None
        for hazard_rect, data in current_level.iter_hazard_hits(combat_player.rect):
            damage = positive_int(data.get("damage"), DEFAULT_HAZARD_DAMAGE)
            if strongest_hit is None or damage > strongest_hit["damage"]:
                strongest_hit = {"rect": hazard_rect, "data": data, "damage": damage}

        if not strongest_hit:
            return

        damage = strongest_hit["damage"]
        combat_player.hp -= damage
        audio.play_sfx("hurt")
        player_hazard_cooldown = positive_int(
            strongest_hit["data"].get("damage_cooldown"),
            DEFAULT_HAZARD_DAMAGE_COOLDOWN,
        )
        floating_texts.append({
            "text": str(damage),
            "x": combat_player.x,
            "y": combat_player.y - 38,
            "life": 38,
            "color": (255, 220, 80)
        })

    def spawn_enemy(enemy_cls, preferred_positions=None):
        world_w, world_h = combat_world_size()
        scale = current_level.character_scale if current_level else 1.0
        positions = list(preferred_positions or [])
        if current_level and current_level.enemy_spawns:
            level_spawns = list(current_level.enemy_spawns)
            random.shuffle(level_spawns)
            positions.extend(level_spawns)

        last_position = positions[0] if positions else (world_w // 2, world_h // 2)
        for attempt in range(80):
            if attempt < len(positions):
                x, y = positions[attempt]
            else:
                x = random.randint(80, max(80, world_w - 80))
                y = random.randint(80, max(80, world_h - 80))
            last_position = (x, y)

            enemy = enemy_cls(x, y, scale=scale)
            enemy.sync_rect_to_position()
            if collision_manager and collision_manager.check_collision(enemy.rect):
                continue
            if pathfinder and not pathfinder.is_position_walkable((enemy.x, enemy.y), (enemy.rect.w, enemy.rect.h), allow_hazards=False):
                continue
            if combat_player and enemy.rect.colliderect(combat_player.rect.inflate(180, 180)):
                continue
            return enemy

        return enemy_cls(last_position[0], last_position[1], scale=scale)

    def start_combat(room_id):
        nonlocal current_room, combat_player, enemies, current_wave, max_waves, wave_timer, energy, level_passed_timer, level_passed_done, level_failed_timer, level_failed_done, player_hazard_cooldown
        current_room = room_id
        load_room_level(current_room)
        trigger_transition("COMBAT", "CIRCLE", 0.03)
        energy -= 1
        level_passed_timer = 0
        level_passed_done = False
        level_failed_timer = 0
        level_failed_done = False
        player_hazard_cooldown = 0

        world_w, world_h = combat_world_size()
        scale = current_level.character_scale if current_level else 1.0
        combat_player = Player(current_level.player_spawn[0], current_level.player_spawn[1], scale=scale)
        combat_player.rect.clamp_ip(pygame.Rect(0, 0, world_w, world_h))
        combat_player.sync_position_to_rect()
        update_combat_camera(smooth=False)

        current_wave = 1
        max_waves = 1 + (semester_counter // 2)
        wave_timer = 300

        enemy_types = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]
        enemies = [spawn_enemy(random.choice(enemy_types)) for _ in range(random.randint(3, 6))]
        if current_room == FINAL_BOSS_ROOM_ID:
            enemies.append(spawn_enemy(Boss, [(world_w // 2, 140)]))
        if is_miniboss_room(current_room) and max_waves == 1:
            enemies.append(spawn_enemy(MiniBoss, [(world_w // 2, world_h // 3)]))

    def begin_level_failure():
        nonlocal level_failed_timer
        if level_failed_timer > 0 or level_failed_done:
            return
        if combat_player:
            combat_player.hp = 0
            combat_player.state = 0
        level_failed_timer = DEFEAT_SEQUENCE_FRAMES
        audio.play_sfx("level_failed")

    load_room_level(None)

    last_click_time = 0
    last_clicked_node = None
    map_message = ""
    map_message_timer = 0
    level_passed_timer = 0
    level_passed_done = False
    level_failed_timer = 0
    level_failed_done = False
    sim_accumulator = 0.0
    running = True
    while running:
        # Ritmo de RENDER segun el limite de FPS elegido (independiente de la resolucion).
        # "unlimited" -> tick(0): no limita. Devuelve los ms reales transcurridos.
        frame_ms = clock.tick(0 if fps_limit == "unlimited" else fps_limit)

        # Simulacion a PASO FIJO de 60 Hz desacoplada del render: acumulamos el tiempo
        # real y ejecutamos la logica en pasos de 1/60 s. Asi el juego corre a la misma
        # velocidad a 30, 60, 120, 144, 240 FPS o sin limite.
        sim_accumulator += frame_ms
        max_accumulated = FIXED_DT_MS * MAX_SIM_STEPS
        if sim_accumulator > max_accumulated:
            sim_accumulator = max_accumulated  # descartar tiempo tras un tiron/pausa
        sim_steps = int(sim_accumulator / FIXED_DT_MS)
        sim_accumulator -= sim_steps * FIXED_DT_MS
        # Factor para efectos de RENDER dependientes del tiempo (transiciones): 1.0 a 60 FPS.
        render_scale = min(frame_ms / FIXED_DT_MS, float(MAX_SIM_STEPS))

        # Convertir coordenadas del raton real a la superficie virtual 16:9.
        raw_mx, raw_my = pygame.mouse.get_pos()
        mouse_x, mouse_y = window_to_virtual((raw_mx, raw_my), real_screen.get_size(), aspect_mode)

        keys = pygame.key.get_pressed()

        # Selección por defecto
        if game_state == "MAP" and (selected_node is None or engine.state[selected_node] == NodeState.CLEANED):
            unlocked = [n for n in engine.nodes if engine.state[n] == NodeState.UNLOCKED]
            if unlocked:
                selected_node = unlocked[0]
                if selected_node in map_gen.rooms:
                    _mv = map_view_rect()
                    camera_x = _mv.centerx - map_gen.rooms[selected_node].rect.centerx
                    camera_y = (_mv.top + 104 + _mv.bottom)//2 - map_gen.rooms[selected_node].rect.centery
                    camera_x, camera_y = clamp_map_camera(camera_x, camera_y)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if trans_state["active"]:
                continue

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                debug_collisions = not debug_collisions
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                editor_mode = not editor_mode
                if editor_mode:
                    debug_collisions = True # force display in editor mode
                else:
                    collision_manager = current_level.create_collision_manager()
                    pathfinder = PathFinder(current_level)
                    editor = CollisionEditor(current_level, collision_manager)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                debug_collision_labels = not debug_collision_labels
                if debug_collision_labels:
                    debug_collisions = True
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F4:
                debug_enemy_paths = not debug_enemy_paths

            if game_state == "TITLE_SCREEN":
                action = ui_action(title_screen, event, mouse_x, mouse_y)
                if action == "START":
                    main_menu.time = 0
                    trigger_transition("MAIN_MENU", "FADE", 0.03)

            elif game_state == "MAIN_MENU":
                action = ui_action(main_menu, event, mouse_x, mouse_y)
                if action == "Continuar Partida":
                    slot = save_mgr.get_latest_slot()
                    data = save_mgr.load_game(slot)
                    if data and load_saved_game_data(data):
                        current_slot = slot
                        trigger_transition("MAP", "CIRCLE", 0.04)
                    else:
                        main_menu.notification = "No hay partida guardada."
                        main_menu.notification_timer = 180
                elif action == "Nueva Partida":
                    current_slot_mode = "NUEVA"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
                elif action == "Cargar Partida":
                    current_slot_mode = "CARGAR"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
                elif action == "Tutorial":
                    tutorial_state.reset()
                    trigger_transition("TUTORIAL", "SLIDE_LEFT", 0.05)
                elif action == "Bestiario":
                    previous_state = "MAIN_MENU"
                    trigger_transition("BESTIARY", "PIXELATE", 0.03)
                elif action == "Opciones":
                    options_return_state = "MAIN_MENU"
                    trigger_transition("OPTIONS", "SLIDE_LEFT", 0.05)
                elif action == "Salir":
                    running = False
            elif game_state == "SLOT_SELECT":
                action = ui_action(slot_select_menu, event, mouse_x, mouse_y)
                if action == "Regresar":
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
                elif action and action.startswith("Slot"):
                    slot = int(action.split(" ")[1])
                    if current_slot_mode == "NUEVA":
                        current_slot = slot
                        engine = DagEngine()
                        map_gen = MapGenerator(engine)
                        semester_counter = 1
                        energy = 6
                        max_energy = 6
                        camera_x, camera_y = 0, 0
                        trigger_transition("MAP", "CIRCLE", 0.04)
                    elif current_slot_mode == "CARGAR":
                        data = save_mgr.load_game(slot)
                        if data and load_saved_game_data(data):
                            current_slot = slot
                            trigger_transition("MAP", "CIRCLE", 0.04)
            elif game_state == "PAUSE":
                action = ui_action(pause_menu, event, mouse_x, mouse_y)
                if action == "Continuar":
                    trigger_transition(previous_state, "FADE", 0.08)
                elif action == "Opciones":
                    options_return_state = "PAUSE"
                    trigger_transition("OPTIONS", "SLIDE_LEFT", 0.05)
                elif action == "Guardar y regresar al mapa":
                    save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                    trigger_transition("MAP", "CIRCLE", 0.04)
                elif action == "Guardar y Salir al menú principal":
                    save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
            elif game_state == "BESTIARY":
                action = ui_action(bestiary_menu, event, mouse_x, mouse_y)
                if action == "BACK":
                    if previous_state == "TUTORIAL":
                        tutorial_state.phase = 4 # TutorialPhase.OUTRO
                        tutorial_state.timer = 0
                        trigger_transition("TUTORIAL", "FADE", 0.05)
                    else:
                        trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
            elif game_state == "TUTORIAL":
                action = ui_action(tutorial_state, event, mouse_x, mouse_y)
                if action == "GO_TO_BESTIARY":
                    main_menu.unlock_bestiary()
                    previous_state = "TUTORIAL"
                    trigger_transition("BESTIARY", "PIXELATE", 0.03)
                elif action == "FINISH_TUTORIAL":
                    finish_tutorial()

            elif game_state == "OPTIONS":
                action = ui_action(options_menu, event, mouse_x, mouse_y)
                if action:
                    if action["action"] == "BACK":
                        trigger_transition(options_return_state, "SLIDE_RIGHT" if options_return_state == "MAIN_MENU" else "FADE", 0.05)
                    elif action["action"] == "APPLY":
                        res = action["res"]
                        fullscreen = action["fullscreen"]
                        gen_vol = action["gen_vol"]
                        aspect_mode = action.get("aspect_mode", aspect_mode)
                        fps_limit = sanitize_fps_limit(action.get("fps_limit", fps_limit))

                        global_data["resolution"] = res
                        global_data["fullscreen"] = fullscreen
                        global_data["aspect_mode"] = aspect_mode
                        global_data["volume"] = gen_vol
                        global_data["music_volume"] = action.get("mus_vol", global_data.get("music_volume", 100))
                        global_data["fps_limit"] = fps_limit
                        save_mgr.save_global_save(global_data)
                        audio.set_volumes(gen_vol, global_data["music_volume"])

                        # La ventana se recrea de forma robusta; la logica interna se
                        # mantiene en 1280x720 y solo cambia el escalado final (letterbox).
                        real_screen = apply_display_mode(res, fullscreen)
                        trigger_transition(options_return_state, "SLIDE_RIGHT" if options_return_state == "MAIN_MENU" else "FADE", 0.05)
            elif game_state == "MAP":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    previous_state = "MAP"
                    pause_menu.set_context(in_combat=False)
                    audio.play_sfx("pause")
                    trigger_transition("PAUSE", "FADE", 0.08)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 3: # Clic derecho para arrastrar
                        dragging = True
                        last_mouse_pos = event.pos
                    elif event.button == 1: # Clic izquierdo para seleccionar/entrar
                        clicked_node = map_gen.get_room_at(mouse_x, mouse_y, camera_x, camera_y)
                        if clicked_node and engine.state[clicked_node] == NodeState.UNLOCKED:
                            current_time = pygame.time.get_ticks()
                            if clicked_node == last_clicked_node and current_time - last_click_time < 500:
                                # Doble clic: entrar
                                selected_node = clicked_node
                                if energy > 0:
                                    start_combat(clicked_node)
                                else:
                                    map_message = "¡No hay suficiente energía! Descansa para avanzar de semestre."
                                    map_message_timer = 180
                            else:
                                # Un clic: seleccionar
                                selected_node = clicked_node
                                last_clicked_node = clicked_node
                                last_click_time = current_time

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3:
                        dragging = False

                elif event.type == pygame.MOUSEMOTION:
                    if dragging:
                        dx, dy = event.pos[0] - last_mouse_pos[0], event.pos[1] - last_mouse_pos[1]
                        camera_x += dx
                        camera_y += dy
                        camera_x, camera_y = clamp_map_camera(camera_x, camera_y)
                        last_mouse_pos = event.pos

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r or event.key == pygame.K_SPACE: # Descansar / Avanzar Semestre
                        energy = max_energy
                        semester_counter += 1
                        engine.update_unlocks()
                        rest_animation_timer = 90 # 1.5 seconds animation

                    elif event.key == pygame.K_RETURN: # Entrar con Enter
                        if selected_node and engine.state[selected_node] == NodeState.UNLOCKED:
                            if energy > 0:
                                start_combat(selected_node)
                            else:
                                map_message = "¡No hay suficiente energía! Descansa para avanzar de semestre."
                                map_message_timer = 180

                    elif event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                        if selected_node and selected_node in map_gen.rooms:
                            current_rect = map_gen.rooms[selected_node].rect
                            best_dist = float('inf')
                            best_node = None
                            for n, r in map_gen.rooms.items():
                                if n == selected_node or engine.state[n] == NodeState.CLEANED: continue
                                dx_ = r.rect.centerx - current_rect.centerx
                                dy_ = r.rect.centery - current_rect.centery
                                dist = math.hypot(dx_, dy_)

                                valid = False
                                if event.key == pygame.K_UP and dy_ < -abs(dx_): valid = True
                                elif event.key == pygame.K_DOWN and dy_ > abs(dx_): valid = True
                                elif event.key == pygame.K_LEFT and dx_ < -abs(dy_): valid = True
                                elif event.key == pygame.K_RIGHT and dx_ > abs(dy_): valid = True

                                if valid and dist < best_dist:
                                    best_dist = dist
                                    best_node = n
                            if best_node:
                                selected_node = best_node
                                target_room = map_gen.rooms[selected_node]
                                _mv = map_view_rect()
                                camera_x = _mv.centerx - target_room.rect.centerx
                                camera_y = (_mv.top + 104 + _mv.bottom)//2 - target_room.rect.centery
                                camera_x, camera_y = clamp_map_camera(camera_x, camera_y)

            elif game_state == "COMBAT":
                combat_defeat_active = combat_player and (combat_player.hp <= 0 or level_failed_timer > 0)
                if combat_defeat_active and not editor_mode:
                    continue

                if editor_mode:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                        dragging = True
                        last_mouse_pos = (mouse_x, mouse_y)
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                        dragging = False
                    elif event.type == pygame.MOUSEMOTION and dragging:
                        dx = mouse_x - last_mouse_pos[0]
                        dy = mouse_y - last_mouse_pos[1]
                        combat_cam_x += dx
                        combat_cam_y += dy
                        last_mouse_pos = (mouse_x, mouse_y)

                    editor.handle_event(event, mouse_x, mouse_y, combat_cam_x, combat_cam_y)
                    continue
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    previous_state = "COMBAT"
                    pause_menu.set_context(in_combat=True)
                    audio.play_sfx("pause")
                    trigger_transition("PAUSE", "FADE", 0.08)
                # Disparar con el ratón
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    combat_player.shoot_angle(math.atan2((mouse_y - combat_cam_y) - combat_player.y, (mouse_x - combat_cam_x) - combat_player.x))
            elif game_state == "WIN":
                if event.type == pygame.KEYDOWN:
                    save_mgr.delete_save(current_slot)
                    main_menu.notification = "¡Nuevo enemigo desbloqueado! La experiencia es rejugable."
                    main_menu.notification_timer = 300
                    trigger_transition("MAIN_MENU", "FADE", 0.05)
            elif game_state == "GAME_OVER":
                if event.type == pygame.KEYDOWN and (event.key == pygame.K_r or event.key == pygame.K_SPACE):
                    main()
                    return

        # Simulacion a PASO FIJO (60 Hz): se ejecuta 0, 1 o varias veces por frame de
        # render segun sim_steps, manteniendo la velocidad del juego constante a cualquier FPS.
        for _ in range(sim_steps):
            # Actualizaciones Continuas (teclas presionadas)
            if game_state == "DISCLAIMER_SCREEN":
                if disclaimer_screen.time > 200 and not trans_state["active"]:
                    trigger_transition("TITLE_SCREEN", "FADE", 0.03)
            elif game_state == "TUTORIAL":
                tutorial_action = tutorial_state.update(keys, WIDTH, HEIGHT, mouse_x, mouse_y)
                if tutorial_action == "FINISH_TUTORIAL":
                    finish_tutorial()
            elif game_state == "COMBAT":
                world_w, world_h = combat_world_size()
                if combat_player and combat_player.hp <= 0 and not level_failed_done:
                    begin_level_failure()

                if level_failed_timer > 0:
                    level_failed_timer -= 1
                    if level_failed_timer == 0:
                        level_failed_done = True
                        trigger_transition("MAP", "CIRCLE", 0.04)
                elif not editor_mode:
                    # Disparar con flechas (soporta diagonales)
                    dx, dy = 0, 0
                    if keys[pygame.K_UP]: dy -= 1
                    if keys[pygame.K_DOWN]: dy += 1
                    if keys[pygame.K_LEFT]: dx -= 1
                    if keys[pygame.K_RIGHT]: dx += 1

                    if dx != 0 or dy != 0:
                        combat_player.shoot_angle(math.atan2(dy, dx))

                    # Mouse drag shooting
                    if pygame.mouse.get_pressed()[0]:
                        combat_player.shoot_angle(math.atan2((mouse_y - combat_cam_y) - combat_player.y, (mouse_x - combat_cam_x) - combat_player.x))

                    combat_player.move(keys, world_w, world_h, collision_manager)
                    combat_player.update_bullets(world_w, world_h)
                    apply_player_hazard_damage()

                    update_combat_camera(smooth=True)

                    for enemy in enemies:
                        enemy.update(combat_player.x, combat_player.y, world_w, world_h, collision_manager, pathfinder=pathfinder, nearby_enemies=enemies)

                        if isinstance(enemy, MiniBoss):
                            bestiary_menu.unlock("MINI BOSS (PARCIAL)")
                        elif isinstance(enemy, Boss):
                            bestiary_menu.unlock("MEGA BOSS (TITULACIÓN)")

                        # El jugador recibe daño por contacto
                        if enemy.collides_with_player(combat_player) and enemy.attack_cooldown == 0:
                            combat_player.hp -= 20 if isinstance(enemy, (MiniBoss, Boss)) else 10
                            enemy.attack_cooldown = 45 if isinstance(enemy, (MiniBoss, Boss)) else 30
                            audio.play_sfx("hurt")

                        # El jugador recibe daño por balas enemigas
                        for b in enemy.bullets[:]:
                            dist = math.hypot(combat_player.x - b.x, combat_player.y - b.y)
                            if dist < (combat_player.radius + b.radius):
                                combat_player.hp -= 15
                                audio.play_sfx("hurt")
                                if b in enemy.bullets:
                                    enemy.bullets.remove(b)

                        if hasattr(enemy, "collect_area_damage_events"):
                            for hit in enemy.collect_area_damage_events(combat_player):
                                combat_player.hp -= hit["damage"]
                                audio.play_sfx("hurt")
                                floating_texts.append({
                                    "text": str(hit["damage"]),
                                    "x": hit["x"],
                                    "y": hit["y"] - 35,
                                    "life": 45,
                                    "color": (255, 125, 45)
                                })

                    # Las balas golpean a los enemigos
                    for b in combat_player.bullets[:]:
                        for e in enemies[:]:
                            if e.collides_with_bullet(b):
                                damage = 10
                                e.hp -= damage
                                audio.play_sfx("hit")

                                # Generar texto flotante de daño
                                floating_texts.append({
                                    "text": str(damage),
                                    "x": e.x,
                                    "y": e.y - 20,
                                    "life": 40,
                                    "color": (255, 50, 50)
                                })

                                if b in combat_player.bullets:
                                    combat_player.bullets.remove(b)
                                if e.hp <= 0:
                                    enemies.remove(e)
                                    audio.play_sfx("enemy_die")

                    # Actualizar textos flotantes
                    for ft in floating_texts[:]:
                        ft["y"] -= 1.5  # Subir
                        ft["life"] -= 1 # Desvanecerse
                        if ft["life"] <= 0:
                            floating_texts.remove(ft)

                    # Spawnear nuevas rondas
                    if current_wave < max_waves:
                        wave_timer -= 1
                        if wave_timer <= 0:
                            current_wave += 1
                            wave_timer = 300 # Reset timer para la siguiente ola

                            # Spawn desde la puerta del nivel activo
                            door_x, door_y = int(world_w * 0.85), int(world_h * 0.22)
                            enemy_types = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]

                            for _ in range(random.randint(3, 5)):
                                ex = door_x + random.randint(-20, 20)
                                ey = door_y + random.randint(-20, 20)
                                enemies.append(spawn_enemy(random.choice(enemy_types), [(ex, ey)]))

                            if current_wave == max_waves and is_miniboss_room(current_room):
                                enemies.append(spawn_enemy(MiniBoss, [(door_x, door_y)]))

                    # Revisar si la habitación está limpia (solo si ya estamos en la última ronda)
                    if current_wave == max_waves and not enemies:
                        if level_passed_timer == 0 and not level_passed_done:
                            level_passed_timer = 120 # 2 segundos
                            audio.play_sfx("level_clear")

                        if level_passed_timer > 0:
                            level_passed_timer -= 1
                            if level_passed_timer == 0:
                                level_passed_done = True
                                engine.clean_room(current_room)
                                engine.update_unlocks()

                                # AUTOSAVE
                                save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                                save_indicator_timer = 120

                                if current_room == FINAL_BOSS_ROOM_ID:
                                    global_data["bestiary_unlocks"] = list(set(global_data.get("bestiary_unlocks", []) + ["MEGA BOSS (TITULACION)"]))
                                    save_mgr.save_global_save(global_data)
                                    bestiary_menu.unlocked_names = global_data["bestiary_unlocks"]

                                    trigger_transition("WIN", "FADE", 0.02)
                                else:
                                    trigger_transition("MAP", "CIRCLE", 0.04)

                    if combat_player.hp <= 0:
                        begin_level_failure()

            # Temporizadores de UI a 60 Hz (independientes del FPS de render).
            if rest_animation_timer > 0:
                rest_animation_timer -= 1
            if map_message_timer > 0:
                map_message_timer -= 1
            if save_indicator_timer > 0:
                save_indicator_timer -= 1

        # Dibujado
        screen.fill(BG_COLOR)

        # Área realmente visible: las pantallas de UI anclan a ella sus elementos de
        # borde para que 'fill' no los recorte en monitores no 16:9 (en 'fit' es toda
        # la superficie, así que no cambia nada).
        _ui_view = ui_safe_rect()
        for _ui in (disclaimer_screen, title_screen, main_menu, slot_select_menu,
                    options_menu, bestiary_menu, pause_menu, tutorial_state):
            if _ui is not None:
                _ui.safe_rect = _ui_view

        if game_state == "DISCLAIMER_SCREEN":
            disclaimer_screen.draw(screen)
        elif game_state == "TITLE_SCREEN":
            title_screen.draw(screen)
        elif game_state in ["MAIN_MENU", "SLOT_SELECT"]:
            main_menu.draw(screen, mouse_x, mouse_y)
            if game_state == "SLOT_SELECT":
                slot_select_menu.draw(screen)
        elif game_state == "OPTIONS":
            options_menu.draw(screen)
        elif game_state == "BESTIARY":
            bestiary_menu.draw(screen)
        elif game_state == "TUTORIAL":
            tutorial_state.draw(screen)
        elif game_state == "MAP" or (game_state == "PAUSE" and previous_state == "MAP"):
            if MAP_BG_IMG:
                screen.blit(MAP_BG_IMG, (0, 0))
            # Viñeteado/degradado ambiental sutil (detras de nodos y aristas).
            screen.blit(get_map_overlay(), (0, 0))

            map_gen.draw(screen, font_sm, camera_x, camera_y)

            if selected_node and selected_node in map_gen.rooms:
                sel_rect = map_gen.rooms[selected_node].rect.copy()
                sel_rect.x += camera_x
                sel_rect.y += camera_y
                draw_selection_highlight(screen, sel_rect)
                draw_subject_tooltip(screen, engine, selected_node, sel_rect)

            # HUD superior del mapa (panel pixel-art con cristales de energia).
            # Se ancla al área visible para no recortarse en modo 'fill'.
            draw_map_hud(screen, semester_counter, par_score, energy, max_energy,
                         get_visible_virtual_rect(real_screen.get_size(), aspect_mode))

            # Animación de descanso (el contador se decrementa en la simulación a 60 Hz)
            if rest_animation_timer > 0:
                alpha = int((rest_animation_timer / 90) * 255)

                overlay = pygame.Surface((WIDTH, HEIGHT))
                overlay.set_alpha(alpha // 3) # Capa semitransparente verde
                overlay.fill((50, 200, 50))
                screen.blit(overlay, (0, 0))

                # Textos flotantes
                offset_y = (90 - rest_animation_timer) * 1.5 # Sube progresivamente
                msg = font_lg.render("Zzz... DESCANSO COMPLETADO", True, (150, 255, 150))
                msg.set_alpha(alpha)
                screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - offset_y)))

                msg2 = font_md.render("¡ENERGÍA RESTAURADA AL MÁXIMO!", True, (255, 255, 255))
                msg2.set_alpha(alpha)
                screen.blit(msg2, msg2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50 - offset_y)))

            if map_message_timer > 0:
                msg_surf = font_md.render(map_message, True, (255, 100, 100))
                msg_rect = msg_surf.get_rect(center=(WIDTH // 2, HEIGHT - 50))

                # Dark background
                bg_rect = msg_rect.inflate(20, 10)
                s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                s.fill((0, 0, 0, 180))
                screen.blit(s, bg_rect.topleft)
                screen.blit(msg_surf, msg_rect)

        elif game_state == "COMBAT" or (game_state == "PAUSE" and previous_state == "COMBAT"):
            draw_floor(screen, combat_bg_img, combat_cam_x, combat_cam_y)
            for e in enemies:
                if hasattr(e, "draw_area_ground_effects"):
                    e.draw_area_ground_effects(screen, combat_cam_x, combat_cam_y)
            combat_player.draw(screen, combat_cam_x, combat_cam_y)
            for e in enemies:
                e.draw(screen, combat_cam_x, combat_cam_y)

            # Dibujar textos flotantes de daño
            for ft in floating_texts:
                alpha = min(255, int((ft["life"] / 40.0) * 255))
                dmg_surf = font_md.render(ft["text"], True, ft["color"])
                dmg_surf.set_alpha(alpha)
                rect = dmg_surf.get_rect(center=(int(ft["x"] + combat_cam_x), int(ft["y"] + combat_cam_y)))
                screen.blit(dmg_surf, rect)

            if debug_enemy_paths and pathfinder:
                draw_enemy_ai_debug(
                    screen,
                    enemies,
                    pathfinder,
                    camera=(combat_cam_x, combat_cam_y),
                    font=font_sm,
                    player_pos=(combat_player.x, combat_player.y),
                )

            if editor_mode:
                editor.draw(screen, combat_cam_x, combat_cam_y,
                            safe_rect=get_visible_virtual_rect(real_screen.get_size(), aspect_mode))
            elif debug_collisions and collision_manager:
                collision_manager.draw_debug(
                    screen,
                    camera=(combat_cam_x, combat_cam_y),
                    font=font_sm,
                    show_names=debug_collision_labels,
                )
                current_level.draw_hazard_debug(
                    screen,
                    camera=(combat_cam_x, combat_cam_y),
                    font=font_sm,
                    show_names=debug_collision_labels,
                )

                p_rect = combat_player.rect.move(combat_cam_x, combat_cam_y)
                p_hit = combat_player.last_collision.get("x") or combat_player.last_collision.get("y")
                pygame.draw.rect(screen, (255, 80, 80) if p_hit else (0, 255, 255), p_rect, 2)
                for e in enemies:
                    e_rect = e.rect.move(combat_cam_x, combat_cam_y)
                    e_hit = e.last_collision.get("x") or e.last_collision.get("y")
                    pygame.draw.rect(screen, (255, 80, 80) if e_hit else (255, 80, 180), e_rect, 1)

                if debug_collision_labels:
                    debug_lines = [
                        f"Nivel: {current_level.name}  Mundo: {current_level.width}x{current_level.height}",
                        f"Jugador: {int(combat_player.x)}, {int(combat_player.y)}  Bloqueo: X={combat_player.last_collision.get('x')} Y={combat_player.last_collision.get('y')}",
                        "F1: debug colisiones | F2: Modo Editor | F3: etiquetas | F4: rutas IA",
                    ]
                    # Anclado al área visible para que el modo 'fill' no lo recorte.
                    debug_safe = get_visible_virtual_rect(real_screen.get_size(), aspect_mode)
                    info_y = debug_safe.top + 68
                    for line in debug_lines:
                        text_surf = font_sm.render(line, True, (255, 255, 255))
                        bg = pygame.Surface((text_surf.get_width() + 10, text_surf.get_height() + 6), pygame.SRCALPHA)
                        bg.fill((0, 0, 0, 170))
                        screen.blit(bg, (debug_safe.left + 12, info_y))
                        screen.blit(text_surf, (debug_safe.left + 17, info_y + 3))
                        info_y += text_surf.get_height() + 8

            # UI de Combate - Panel superior
            combat_ui_rect = get_visible_virtual_rect(real_screen.get_size(), aspect_mode)
            ui_left = combat_ui_rect.left
            ui_right = combat_ui_rect.right
            ui_top = combat_ui_rect.top
            ui_margin = 15

            hud_rect = pygame.Surface((WIDTH, 60))
            hud_rect.set_alpha(180)
            hud_rect.fill((10, 10, 10))
            screen.blit(hud_rect, (0, ui_top))
            pygame.draw.line(screen, (150, 150, 150), (0, ui_top + 60), (WIDTH, ui_top + 60), 2)

            # Dibujar barra de vida grafica del jugador (Top-Left)
            life_right = ui_left + ui_margin
            if HEART_FRAMES and len(HEART_FRAMES) == 5:
                max_hearts = 7
                hp_per_heart = combat_player.max_hp / max_hearts

                # Suavizar la animacion de perdida de vida
                if not hasattr(combat_player, 'display_hp'):
                    combat_player.display_hp = combat_player.hp
                if combat_player.display_hp > combat_player.hp:
                    combat_player.display_hp -= 2.0  # Animacion rapida
                elif combat_player.display_hp < combat_player.hp:
                    combat_player.display_hp = combat_player.hp

                current_hp = combat_player.display_hp

                bar_x = ui_left + ui_margin
                bar_y = ui_top + 15
                for i in range(max_hearts):
                    heart_hp = current_hp - (i * hp_per_heart)
                    heart_hp = max(0, min(hp_per_heart, heart_hp))
                    fraction = heart_hp / hp_per_heart
                    frame_idx = int(round(fraction * 4)) # 0 a 4 (5 fotogramas)
                    frame_idx = max(0, min(4, frame_idx))

                    screen.blit(HEART_FRAMES[frame_idx], (bar_x + i * 32, bar_y)) # Separacion ajustada (32px)
                life_right = bar_x + max_hearts * 32
            else:
                hp_text = font_md.render("Vida:", False, (255, 255, 255))
                hp_x = ui_left + ui_margin
                screen.blit(hp_text, (hp_x, ui_top + 15))

                bar_x = hp_x + hp_text.get_width() + 10
                bar_y = ui_top + 18
                bar_w = 200
                bar_h = 24

                hp_ratio = max(0, combat_player.hp / combat_player.max_hp)
                pygame.draw.rect(screen, (80, 20, 20), (bar_x, bar_y, bar_w, bar_h)) # Fondo de la barra
                pygame.draw.rect(screen, (255, 50, 50), (bar_x, bar_y, bar_w * hp_ratio, bar_h)) # Relleno de vida
                pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 2) # Borde de la barra

                # Texto de vida numerico
                hp_num = font_sm.render(f"{max(0, int(combat_player.hp))}/{combat_player.max_hp}", False, (255, 255, 255))
                screen.blit(hp_num, (bar_x + bar_w//2 - hp_num.get_width()//2, bar_y + 2))
                life_right = bar_x + bar_w

            # Titulo de la sala (Top-Right)
            room_name = engine.subjects[current_room]['name']
            title = f"Limpiando: {room_name}"
            title_color = (255, 255, 255)

            if current_room in engine.critical_nodes:
                title += " [CAMINO CRITICO]"
                title_color = engine.node_colors.get(current_room, (255, 100, 100))

            room_ts_max_w = max(120, ui_right - life_right - 40)
            room_ts = render_text_fit(font_md, title, title_color, room_ts_max_w, antialias=False)
            room_x = max(life_right + 20, ui_right - room_ts.get_width() - 20)
            screen.blit(room_ts, (room_x, ui_top + 15))
            if current_wave == max_waves and not enemies and level_passed_timer > 0:
                msg_surf = font_lg.render("¡NIVEL SUPERADO!", True, (100, 255, 100))
                msg_rect = msg_surf.get_rect(center=(WIDTH // 2, HEIGHT // 3))
                # Text shadow
                shadow_surf = font_lg.render("¡NIVEL SUPERADO!", True, (0, 50, 0))
                screen.blit(shadow_surf, (msg_rect.x + 3, msg_rect.y + 3))
                screen.blit(msg_surf, msg_rect)

            if level_failed_timer > 0:
                draw_defeat_sequence(screen, combat_player, combat_cam_x, combat_cam_y, level_failed_timer, DEFEAT_SEQUENCE_FRAMES)

        elif game_state == "WIN":
            draw_centered_text_fit(
                screen,
                f"¡PROYECTO DE TITULACION APROBADO! ¡HAS GANADO!",
                font_lg,
                (WIDTH // 2, HEIGHT // 2 - 60),
                (0, 255, 0),
                WIDTH - 80,
                antialias=False,
            )
            draw_centered_text_fit(
                screen,
                f"Te tomo {semester_counter} Semestres. (El record ideal era {par_score})",
                font_md,
                (WIDTH // 2, HEIGHT // 2),
                TEXT_COLOR,
                WIDTH - 100,
                antialias=False,
            )
            draw_centered_text_fit(
                screen,
                "Presiona cualquier tecla para regresar al menu.",
                font_md,
                (WIDTH // 2, HEIGHT // 2 + 50),
                TEXT_COLOR,
                WIDTH - 100,
                antialias=False,
            )
        elif game_state == "GAME_OVER":
            draw_centered_text_fit(
                screen,
                "TE HAS QUEDADO SIN ENERGIA.",
                font_lg,
                (WIDTH // 2, HEIGHT // 2 - 50),
                (255, 0, 0),
                WIDTH - 80,
                antialias=False,
            )
            draw_centered_text_fit(
                screen,
                "Presiona 'R' para reintentar el nivel.",
                font_md,
                (WIDTH // 2, HEIGHT // 2 + 50),
                TEXT_COLOR,
                WIDTH - 100,
                antialias=False,
            )
        if game_state == "PAUSE":
            pause_menu.draw(screen)

        # Renderizar transición (el contador se decrementa en la simulación a 60 Hz)
        if save_indicator_timer > 0:
            # Fondo oscuro semitransparente
            s = pygame.Surface((180, 50), pygame.SRCALPHA)
            s.fill((0, 0, 0, 100)) # Alpha mucho más transparente (antes 200)
            screen.blit(s, (WIDTH - 200, HEIGHT - 70))

            # Círculo e icono (tamaño intermedio)
            icon_x, icon_y = WIDTH - 170, HEIGHT - 45
            if SAVE_ICON_IMG:
                scale_factor = 1.0 + 0.15 * abs(math.sin(save_indicator_timer * 0.1))
                new_w = int(SAVE_ICON_IMG.get_width() * scale_factor)
                new_h = int(SAVE_ICON_IMG.get_height() * scale_factor)
                scaled_img = pygame.transform.smoothscale(SAVE_ICON_IMG, (new_w, new_h))
                img_rect = scaled_img.get_rect(center=(icon_x, icon_y))
                screen.blit(scaled_img, img_rect)
            else:
                pygame.draw.circle(screen, (100, 255, 100), (icon_x, icon_y), 17, 3)
                arc_angle = (save_indicator_timer * 12) % 360
                pygame.draw.arc(screen, (255, 255, 255), (icon_x - 17, icon_y - 17, 34, 34), math.radians(arc_angle), math.radians(arc_angle+100), 4)

            # Texto
            s_text = font_sm.render("Guardando...", True, (255, 255, 255))
            screen.blit(s_text, (icon_x + 25, icon_y - s_text.get_height()//2))

        if trans_state["active"]:
            # Escalado por tiempo real para que la duración sea igual a cualquier FPS.
            trans_state["progress"] += trans_state["speed"] * render_scale
            if trans_state["progress"] >= 1.0:
                trans_state["progress"] = 1.0
                trans_state["active"] = False

            # Dibujamos encima del 'screen' que ya tiene el nuevo estado
            render_transition(screen, trans_state["old_surf"], screen.copy(), trans_state["type"], trans_state["progress"], WIDTH, HEIGHT)

        # Escalado final: mantiene 16:9 sin deformar. fit deja barras; fill llena la
        # pantalla (recortando bordes). El contenido pegado a los bordes se ancló antes
        # al área visible (ui_safe_rect / safe_rect) para que fill no lo corte.
        present_virtual_surface(screen, real_screen, aspect_mode)

        pygame.display.flip()

if __name__ == "__main__":
    main()
    pygame.quit()
    sys.exit()
