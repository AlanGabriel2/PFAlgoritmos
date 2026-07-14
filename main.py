import pygame
import sys
import os

# En la version compilada, todas las rutas relativas deben partir de la carpeta
# que contiene el .exe aunque se abra desde un acceso directo u otro directorio.
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

# Windows agrupa las ventanas en la barra de tareas por AppUserModelID. Definir
# uno propio evita que SDL/Pygame herede una identidad e icono genericos.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MegaCalabozoDAG.Game.1"
        )
    except (AttributeError, OSError):
        pass

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
from menu import MainMenu, BestiaryMenu, PauseMenu, TitleScreen, OptionsMenu, DisclaimerScreen, PlaySubMenu, SlotSelectMenu, draw_energy_crystal
from tutorial import TutorialState
from gamepad import GamepadManager, localize as gp_localize, render_prompt_line as gp_prompt_line
import audio

# Buffer estable para musica en streaming y efectos con baja latencia.
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.init()

# Icono de la ventana (titulo, Alt+Tab y barra de tareas). El icono incrustado
# por PyInstaller cubre el Explorador; SDL necesita recibirlo por separado.
try:
    pygame.display.set_icon(pygame.image.load("assets/images/ui/game_icon.png"))
except (pygame.error, FileNotFoundError) as e:
    print("No se pudo cargar el icono de la ventana:", e)

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
# Enemigos comunes y su peso de aparicion. El Bug es el mas debil y basico,
# asi que domina las oleadas; los mas duros aparecen con menos frecuencia.
COMMON_ENEMY_TYPES = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]
COMMON_ENEMY_WEIGHTS = [5, 2, 2, 1]
MAP_HUD_H = 140  # alto de la franja del HUD del mapa (los iconos de mando necesitan aire)
MAP_GAMEPAD_PAN_SPEED = 12.0  # pixeles por paso fijo al mover la camara con el stick derecho
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
    font_heading = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 40)
    font_lg = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 56)
    font_title = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 100)
except:
    font_sm = pygame.font.SysFont("Arial", 16)
    font_md = pygame.font.SysFont("Arial", 24)
    font_heading = pygame.font.SysFont("Arial", 36, bold=True)
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

def _combat_scales():
    """Escalas de personaje que usan los niveles.

    Precalentar los sprites a su tamaño real (no solo a 1.0) evita el tiron la
    primera vez que se entra a cada tipo de sala; en los niveles de jefe la
    escala es 0.7 y el Boss ademas la multiplica por su SCALE_FACTOR, asi que
    el reescalado de sus hojas (1408x704) se pagaba en pleno combate.
    """
    scales = {1.0}
    try:
        import json, glob, os
        for path in glob.glob(os.path.join("levels", "*.json")):
            try:
                with open(path, encoding="utf-8") as fh:
                    scales.add(round(float(json.load(fh).get("character_scale", 0.7)), 3))
            except Exception:
                continue
    except Exception:
        pass
    return tuple(sorted(scales))

_preload_scales = _combat_scales()
preload_combat_assets(scales=_preload_scales)
try:
    for _scale in _preload_scales:
        Player(0, 0, scale=_scale)  # calienta el spritesheet del jugador a cada escala
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
    else:
        pygame.draw.rect(surface, (40, 30, 30), (0, 0, WIDTH, HEIGHT))


def draw_boss_health_bar(surface, boss, safe_rect, font):
    """Barra pixel-art legible para minibosses y el jefe final."""
    if boss is None or boss.max_hp <= 0:
        return
    ratio = max(0.0, min(1.0, boss.hp / boss.max_hp))
    bar_w = min(520, safe_rect.width - 80)
    bar_h = 22
    bar_x = safe_rect.centerx - bar_w // 2
    # El HUD del jugador ocupa los primeros 60 px. La barra del jefe vive
    # debajo de esa franja para que los corazones nunca la oculten.
    bar_y = safe_rect.top + 78
    outer = pygame.Rect(bar_x - 4, bar_y - 4, bar_w + 8, bar_h + 8)
    pygame.draw.rect(surface, (12, 9, 16), outer)
    pygame.draw.rect(surface, (220, 180, 125), outer, 2)
    pygame.draw.rect(surface, (50, 18, 25), (bar_x, bar_y, bar_w, bar_h))
    fill_w = int(bar_w * ratio)
    if fill_w > 0:
        color = (205, 42, 54) if ratio > 0.25 else (245, 92, 48)
        pygame.draw.rect(surface, color, (bar_x, bar_y, fill_w, bar_h))
        pygame.draw.rect(surface, (255, 130, 92), (bar_x, bar_y, fill_w, 4))
    label = "MEGA BOSS" if isinstance(boss, Boss) else "MINI BOSS"
    text = font.render(f"{label}  {max(0, int(boss.hp))}/{boss.max_hp}", False, (255, 240, 220))
    surface.blit(text, text.get_rect(center=(safe_rect.centerx, bar_y + bar_h // 2)))



def render_text_fit(font, text, color, max_width, antialias=False):
    text_surface = font.render(text, antialias, color)
    if text_surface.get_width() <= max_width:
        return text_surface

    # Nunca comprimir un bitmap de texto pixel-art: al reducirlo desaparecen
    # columnas de los glifos. Conservamos el tamaño nativo y abreviamos.
    suffix = "..."
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = font.render(text[:mid].rstrip() + suffix, antialias, color)
        if candidate.get_width() <= max_width:
            low = mid
        else:
            high = mid - 1
    return font.render(text[:low].rstrip() + suffix, antialias, color)


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

    if aspect_mode == "pixel_perfect":
        # La escala entera es la única que garantiza que cada píxel lógico ocupe
        # exactamente N×N píxeles físicos. En ventanas menores al lienzo base se
        # usa fit como salvaguarda para que la interfaz siga siendo utilizable.
        fit_scale = min(target_w / WIDTH, target_h / HEIGHT)
        scale = float(max(1, int(fit_scale))) if fit_scale >= 1.0 else fit_scale
    elif aspect_mode == "fill":
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


def draw_map_hud(surface, semester, par, energy, max_energy, view=None):
    """HUD superior del mapa: barra plana pixel-art con bordes duros.

    Se ancla al área realmente visible (`view`) para que en modo 'fill' —que
    recorta los bordes de la superficie virtual— la barra no quede cortada.
    Los ejes X se reanclan proporcionalmente al ancho visible; el eje Y solo se
    desplaza hacia el borde superior visible.
    """
    HUD_H = MAP_HUD_H
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

    cs = gp_prompt_line(font_sm, "WASD Mover   -   Flechas/Mouse Disparar   -   ENTER Entrar   -   ESPACIO Descansar   -   ESC_PAUSA Pausa",
                        MAP_UI["text_dim"], antialias=False)
    # Los iconos se mantienen en su posicion; la barra crecio hacia abajo, asi que
    # el offset desde el fondo sube para dejar mas aire entre iconos y la linea.
    surface.blit(cs, cs.get_rect(center=(X(WIDTH // 2), Y(HUD_H - 38))))


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


def draw_subject_tooltip(surface, engine, selected_node, sel_rect, view=None):
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

    # En modo fill el área visible puede ser menor que el lienzo virtual.
    if view is None:
        view = pygame.Rect(0, 0, WIDTH, HEIGHT)

    # Misma logica que antes: al lado derecho del nodo y se voltea si no cabe.
    tt_x = sel_rect.right + 15
    tt_y = sel_rect.top
    if tt_x + tt_w > view.right:
        tt_x = sel_rect.left - tt_w - 15
    tt_x = max(view.left + 8, tt_x)
    tt_y = max(view.top + 8, min(tt_y, view.bottom - 8 - tt_h))

    draw_pixel_panel(surface, (tt_x, tt_y, tt_w, tt_h), title_h=title_h, accent=MAP_UI["accent"])
    surface.blit(title_surf, (tt_x + pad, tt_y + 6))
    cy = tt_y + title_h + 5
    for s in body:
        surface.blit(s, (tt_x + pad, cy))
        cy += line_h


def enemy_die_sfx_names(enemy):
    """Efecto de muerte según el tipo de enemigo, con fallback al genérico."""
    if isinstance(enemy, Boss):
        return ("enemy_die_boss", "enemy_die_miniboss", "enemy_die")
    if isinstance(enemy, MiniBoss):
        return ("enemy_die_miniboss", "enemy_die")
    if isinstance(enemy, BugEnemy):
        return ("enemy_die_bug", "enemy_die")
    if isinstance(enemy, SpaghettiEnemy):
        return ("enemy_die_spaghetti", "enemy_die")
    if isinstance(enemy, MemoryLeakEnemy):
        return ("enemy_die_memoryleak", "enemy_die")
    if isinstance(enemy, DeadlineEnemy):
        return ("enemy_die_deadline", "enemy_die")
    return ("enemy_die",)


def combat_music_candidates_for_room(room_id):
    """Selecciona la intensidad musical según el semestre real de la materia."""
    semester_key = level_key_from_room_id(room_id)
    try:
        room_semester = int(semester_key[1:])
    except (TypeError, ValueError):
        room_semester = 1

    if room_semester >= 7:
        return ("combat_s3", "combat_s2", "combat", "map", "menu")
    if room_semester >= 4:
        return ("combat_s2", "combat", "map", "menu")
    return ("combat", "map", "menu")


def main():
    save_mgr = save_manager
    global_data = save_mgr.load_global_save()
    global screen, real_screen
    clock = pygame.time.Clock()
    gamepad = GamepadManager()
    gamepad.set_preferences(
        rumble_enabled=global_data.get("gamepad_rumble", True),
        deadzone_name=global_data.get("gamepad_deadzone", "media"),
    )

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
    # 'fit' como default: en monitores 1080p el modo pixel-perfect cae a escala
    # x1 (1280x720 centrado con bordes enormes), asi que se deja como opt-in.
    if aspect_mode not in ("pixel_perfect", "fit", "fill"):
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
        hud_h = MAP_HUD_H    # franja del HUD superior dentro del área visible

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
    combat_bg_img = None
    debug_collisions = False
    debug_collision_labels = False
    debug_enemy_paths = False
    editor_mode = False
    editor = CollisionEditor(current_level, collision_manager)
    gamepad_status_text = gamepad.consume_status_message() or ""
    gamepad_status_timer = 240 if gamepad_status_text else 0

    combat_cam_x, combat_cam_y = 0, 0
    hit_stop_frames = 0
    screen_shake_timer = 0
    screen_shake_duration = 0
    screen_shake_magnitude = 0.0

    current_wave = 1
    max_waves = 1
    wave_timer = 0

    floating_texts = [] # Lista para almacenar los números de daño flotantes
    player_hazard_cooldown = 0
    death_effects = []  # esquirlas de píxeles de enemigos muriendo
    bullet_impacts = []  # chispas de proyectiles contra objetos sólidos
    combat_stats = {"damage": 0, "kills": 0, "start_ms": 0, "end_ms": 0}  # resumen post-combate
    map_unlock_effects = []  # anillos de "materia desbloqueada" en el mapa
    win_selected = 0
    win_time = 0
    win_bg_img = None

    def trigger_combat_feedback(stop_frames=0, shake_magnitude=0.0, shake_frames=0):
        nonlocal hit_stop_frames, screen_shake_timer, screen_shake_duration, screen_shake_magnitude
        hit_stop_frames = max(hit_stop_frames, int(stop_frames))
        if shake_frames > 0 and shake_magnitude > 0:
            screen_shake_timer = max(screen_shake_timer, int(shake_frames))
            screen_shake_duration = max(screen_shake_duration, int(shake_frames))
            screen_shake_magnitude = max(screen_shake_magnitude, float(shake_magnitude))

    def capture_unlocks(states_before):
        """Registra las materias recién desbloqueadas para celebrarlas en el mapa."""
        newly = [n for n in engine.nodes
                 if states_before.get(n) == NodeState.LOCKED and engine.state[n] == NodeState.UNLOCKED]
        for n in newly:
            map_unlock_effects.append({"node": n, "timer": 180, "max": 180})
        if newly:
            audio.play_sfx("unlock", "level_clear")

    def recommended_node():
        """Materia disponible que conviene jugar: prioriza las que pertenecen a un
        camino crítico (no atrasarlas es lo que protege el Tiempo Récord) y entre
        ellas la de cadena de prerrequisitos más larga."""
        unlocked = [n for n in engine.nodes if engine.state[n] == NodeState.UNLOCKED]
        if not unlocked:
            return None
        critical = [n for n in unlocked if n in engine.critical_nodes]
        pool = critical or unlocked
        return max(pool, key=lambda n: engine.dp.get(n, 0))

    def spawn_death_effect(enemy):
        """Rompe el sprite del enemigo en esquirlas de píxeles que salen despedidas.

        Sin transparencias ni escalado suave: bloques del propio sprite que se
        encogen hasta desaparecer, acorde al lenguaje pixel del juego.
        """
        image = enemy.animator.get_current_image()
        if not image:
            return
        w, h = image.get_size()
        block = max(6, min(w, h) // 8)  # ~8x8 esquirlas por lado, mínimo 6px
        for by in range(0, h, block):
            for bx in range(0, w, block):
                rect = pygame.Rect(bx, by, min(block, w - bx), min(block, h - by))
                piece = image.subsurface(rect)
                if piece.get_bounding_rect(min_alpha=20).width == 0:
                    continue  # esquirla vacía (fuera de la silueta)
                px = enemy.x - w / 2 + bx + rect.w / 2
                py = enemy.y - h / 2 + by + rect.h / 2
                angle = math.atan2(py - enemy.y, px - enemy.x) + random.uniform(-0.6, 0.6)
                if isinstance(enemy, Boss):
                    speed = random.uniform(2.2, 6.2)
                    life = random.randint(45, 90)
                else:
                    speed = random.uniform(1.2, 3.4)
                    life = random.randint(14, 26)
                death_effects.append({
                    "piece": piece.copy(),
                    "x": px, "y": py,
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "life": life, "max": life,
                })

    def spawn_bullet_impact(impact):
        """Crea un abanico breve de chispas en dirección contraria al disparo."""
        reverse_angle = math.atan2(-impact["dy"], -impact["dx"])
        for _ in range(random.randint(5, 8)):
            angle = reverse_angle + random.uniform(-1.15, 1.15)
            speed = random.uniform(1.5, 4.0)
            life = random.randint(8, 16)
            bullet_impacts.append({
                "x": impact["x"],
                "y": impact["y"],
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": life,
                "max": life,
                "size": random.randint(2, 4),
                "color": random.choice(((80, 255, 255), (0, 210, 230), (220, 255, 255))),
            })

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
        if target == "TUTORIAL":
            return ("tutorial", "menu")
        if target == "MAP":
            return ("map", "menu")
        if target == "COMBAT":
            if current_room == FINAL_BOSS_ROOM_ID:
                return ("boss_final", "boss", "combat", "map", "menu")
            if is_miniboss_room(current_room):
                return ("boss", "combat", "map", "menu")
            return combat_music_candidates_for_room(current_room)
        if target == "WIN":
            return ("win", "menu")
        return None

    def trigger_transition(target, t_type="FADE", speed=0.04):
        nonlocal game_state, win_selected, win_time, win_bg_img
        source_state = game_state
        leaving_combat = source_state == "COMBAT" or (
            source_state == "PAUSE" and previous_state == "COMBAT"
        )
        if leaving_combat and target in ("MAP", "MAIN_MENU", "WIN"):
            audio.stop_all_sfx()
        trans_state["active"] = True
        trans_state["progress"] = 0.0
        trans_state["speed"] = speed
        trans_state["type"] = t_type
        trans_state["old_surf"] = screen.copy()
        game_state = target
        if target == "WIN":
            win_selected = 0
            win_time = 0
            win_bg_img = pygame.transform.scale(combat_bg_img, (WIDTH, HEIGHT)) if combat_bg_img else None
        candidates = music_candidates_for(target)
        if candidates:
            audio.play_music(*candidates)
        keep_music_ducked = target == "PAUSE" or (
            target == "OPTIONS" and options_return_state == "PAUSE"
        )
        audio.set_music_duck(keep_music_ducked)

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
        if not combat_player.take_damage(damage):
            return
        combat_stats["damage"] += damage
        audio.play_sfx("hurt")
        gamepad.rumble()
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
        nonlocal current_room, combat_player, enemies, current_wave, max_waves, wave_timer, energy, level_passed_timer, level_passed_done, level_failed_timer, level_failed_done, player_hazard_cooldown, hit_stop_frames, screen_shake_timer, screen_shake_duration, screen_shake_magnitude
        current_room = room_id
        load_room_level(current_room)
        trigger_transition("COMBAT", "CIRCLE", 0.03)
        energy -= 1
        level_passed_timer = 0
        level_passed_done = False
        level_failed_timer = 0
        level_failed_done = False
        player_hazard_cooldown = 0
        hit_stop_frames = 0
        screen_shake_timer = 0
        screen_shake_duration = 0
        screen_shake_magnitude = 0.0
        death_effects.clear()
        bullet_impacts.clear()
        combat_stats["damage"] = 0
        combat_stats["kills"] = 0
        combat_stats["start_ms"] = pygame.time.get_ticks()
        combat_stats["end_ms"] = 0

        world_w, world_h = combat_world_size()
        scale = current_level.character_scale if current_level else 1.0
        combat_player = Player(current_level.player_spawn[0], current_level.player_spawn[1], scale=scale)
        combat_player.rect.clamp_ip(pygame.Rect(0, 0, world_w, world_h))
        combat_player.sync_position_to_rect()
        update_combat_camera(smooth=False)

        current_wave = 1
        max_waves = 1 + (semester_counter // 2)
        wave_timer = 300

        enemies = [
            spawn_enemy(random.choices(COMMON_ENEMY_TYPES, weights=COMMON_ENEMY_WEIGHTS)[0])
            for _ in range(random.randint(3, 6))
        ]
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
        level_failed_timer = DEFEAT_SEQUENCE_FRAMES
        audio.play_sfx("level_failed")
        gamepad.rumble(0.8, 1.0, 500)

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
                    camera_y = (_mv.top + MAP_HUD_H + _mv.bottom)//2 - map_gen.rooms[selected_node].rect.centery
                    camera_x, camera_y = clamp_map_camera(camera_x, camera_y)

        frame_events = pygame.event.get()
        for raw_event in frame_events:
            gamepad.handle_event(raw_event)
        frame_events.extend(gamepad.poll_events(game_state))
        gamepad_message = gamepad.consume_status_message()
        if gamepad_message:
            gamepad_status_text = gamepad_message
            gamepad_status_timer = 240

        for event in frame_events:
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

            if game_state == "DISCLAIMER_SCREEN":
                # Saltar el aviso de autoguardado con Espacio/Enter (teclado) o
                # el boton A del mando (confirm -> K_RETURN en este contexto).
                # Sin indicador visible: avanza directo a la portada.
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    trigger_transition("TITLE_SCREEN", "FADE", 0.03)

            elif game_state == "TITLE_SCREEN":
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
                        global_data["gamepad_rumble"] = action.get("gp_rumble", global_data.get("gamepad_rumble", True))
                        global_data["gamepad_deadzone"] = action.get("gp_deadzone", global_data.get("gamepad_deadzone", "media"))
                        save_mgr.save_global_save(global_data)
                        audio.set_volumes(gen_vol, global_data["music_volume"])
                        gamepad.set_preferences(
                            rumble_enabled=global_data["gamepad_rumble"],
                            deadzone_name=global_data["gamepad_deadzone"],
                        )

                        # La ventana se recrea de forma robusta; la logica interna se
                        # mantiene en 1280x720 y solo cambia el escalado final (letterbox).
                        real_screen = apply_display_mode(res, fullscreen)
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
                        states_before = dict(engine.state)
                        engine.update_unlocks()
                        capture_unlocks(states_before)
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
                                camera_y = (_mv.top + MAP_HUD_H + _mv.bottom)//2 - target_room.rect.centery
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
                win_buttons = [pygame.Rect(300, 570, 310, 48), pygame.Rect(670, 570, 310, 48)]
                if event.type == pygame.MOUSEMOTION:
                    for i, rect in enumerate(win_buttons):
                        if rect.collidepoint(mouse_x, mouse_y):
                            win_selected = i
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, rect in enumerate(win_buttons):
                        if rect.collidepoint(mouse_x, mouse_y):
                            win_selected = i
                            if i == 0:
                                trigger_transition("MAP", "CIRCLE", 0.04)
                            else:
                                main_menu.notification = "Titulación completada. Partida guardada."
                                main_menu.notification_timer = 300
                                trigger_transition("MAIN_MENU", "FADE", 0.05)
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_UP):
                        win_selected = (win_selected - 1) % 2
                    elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                        win_selected = (win_selected + 1) % 2
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if win_selected == 0:
                            trigger_transition("MAP", "CIRCLE", 0.04)
                        else:
                            main_menu.notification = "Titulación completada. Partida guardada."
                            main_menu.notification_timer = 300
                            trigger_transition("MAIN_MENU", "FADE", 0.05)
            elif game_state == "GAME_OVER":
                if event.type == pygame.KEYDOWN and (event.key == pygame.K_r or event.key == pygame.K_SPACE):
                    gamepad.quit()
                    main()
                    return

        # Simulacion a PASO FIJO (60 Hz): se ejecuta 0, 1 o varias veces por frame de
        # render segun sim_steps, manteniendo la velocidad del juego constante a cualquier FPS.
        for _ in range(sim_steps):
            if screen_shake_timer > 0:
                screen_shake_timer -= 1
                if screen_shake_timer <= 0:
                    screen_shake_magnitude = 0.0
                    screen_shake_duration = 0
            # Actualizaciones Continuas (teclas presionadas)
            if game_state == "DISCLAIMER_SCREEN":
                if disclaimer_screen.time > 200 and not trans_state["active"]:
                    trigger_transition("TITLE_SCREEN", "FADE", 0.03)
            elif game_state == "TUTORIAL":
                tutorial_action = tutorial_state.update(keys, WIDTH, HEIGHT, mouse_x, mouse_y, gamepad)
                if tutorial_action == "FINISH_TUTORIAL":
                    finish_tutorial()
            elif game_state == "MAP":
                # El stick izquierdo/D-pad conserva la seleccion entre nodos. El
                # derecho replica el arrastre con clic derecho para explorar el mapa.
                pan_x, pan_y = gamepad.get_aim_vector()
                if pan_x != 0.0 or pan_y != 0.0:
                    camera_x -= pan_x * MAP_GAMEPAD_PAN_SPEED
                    camera_y -= pan_y * MAP_GAMEPAD_PAN_SPEED
                    camera_x, camera_y = clamp_map_camera(camera_x, camera_y)
            elif game_state == "WIN":
                win_time += 1
            elif game_state == "COMBAT":
                world_w, world_h = combat_world_size()
                if combat_player and combat_player.hp <= 0 and not level_failed_done:
                    begin_level_failure()

                if level_failed_timer > 0:
                    level_failed_timer -= 1
                    if level_failed_timer == 0:
                        level_failed_done = True
                        trigger_transition("MAP", "CIRCLE", 0.04)
                elif hit_stop_frames > 0:
                    # Pausa solo la simulacion de combate: render, eventos y
                    # presentacion siguen vivos; nunca se bloquea con sleep().
                    hit_stop_frames -= 1
                elif not editor_mode:
                    # Disparar con flechas (soporta diagonales)
                    dx, dy = 0, 0
                    if keys[pygame.K_UP]: dy -= 1
                    if keys[pygame.K_DOWN]: dy += 1
                    if keys[pygame.K_LEFT]: dx -= 1
                    if keys[pygame.K_RIGHT]: dx += 1

                    if dx != 0 or dy != 0:
                        combat_player.shoot_angle(math.atan2(dy, dx))

                    aim_x, aim_y = gamepad.get_aim_vector()
                    if math.hypot(aim_x, aim_y) > 0.0:
                        combat_player.shoot_angle(math.atan2(aim_y, aim_x))
                    elif gamepad.wants_trigger_fire():
                        last_aim_x, last_aim_y = gamepad.get_last_aim_vector()
                        combat_player.shoot_angle(math.atan2(last_aim_y, last_aim_x))

                    # Mouse drag shooting
                    if pygame.mouse.get_pressed()[0]:
                        combat_player.shoot_angle(math.atan2((mouse_y - combat_cam_y) - combat_player.y, (mouse_x - combat_cam_x) - combat_player.x))

                    combat_player.move(keys, world_w, world_h, collision_manager, gamepad.get_move_vector())
                    projectile_collisions = (
                        collision_manager
                        if current_level.projectiles_collide_with_solids
                        else None
                    )
                    for impact in combat_player.update_bullets(world_w, world_h, projectile_collisions):
                        spawn_bullet_impact(impact)
                    apply_player_hazard_damage()

                    update_combat_camera(smooth=True)

                    for enemy in enemies:
                        enemy.update(combat_player.x, combat_player.y, world_w, world_h, collision_manager, pathfinder=pathfinder, nearby_enemies=enemies)

                        if isinstance(enemy, MiniBoss):
                            bestiary_menu.unlock("MINI BOSS (PARCIAL)")
                        elif isinstance(enemy, Boss):
                            bestiary_menu.unlock("MEGA BOSS (TITULACIÓN)")

                        # El jugador recibe daño por contacto (si no está en i-frames)
                        if enemy.collides_with_player(combat_player) and enemy.attack_cooldown == 0:
                            contact_damage = 20 if isinstance(enemy, (MiniBoss, Boss)) else 10
                            if combat_player.take_damage(contact_damage):
                                enemy.attack_cooldown = 45 if isinstance(enemy, (MiniBoss, Boss)) else 30
                                enemy.notify_attack()
                                trigger_combat_feedback(
                                    4,
                                    5.0 if isinstance(enemy, (MiniBoss, Boss)) else 3.0,
                                    12,
                                )
                                combat_stats["damage"] += contact_damage
                                audio.play_sfx("hurt")
                                if isinstance(enemy, (MiniBoss, Boss)):
                                    gamepad.rumble(0.7, 1.0, 220)  # golpe de jefe: vibración fuerte
                                else:
                                    gamepad.rumble()

                        # El jugador recibe daño por balas enemigas
                        for b in enemy.bullets[:]:
                            dist = math.hypot(combat_player.x - b.x, combat_player.y - b.y)
                            if dist < (combat_player.radius + b.radius):
                                if combat_player.take_damage(15):
                                    combat_stats["damage"] += 15
                                    audio.play_sfx("hurt")
                                    gamepad.rumble()
                                    trigger_combat_feedback(3, 3.0, 10)
                                if b in enemy.bullets:
                                    enemy.bullets.remove(b)

                        if hasattr(enemy, "collect_area_damage_events"):
                            for hit in enemy.collect_area_damage_events(combat_player):
                                if not combat_player.take_damage(hit["damage"]):
                                    continue
                                combat_stats["damage"] += hit["damage"]
                                trigger_combat_feedback(4, 4.0, 12)
                                audio.play_sfx("hurt")
                                gamepad.rumble()
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
                                defeated = e.take_damage(damage, b.x, b.y)
                                audio.play_sfx("hit")
                                # Sin hit-stop ni shake al impactar: los disparos son
                                # muy frecuentes y el hit-stop pausa toda la simulacion,
                                # lo que hacia sentir a los enemigos lentisimos. El golpe
                                # se comunica con el flash rojo, el knockback y el sonido.

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
                                if defeated:
                                    # Hit-stop solo en la muerte de jefes (evento raro
                                    # y dramatico); los enemigos normales mueren muy
                                    # seguido y pausar la simulacion en cada uno frenaba
                                    # todo el combate.
                                    if isinstance(e, Boss):
                                        trigger_combat_feedback(18, 7.0, 50)
                                    elif isinstance(e, MiniBoss):
                                        trigger_combat_feedback(6, 3.0, 14)
                                    enemies.remove(e)
                                    combat_stats["kills"] += 1
                                    spawn_death_effect(e)
                                    audio.play_sfx(*enemy_die_sfx_names(e))

                    # Esquirlas de muerte: vuelan, frenan y desaparecen
                    for fx in death_effects[:]:
                        fx["x"] += fx["vx"]
                        fx["y"] += fx["vy"]
                        fx["vx"] *= 0.90
                        fx["vy"] *= 0.90
                        fx["life"] -= 1
                        if fx["life"] <= 0:
                            death_effects.remove(fx)

                    # Chispas de impacto: avanzan, frenan y se apagan rápidamente.
                    for spark in bullet_impacts[:]:
                        spark["x"] += spark["vx"]
                        spark["y"] += spark["vy"]
                        spark["vx"] *= 0.85
                        spark["vy"] *= 0.85
                        spark["life"] -= 1
                        if spark["life"] <= 0:
                            bullet_impacts.remove(spark)

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

                            for _ in range(random.randint(3, 5)):
                                ex = door_x + random.randint(-20, 20)
                                ey = door_y + random.randint(-20, 20)
                                enemy_cls = random.choices(COMMON_ENEMY_TYPES, weights=COMMON_ENEMY_WEIGHTS)[0]
                                enemies.append(spawn_enemy(enemy_cls, [(ex, ey)]))

                            if current_wave == max_waves and is_miniboss_room(current_room):
                                enemies.append(spawn_enemy(MiniBoss, [(door_x, door_y)]))

                    # Revisar si la habitación está limpia (solo si ya estamos en la última ronda)
                    if current_wave == max_waves and not enemies:
                        if level_passed_timer == 0 and not level_passed_done:
                            level_passed_timer = 300 if current_room == FINAL_BOSS_ROOM_ID else 210
                            combat_stats["end_ms"] = pygame.time.get_ticks()  # congelar el cronómetro
                            audio.play_sfx("level_clear")
                            gamepad.rumble(0.2, 0.4, 150)  # confirmación suave

                        if level_passed_timer > 0:
                            level_passed_timer -= 1
                            if level_passed_timer == 0:
                                level_passed_done = True
                                states_before = dict(engine.state)
                                engine.clean_room(current_room)
                                engine.update_unlocks()
                                capture_unlocks(states_before)

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
            for fx in map_unlock_effects[:]:
                fx["timer"] -= 1
                if fx["timer"] <= 0:
                    map_unlock_effects.remove(fx)
            if save_indicator_timer > 0:
                save_indicator_timer -= 1
            if gamepad_status_timer > 0:
                gamepad_status_timer -= 1

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

            # Anillos de "materia desbloqueada": celebran los nuevos desbloqueos
            for fx in map_unlock_effects:
                room = map_gen.rooms.get(fx["node"])
                if not room:
                    continue
                cx = room.rect.centerx + camera_x
                cy = room.rect.centery + camera_y
                t = 1.0 - fx["timer"] / fx["max"]
                alpha = int(220 * (fx["timer"] / fx["max"]))
                radius = int(max(room.rect.w, room.rect.h) * 0.55 + t * 46)
                ring = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
                pygame.draw.circle(ring, (140, 235, 160, alpha), (radius + 4, radius + 4), radius, 4)
                screen.blit(ring, (cx - radius - 4, cy - radius - 4))
                if fx["timer"] > fx["max"] - 130:
                    lbl = font_sm.render("¡DESBLOQUEADA!", False, (150, 255, 170))
                    lbl.set_alpha(alpha)
                    screen.blit(lbl, lbl.get_rect(center=(cx, room.rect.top + camera_y - 18)))

            # Marcador del objetivo recomendado (materia disponible con la cadena
            # más larga: seguirla mantiene al jugador sobre el camino crítico)
            rec = recommended_node()
            if rec and rec in map_gen.rooms:
                r_rect = map_gen.rooms[rec].rect
                rx = r_rect.centerx + camera_x
                bob = int(4 * math.sin(pygame.time.get_ticks() / 180.0))
                tip_y = r_rect.top + camera_y - 12 + bob
                rec_color = (120, 230, 160)
                pygame.draw.polygon(screen, (12, 10, 18),
                                    [(rx - 12, tip_y - 18), (rx + 12, tip_y - 18), (rx, tip_y + 2)])
                pygame.draw.polygon(screen, rec_color,
                                    [(rx - 9, tip_y - 16), (rx + 9, tip_y - 16), (rx, tip_y - 1)])
                rec_lbl = font_sm.render("RECOMENDADA", False, rec_color)
                screen.blit(rec_lbl, rec_lbl.get_rect(center=(rx, tip_y - 30)))

            if selected_node and selected_node in map_gen.rooms:
                sel_rect = map_gen.rooms[selected_node].rect.copy()
                sel_rect.x += camera_x
                sel_rect.y += camera_y
                draw_selection_highlight(screen, sel_rect)
                draw_subject_tooltip(screen, engine, selected_node, sel_rect,
                                     view=get_visible_virtual_rect(real_screen.get_size(), aspect_mode))

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
            shake_x = shake_y = 0
            if screen_shake_timer > 0 and screen_shake_duration > 0:
                decay = screen_shake_timer / max(1, screen_shake_duration)
                magnitude = screen_shake_magnitude * decay
                shake_x = int(round(math.sin(screen_shake_timer * 2.37) * magnitude))
                shake_y = int(round(math.cos(screen_shake_timer * 3.11) * magnitude))
            render_combat_cam_x = combat_cam_x + shake_x
            render_combat_cam_y = combat_cam_y + shake_y

            draw_floor(screen, combat_bg_img, render_combat_cam_x, render_combat_cam_y)
            for e in enemies:
                if hasattr(e, "draw_area_ground_effects"):
                    e.draw_area_ground_effects(screen, render_combat_cam_x, render_combat_cam_y)
            combat_player.draw(screen, render_combat_cam_x, render_combat_cam_y)
            for e in enemies:
                e.draw(screen, render_combat_cam_x, render_combat_cam_y)

            active_boss = next((e for e in enemies if isinstance(e, Boss)), None)
            if active_boss is None:
                active_boss = next((e for e in enemies if isinstance(e, MiniBoss)), None)
            draw_boss_health_bar(
                screen,
                active_boss,
                get_visible_virtual_rect(real_screen.get_size(), aspect_mode),
                font_sm,
            )

            # Esquirlas de muerte: bloques del sprite que se encogen al volar
            for fx in death_effects:
                f = fx["life"] / fx["max"]
                pw = max(1, int(fx["piece"].get_width() * f))
                ph = max(1, int(fx["piece"].get_height() * f))
                piece = pygame.transform.scale(fx["piece"], (pw, ph))
                screen.blit(piece, (int(fx["x"] + render_combat_cam_x - pw / 2), int(fx["y"] + render_combat_cam_y - ph / 2)))

            # Chispas pixel-art de las balas al golpear paredes y máquinas.
            for spark in bullet_impacts:
                fade = spark["life"] / spark["max"]
                size = max(1, int(spark["size"] * fade))
                color = tuple(int(channel * fade) for channel in spark["color"])
                spark_rect = pygame.Rect(0, 0, size, size)
                spark_rect.center = (
                    int(spark["x"] + render_combat_cam_x),
                    int(spark["y"] + render_combat_cam_y),
                )
                pygame.draw.rect(screen, color, spark_rect)

            # Dibujar textos flotantes de daño
            for ft in floating_texts:
                alpha = min(255, int((ft["life"] / 40.0) * 255))
                dmg_surf = font_md.render(ft["text"], True, ft["color"])
                dmg_surf.set_alpha(alpha)
                rect = dmg_surf.get_rect(center=(int(ft["x"] + render_combat_cam_x), int(ft["y"] + render_combat_cam_y)))
                screen.blit(dmg_surf, rect)

            # Resumen post-combate mientras corre la pausa de sala superada
            if level_passed_timer > 0 and not editor_mode:
                panel = pygame.Rect(0, 0, 680, 240)
                panel.center = (WIDTH // 2, HEIGHT // 2 - 20)
                bg = pygame.Surface(panel.size, pygame.SRCALPHA)
                bg.fill((12, 10, 20, 225))
                screen.blit(bg, panel.topleft)
                pygame.draw.rect(screen, (36, 30, 54), panel, 4)
                pygame.draw.rect(screen, (86, 74, 122), panel, 2)

                final_clear = current_room == FINAL_BOSS_ROOM_ID
                clear_title = "SISTEMA CENTRAL DESTRUIDO" if final_clear else "¡MATERIA APROBADA!"
                title = render_text_fit(font_heading if final_clear else font_lg, clear_title,
                                        (255, 210, 100) if final_clear else (150, 255, 150),
                                        panel.width - 40, antialias=False)
                screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 46)))

                subject_name = engine.subjects.get(current_room, {}).get("name", "")
                if subject_name:
                    name_surf = font_md.render(subject_name, True, (255, 216, 110))
                    screen.blit(name_surf, name_surf.get_rect(center=(panel.centerx, panel.top + 92)))

                end_ms = combat_stats["end_ms"] or pygame.time.get_ticks()
                elapsed_s = max(0, (end_ms - combat_stats["start_ms"]) // 1000)
                stats_lines = [
                    f"Tiempo: {elapsed_s // 60}:{elapsed_s % 60:02d}",
                    f"Daño recibido: {combat_stats['damage']}",
                    f"Enemigos eliminados: {combat_stats['kills']}",
                ]
                for i, line in enumerate(stats_lines):
                    surf = font_md.render(line, True, (220, 220, 230))
                    screen.blit(surf, surf.get_rect(center=(panel.centerx, panel.top + 136 + i * 34)))

            if debug_enemy_paths and pathfinder:
                draw_enemy_ai_debug(
                    screen,
                    enemies,
                    pathfinder,
                    camera=(render_combat_cam_x, render_combat_cam_y),
                    font=font_sm,
                    player_pos=(combat_player.x, combat_player.y),
                )

            if editor_mode:
                editor.draw(screen, render_combat_cam_x, render_combat_cam_y,
                            safe_rect=get_visible_virtual_rect(real_screen.get_size(), aspect_mode))
            elif debug_collisions and collision_manager:
                collision_manager.draw_debug(
                    screen,
                    camera=(render_combat_cam_x, render_combat_cam_y),
                    font=font_sm,
                    show_names=debug_collision_labels,
                )
                current_level.draw_hazard_debug(
                    screen,
                    camera=(render_combat_cam_x, render_combat_cam_y),
                    font=font_sm,
                    show_names=debug_collision_labels,
                )

                p_rect = combat_player.rect.move(render_combat_cam_x, render_combat_cam_y)
                p_hit = combat_player.last_collision.get("x") or combat_player.last_collision.get("y")
                pygame.draw.rect(screen, (255, 80, 80) if p_hit else (0, 255, 255), p_rect, 2)
                for e in enemies:
                    e_rect = e.rect.move(render_combat_cam_x, render_combat_cam_y)
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
            # (el aviso "¡NIVEL SUPERADO!" fue reemplazado por el panel de resumen)

            if level_failed_timer > 0:
                draw_defeat_sequence(screen, combat_player, combat_cam_x, combat_cam_y, level_failed_timer, DEFEAT_SEQUENCE_FRAMES)

        elif game_state == "WIN":
            if win_bg_img:
                screen.blit(win_bg_img, (0, 0))
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((3, 5, 12, 178))
            screen.blit(veil, (0, 0))

            # Pulso final alrededor del núcleo de s10.
            pulse = 72 + int(abs(math.sin(win_time / 24.0)) * 18)
            pygame.draw.circle(screen, (255, 197, 72), (WIDTH // 2, HEIGHT // 2), pulse, 3)
            pygame.draw.circle(screen, (50, 205, 255), (WIDTH // 2, HEIGHT // 2), pulse + 12, 2)

            panel = pygame.Rect(170, 76, 940, 566)
            panel_bg = pygame.Surface(panel.size, pygame.SRCALPHA)
            panel_bg.fill((18, 20, 25, 228))
            screen.blit(panel_bg, panel.topleft)
            pygame.draw.rect(screen, (255, 195, 80), panel, 3)
            pygame.draw.rect(screen, (92, 101, 112), panel.inflate(-10, -10), 2)

            title = render_text_fit(font_heading, "¡PROYECTO DE TITULACIÓN APROBADO!",
                                    (255, 218, 125), panel.width - 70, antialias=False)
            screen.blit(title, title.get_rect(center=(panel.centerx, panel.top + 66)))
            subtitle = font_md.render("Has derrotado al sistema central y completado la malla curricular.",
                                      False, (218, 230, 238))
            screen.blit(subtitle, subtitle.get_rect(center=(panel.centerx, panel.top + 112)))

            end_ms = combat_stats["end_ms"] or pygame.time.get_ticks()
            elapsed_s = max(0, (end_ms - combat_stats["start_ms"]) // 1000)
            completed_subjects = sum(1 for state in engine.state.values() if state == NodeState.CLEANED)
            stats = [
                ("TIEMPO FINAL", f"{elapsed_s // 60}:{elapsed_s % 60:02d}"),
                ("DAÑO RECIBIDO", str(combat_stats["damage"])),
                ("MATERIAS APROBADAS", f"{completed_subjects}/{len(engine.nodes)}"),
                ("SEMESTRES", f"{semester_counter}  ·  Récord ideal: {par_score}"),
            ]
            row_y = panel.top + 172
            for i, (label, value) in enumerate(stats):
                rect = pygame.Rect(panel.left + 90, row_y + i * 66, panel.width - 180, 50)
                pygame.draw.rect(screen, (27, 31, 37), rect)
                pygame.draw.line(screen, (78, 88, 98), rect.bottomleft, rect.bottomright, 1)
                lab = font_sm.render(label, False, (157, 174, 187))
                val = font_md.render(value, False, (255, 235, 184))
                screen.blit(lab, (rect.left + 18, rect.centery - lab.get_height() // 2))
                screen.blit(val, val.get_rect(midright=(rect.right - 18, rect.centery)))

            win_buttons = [pygame.Rect(300, 570, 310, 48), pygame.Rect(670, 570, 310, 48)]
            button_labels = ("Continuar en el mapa", "Volver al menú")
            for i, rect in enumerate(win_buttons):
                selected = i == win_selected
                pygame.draw.rect(screen, (105, 73, 32) if selected else (38, 42, 47), rect)
                pygame.draw.rect(screen, (255, 205, 105) if selected else (105, 115, 125), rect, 2)
                label = font_md.render(button_labels[i], False, (255, 244, 218))
                screen.blit(label, label.get_rect(center=rect.center))

            help_line = gp_prompt_line(font_sm, "FLECHAS Elegir   -   ENTER Confirmar",
                                       (210, 216, 222), antialias=False)
            screen.blit(help_line, help_line.get_rect(center=(WIDTH // 2, 674)))
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
                gp_localize("Presiona 'R' para reintentar el nivel."),
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
            save_safe = get_visible_virtual_rect(real_screen.get_size(), aspect_mode)
            s = pygame.Surface((180, 50), pygame.SRCALPHA)
            s.fill((0, 0, 0, 100)) # Alpha mucho más transparente (antes 200)
            screen.blit(s, (save_safe.right - 200, save_safe.bottom - 70))

            # Círculo e icono (tamaño intermedio)
            icon_x, icon_y = save_safe.right - 170, save_safe.bottom - 45
            if SAVE_ICON_IMG:
                scale_factor = 1.0 + 0.15 * abs(math.sin(save_indicator_timer * 0.1))
                new_w = int(SAVE_ICON_IMG.get_width() * scale_factor)
                new_h = int(SAVE_ICON_IMG.get_height() * scale_factor)
                scaled_img = pygame.transform.scale(SAVE_ICON_IMG, (new_w, new_h))
                img_rect = scaled_img.get_rect(center=(icon_x, icon_y))
                screen.blit(scaled_img, img_rect)
            else:
                pygame.draw.circle(screen, (100, 255, 100), (icon_x, icon_y), 17, 3)
                arc_angle = (save_indicator_timer * 12) % 360
                pygame.draw.arc(screen, (255, 255, 255), (icon_x - 17, icon_y - 17, 34, 34), math.radians(arc_angle), math.radians(arc_angle+100), 4)

            # Texto
            s_text = font_sm.render("Guardando...", True, (255, 255, 255))
            screen.blit(s_text, (icon_x + 25, icon_y - s_text.get_height()//2))

        if gamepad_status_timer > 0 and gamepad_status_text:
            status_safe = get_visible_virtual_rect(real_screen.get_size(), aspect_mode)
            status_alpha = min(255, max(0, int(gamepad_status_timer * 1.2)))
            status_surf = font_sm.render(gamepad_status_text, True, (220, 245, 255))
            status_surf.set_alpha(status_alpha)
            status_bg = pygame.Surface((status_surf.get_width() + 20, status_surf.get_height() + 12), pygame.SRCALPHA)
            status_bg.fill((0, 0, 0, min(180, max(0, int(gamepad_status_timer)))))
            status_pos = (status_safe.left + 16, status_safe.bottom - status_bg.get_height() - 16)
            screen.blit(status_bg, status_pos)
            screen.blit(status_surf, (status_pos[0] + 10, status_pos[1] + 6))

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

    gamepad.quit()

if __name__ == "__main__":
    main()
    pygame.quit()
    sys.exit()
