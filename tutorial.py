import pygame
import math
import gamepad
from menu import draw_energy_crystal, render_3d_gradient_text
from dag_engine import PATH_PALETTE
from player import Player
from enemy import BugEnemy
from level import load_combat_level


def draw_dark_cross_bg(surface, width, height, time_offset=0):
    """Fondo del tutorial: mismo patrón de cruces de los menús, en neutro oscuro."""
    surface.fill((13, 13, 17))
    cross_color = (24, 24, 31)
    spacing = 64
    offset_x = (int(time_offset) // 2) % spacing
    offset_y = (int(time_offset) // 2) % spacing
    for y in range(-spacing, height + spacing, spacing):
        for x in range(-spacing, width + spacing, spacing):
            px, py = x + offset_x, y + offset_y
            pygame.draw.rect(surface, cross_color, (px - 2, py - 8, 4, 16))
            pygame.draw.rect(surface, cross_color, (px - 8, py - 2, 16, 4))

class TutorialPhase:
    TEXT_MAP = 0
    COMBAT_PRACTICE = 1
    TEXT_ENEMIES = 2
    DONE = 3
    OUTRO = 4  # main.py asigna este valor directamente al volver del bestiario


# Efecto máquina de escribir: caracteres revelados por tick de simulación (60 Hz).
TYPE_SPEED = 2.4

# Estilo del panel de texto (pixel-art duro, en línea con los tooltips del mapa)
PANEL_BG = (16, 12, 26)
PANEL_BORDER = (86, 74, 122)
PANEL_BORDER_DARK = (36, 30, 54)
ACCENT = (255, 216, 110)
TEXT_MAIN = (235, 235, 240)
TEXT_DIM = (185, 185, 195)

DEFAULT_PROMPT = "(Presiona ESPACIO o ENTER para continuar)"


class TutorialState:
    def __init__(self, width, height, font_lg, font_md, font_sm, heart_frames=None):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.font_sm = font_sm
        self.heart_frames = heart_frames

        self.phase = TutorialPhase.TEXT_MAP
        self.map_page_index = 0
        self.timer = 0
        self.chars_shown = 0.0     # progreso del efecto máquina de escribir
        self.revive_timer = 0      # aviso de "revivido" en la práctica
        self.victory_timer = 0     # pausa de festejo al eliminar al bug

        # Entidades de la práctica de combate (usa la arena del miniboss s1)
        self.player = None
        self.dummy_target = None
        self.cam_x, self.cam_y = 0.0, 0.0
        self._load_practice_level()

        self.panel_rect = pygame.Rect(width // 2 - 490, 150, 980, 396)

        # Páginas del tutorial del mapa: encabezado + cuerpo + ejemplo visual.
        self.map_pages = [
            {
                "heading": "Bienvenido al Mega-Calabozo DAG",
                "lines": [
                    "Este mapa es una malla curricular de la carrera de",
                    "Sistemas de Información: cada habitación es una 'materia'.",
                    "Haz clic en un nodo y presiona ENTER,",
                    "o haz doble clic para entrar a la materia.",
                ],
                "example": "nodes",
            },
            {
                "heading": "Los colores importan",
                "lines": [
                    "Las aristas de colores marcan los 8 posibles",
                    "caminos críticos de la carrera.",
                    "El fondo de las batallas también cambia",
                    "según el semestre en el que te encuentres.",
                ],
                "example": "colors",
            },
            {
                "heading": "¿Cómo calculamos los caminos críticos?",
                "lines": [
                    "Con Programación Dinámica sobre el grafo (DAG):",
                    "ordenamos las materias con Orden Topológico (Kahn) y",
                    "calculamos la cadena más larga de prerrequisitos de cada",
                    "materia. El valor máximo define el 'Tiempo Récord'.",
                ],
                "example": "dag",
            },
            {
                "heading": "Mecánicas de supervivencia: Energía",
                "lines": [
                    "Cada combate consume 1 punto de Energía.",
                    "Si te quedas sin energía, pulsa ESPACIO en el mapa",
                    "para 'Descansar': recuperas la energía, pero avanzas",
                    "al siguiente semestre.",
                ],
                "example": "energy",
            },
            {
                "heading": "Tu objetivo final es la Titulación",
                "lines": [
                    "Limpia todas las materias respetando prerrequisitos.",
                    "Al final te enfrentarás al Mega Boss.",
                    "Cuida tu Vida (HP): si llega a 0, fallarás el intento.",
                ],
                "example": "life",
                "prompt": "(Presiona ESPACIO o ENTER para practicar combate)",
            },
        ]

        # Página de enemigos (tras la práctica): los nombres van coloreados.
        self.enemy_roster = [
            ("BUG", (120, 220, 120), "pequeño, rápido y muy molesto"),
            ("CÓDIGO SPAGHETTI", (235, 180, 90), "se mueve de forma errática"),
            ("MEMORY LEAK", (130, 190, 240), "lento pero implacable"),
            ("DEADLINE", (235, 95, 95), "no dejes que te alcance"),
        ]
        self.enemies_page = {
            "heading": "Enemigos académicos",
            "lines": [
                "Ya manejas los controles básicos.",
                "El calabozo está lleno de enemigos:",
            ],
            "prompt": "(Presiona ESPACIO o ENTER para ver el Bestiario)",
        }

    def _load_practice_level(self):
        self.practice_level = load_combat_level("s1_boss", fallback_size=(self.width, self.height))
        self.collision_manager = self.practice_level.create_collision_manager()
        try:
            self.practice_bg = self.practice_level.load_background()
        except Exception:
            self.practice_bg = None

    def reset(self):
        self.phase = TutorialPhase.TEXT_MAP
        self.map_page_index = 0
        self.timer = 0
        self.chars_shown = 0.0
        self.revive_timer = 0
        self.victory_timer = 0
        self.player = None
        self.dummy_target = None
        self.cam_x, self.cam_y = 0.0, 0.0
        self._load_practice_level()

    # ------------------------------------------------------------------
    # Efecto máquina de escribir
    # ------------------------------------------------------------------
    def _current_page(self):
        if self.phase == TutorialPhase.TEXT_MAP:
            return self.map_pages[self.map_page_index]
        if self.phase == TutorialPhase.TEXT_ENEMIES:
            return self.enemies_page
        return None

    def _page_lines(self, page):
        lines = list(page["lines"])
        if page is self.enemies_page:
            for name, _color, desc in self.enemy_roster:
                lines.append(f"- {name}: {desc}")
            lines.append("A continuación, te presento el Bestiario...")
        return lines

    def _page_total_chars(self, page):
        return sum(len(line) for line in self._page_lines(page))

    def _page_fully_typed(self):
        page = self._current_page()
        if page is None:
            return True
        return self.chars_shown >= self._page_total_chars(page)

    def _start_page(self):
        self.chars_shown = 0.0

    # ------------------------------------------------------------------
    # Eventos y simulación
    # ------------------------------------------------------------------
    def _start_combat_practice(self):
        self.phase = TutorialPhase.COMBAT_PRACTICE
        level = self.practice_level
        scale = level.character_scale
        self.player = Player(level.player_spawn[0], level.player_spawn[1], scale=scale)
        # Un bug REAL, solo un poco más lento y resistente para practicar:
        # persigue, hace daño por contacto y hay que eliminarlo para avanzar.
        spawn = level.enemy_spawns[0] if level.enemy_spawns else (level.width // 2, level.height // 3)
        self.dummy_target = BugEnemy(spawn[0], spawn[1], scale=scale)
        self.dummy_target.speed *= 0.75
        self.dummy_target.hp = 60
        self.dummy_target.max_hp = 60
        self.timer = 0
        self.victory_timer = 0
        self.revive_timer = 0
        self._update_camera(smooth=False)

    # Cámara de la práctica: sigue al jugador, sin salirse del nivel (misma
    # lógica que la cámara del combate real).
    def _clamp_cam_axis(self, target, world, view):
        if world <= view:
            return (view - world) // 2
        return min(0, max(view - world, target))

    def _update_camera(self, smooth=True):
        if not self.player:
            return
        tx = self._clamp_cam_axis(self.width // 2 - int(self.player.x), self.practice_level.width, self.width)
        ty = self._clamp_cam_axis(self.height // 2 - int(self.player.y), self.practice_level.height, self.height)
        if smooth:
            self.cam_x += (tx - self.cam_x) * 0.1
            self.cam_y += (ty - self.cam_y) * 0.1
        else:
            self.cam_x, self.cam_y = float(tx), float(ty)

    def handle_event(self, event, mouse_x, mouse_y):
        confirm = event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]

        if self.phase == TutorialPhase.TEXT_MAP:
            if confirm:
                if not self._page_fully_typed():
                    self.chars_shown = float(10 ** 6)  # completar la página al instante
                elif self.map_page_index < len(self.map_pages) - 1:
                    self.map_page_index += 1
                    self._start_page()
                else:
                    self._start_combat_practice()

        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            if confirm:
                if not self._page_fully_typed():
                    self.chars_shown = float(10 ** 6)
                else:
                    return "GO_TO_BESTIARY"

        elif self.phase == TutorialPhase.OUTRO:
            if confirm:
                self.phase = TutorialPhase.DONE
                return "FINISH_TUTORIAL"

        return None

    def update(self, keys, width, height, mouse_x=None, mouse_y=None, gamepad=None):
        self.timer += 1
        self.chars_shown += TYPE_SPEED
        if self.revive_timer > 0:
            self.revive_timer -= 1

        if self.phase == TutorialPhase.COMBAT_PRACTICE:
            # Festejo tras eliminar al bug: pequeña pausa y pasamos a enemigos.
            if self.victory_timer > 0:
                self.victory_timer -= 1
                if self.player:
                    self.player.update_bullets(self.practice_level.width, self.practice_level.height)
                if self.victory_timer == 0:
                    self.phase = TutorialPhase.TEXT_ENEMIES
                    self.player = None
                    self._start_page()
                return None

            world_w, world_h = self.practice_level.width, self.practice_level.height
            move_vector = gamepad.get_move_vector() if gamepad and gamepad.connected else None
            self.player.move(keys, world_w, world_h, self.collision_manager, move_vector)
            self.player.update_bullets(world_w, world_h)
            self._update_camera()

            # Disparo continuo con el ratón (coordenadas de pantalla -> mundo via cámara)
            if mouse_x is None or mouse_y is None:
                mouse_x, mouse_y = pygame.mouse.get_pos()
            if pygame.mouse.get_pressed()[0]:
                self.player.shoot_angle(math.atan2((mouse_y - self.cam_y) - self.player.y,
                                                   (mouse_x - self.cam_x) - self.player.x))

            dx, dy = 0, 0
            if keys[pygame.K_UP]: dy -= 1
            if keys[pygame.K_DOWN]: dy += 1
            if keys[pygame.K_LEFT]: dx -= 1
            if keys[pygame.K_RIGHT]: dx += 1
            if dx != 0 or dy != 0:
                self.player.shoot_angle(math.atan2(dy, dx))

            if gamepad and gamepad.connected:
                aim_x, aim_y = gamepad.get_aim_vector()
                if math.hypot(aim_x, aim_y) > 0.0:
                    self.player.shoot_angle(math.atan2(aim_y, aim_x))
                elif gamepad.wants_trigger_fire():
                    last_x, last_y = gamepad.get_last_aim_vector()
                    self.player.shoot_angle(math.atan2(last_y, last_x))

            if self.dummy_target:
                self.dummy_target.update(self.player.x, self.player.y, world_w, world_h, self.collision_manager, None, [self.dummy_target])

                for b in self.player.bullets[:]:
                    if self.dummy_target and self.dummy_target.collides_with_bullet(b):
                        self.player.bullets.remove(b)
                        self.dummy_target.hp -= 10
                        self.dummy_target.hit_flash = 8
                        if self.dummy_target.hp <= 0:
                            self.dummy_target = None
                            self.victory_timer = 90

                if self.dummy_target:
                    if self.dummy_target.collides_with_player(self.player) and self.dummy_target.attack_cooldown == 0:
                        self.player.hp -= 10
                        self.dummy_target.attack_cooldown = 30

                    for b in self.dummy_target.bullets[:]:
                        dist = math.hypot(self.player.x - b.x, self.player.y - b.y)
                        if dist < (self.player.radius + b.radius):
                            self.player.hp -= 15
                            if b in self.dummy_target.bullets:
                                self.dummy_target.bullets.remove(b)

            # En la práctica no se puede morir: revivimos avisando al jugador.
            if self.player and self.player.hp <= 0:
                self.player.hp = self.player.max_hp
                self.revive_timer = 120

        elif self.phase == TutorialPhase.OUTRO:
            if self.timer >= 150:
                self.phase = TutorialPhase.DONE
                return "FINISH_TUTORIAL"
        return None

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def _draw_panel(self, surface, rect):
        pygame.draw.rect(surface, PANEL_BG, rect)
        pygame.draw.rect(surface, PANEL_BORDER_DARK, rect, 4)
        pygame.draw.rect(surface, PANEL_BORDER, rect, 2)
        # esquinas de acento (brackets pixel)
        for cx, cy, dx, dy in ((rect.left, rect.top, 1, 1), (rect.right, rect.top, -1, 1),
                               (rect.left, rect.bottom, 1, -1), (rect.right, rect.bottom, -1, -1)):
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx + 14 * dx, cy), 2)
            pygame.draw.line(surface, ACCENT, (cx, cy), (cx, cy + 14 * dy), 2)

    def _draw_page_dots(self, surface, total, current, cy):
        size, gap = 10, 12
        sx = self.width // 2 - (total * size + (total - 1) * gap) // 2
        for i in range(total):
            r = pygame.Rect(sx + i * (size + gap), cy, size, size)
            if i == current:
                pygame.draw.rect(surface, ACCENT, r)
            else:
                pygame.draw.rect(surface, PANEL_BORDER, r, 2)

    def _draw_typed_lines(self, surface, page, y_start, line_h=38):
        """Dibuja el cuerpo con efecto máquina de escribir y cursor parpadeante."""
        budget = int(self.chars_shown)
        lines = self._page_lines(page)
        # colores por línea: las de la lista de enemigos usan su color propio
        for i, line in enumerate(lines):
            if budget <= 0:
                break
            shown = line[:budget]
            budget -= len(line)
            color = TEXT_MAIN
            if page is self.enemies_page and line.startswith("- "):
                for name, ecolor, _d in self.enemy_roster:
                    if line.startswith(f"- {name}"):
                        color = ecolor
                        break
            text = gamepad.render_prompt_line(self.font_md, shown, color)
            rect = text.get_rect(center=(self.width // 2, y_start + i * line_h))
            surface.blit(text, rect)
            # cursor de terminal al final de la línea que se está escribiendo
            if budget <= 0 and shown and (self.timer // 8) % 2 == 0:
                cur = pygame.Rect(rect.right + 4, rect.centery - 10, 10, 20)
                pygame.draw.rect(surface, ACCENT, cur)

    def _draw_prompt(self, surface, line, center_y):
        text = gamepad.render_prompt_line(self.font_md, line, TEXT_DIM)
        # parpadeo suave para invitar a continuar
        alpha = 150 + int(60 * math.sin(self.timer * 0.08))
        text.set_alpha(alpha)
        rect = text.get_rect(center=(self.width // 2, center_y))
        surface.blit(text, rect)

    # --- ejemplos visuales por página -------------------------------------
    def _draw_example_nodes(self, surface, cy):
        """Tres nodos como los del mapa: bloqueada, disponible y aprobada."""
        states = [
            ((70, 62, 84), (110, 100, 130), "Bloqueada", (150, 146, 160)),
            ((232, 214, 168), (255, 245, 212), "Disponible", ACCENT),
            ((156, 200, 156), (214, 242, 214), "Aprobada", (150, 220, 150)),
        ]
        gap = 220
        sx = self.width // 2 - gap
        node_w, node_h = 92, 46
        # aristas que conectan los nodos
        for i in range(2):
            x1 = sx + i * gap + node_w // 2
            x2 = sx + (i + 1) * gap - node_w // 2
            pygame.draw.line(surface, (12, 10, 18), (x1, cy), (x2, cy), 6)
            pygame.draw.line(surface, (126, 122, 142), (x1, cy), (x2, cy), 2)
        for i, (fill, bevel, label, label_color) in enumerate(states):
            r = pygame.Rect(0, 0, node_w, node_h)
            r.center = (sx + i * gap, cy)
            pygame.draw.rect(surface, (12, 10, 18), r.inflate(6, 6))
            pygame.draw.rect(surface, fill, r)
            pygame.draw.line(surface, bevel, (r.left + 2, r.top + 2), (r.right - 3, r.top + 2), 2)
            if i == 1:  # la disponible parpadea como en el mapa
                blink = (math.sin(self.timer / 12.0) + 1) / 2
                if blink > 0.4:
                    pygame.draw.rect(surface, ACCENT, r.inflate(8, 8), 2)
            lab = self.font_sm.render(label, False, label_color)
            surface.blit(lab, lab.get_rect(center=(r.centerx, r.bottom + 18)))

    def _draw_example_colors(self, surface, cy):
        """Las 8 franjas de color reales de los caminos críticos."""
        seg_w, seg_h, gap = 64, 10, 14
        total = len(PATH_PALETTE) * seg_w + (len(PATH_PALETTE) - 1) * gap
        sx = self.width // 2 - total // 2
        for i, color in enumerate(PATH_PALETTE):
            x = sx + i * (seg_w + gap)
            pygame.draw.rect(surface, (12, 10, 18), (x - 2, cy - 2, seg_w + 4, seg_h + 4))
            pygame.draw.rect(surface, color, (x, cy, seg_w, seg_h))
        lab = self.font_sm.render("8 caminos críticos = 8 colores de arista", False, TEXT_DIM)
        surface.blit(lab, lab.get_rect(center=(self.width // 2, cy + 34)))

    def _draw_example_dag(self, surface, cy):
        """Mini-cadena de prerrequisitos con su longitud (la esencia de la PD)."""
        chain = ["1", "2", "3", "4"]
        gap = 150
        sx = self.width // 2 - gap * (len(chain) - 1) // 2
        for i in range(len(chain) - 1):
            x1, x2 = sx + i * gap + 24, sx + (i + 1) * gap - 24
            pygame.draw.line(surface, (12, 10, 18), (x1, cy), (x2, cy), 6)
            pygame.draw.line(surface, ACCENT, (x1, cy), (x2, cy), 2)
            pygame.draw.polygon(surface, ACCENT, [(x2, cy), (x2 - 9, cy - 5), (x2 - 9, cy + 5)])
        # se van "encendiendo" en orden topológico
        lit = (self.timer // 25) % (len(chain) + 2)
        for i, num in enumerate(chain):
            r = pygame.Rect(0, 0, 40, 40)
            r.center = (sx + i * gap, cy)
            on = i < lit
            pygame.draw.rect(surface, (12, 10, 18), r.inflate(6, 6))
            pygame.draw.rect(surface, (232, 214, 168) if on else (70, 62, 84), r)
            n = self.font_md.render(num, False, (66, 44, 22) if on else (140, 136, 150))
            surface.blit(n, n.get_rect(center=r.center))
        lab = self.font_sm.render("cadena más larga de prerrequisitos = Tiempo Récord", False, TEXT_DIM)
        surface.blit(lab, lab.get_rect(center=(self.width // 2, cy + 44)))

    def _draw_example_energy(self, surface, cy):
        max_energy = 5
        shown = max_energy - ((self.timer // 30) % (max_energy + 1))
        gap = 56
        sx = self.width // 2 - (max_energy - 1) * gap // 2
        for i in range(max_energy):
            draw_energy_crystal(surface, sx + i * gap, cy, i < shown, px=5)
        lab = self.font_sm.render(f"Energia: {shown}/{max_energy} (se gasta al entrar a una materia)", False, (150, 220, 250))
        surface.blit(lab, lab.get_rect(center=(self.width // 2, cy - 38)))

    def _draw_example_life(self, surface, cy):
        if not self.heart_frames:
            return
        frame_idx = len(self.heart_frames) - 1 - ((self.timer // 30) % len(self.heart_frames))
        heart = pygame.transform.scale(self.heart_frames[frame_idx], (64, 64))
        surface.blit(heart, heart.get_rect(center=(self.width // 2, cy)))
        lab = self.font_sm.render("Vida (se reduce al recibir daño)", False, (255, 120, 120))
        surface.blit(lab, lab.get_rect(center=(self.width // 2, cy - 48)))

    def _draw_example(self, surface, kind, cy):
        if kind == "nodes":
            self._draw_example_nodes(surface, cy)
        elif kind == "colors":
            self._draw_example_colors(surface, cy)
        elif kind == "dag":
            self._draw_example_dag(surface, cy)
        elif kind == "energy":
            self._draw_example_energy(surface, cy)
        elif kind == "life":
            self._draw_example_life(surface, cy)

    # --- pantallas ---------------------------------------------------------
    def _draw_text_screen(self, surface, title, page, dots=None):
        draw_dark_cross_bg(surface, self.width, self.height, self.timer)
        title_surf = render_3d_gradient_text(title, self.font_lg)
        surface.blit(title_surf, title_surf.get_rect(center=(self.width // 2, 84)))

        panel = self.panel_rect
        self._draw_panel(surface, panel)

        heading = self.font_md.render(page["heading"], False, ACCENT)
        surface.blit(heading, heading.get_rect(center=(self.width // 2, panel.top + 44)))
        pygame.draw.line(surface, PANEL_BORDER, (panel.left + 40, panel.top + 68),
                         (panel.right - 40, panel.top + 68), 1)

        self._draw_typed_lines(surface, page, panel.top + 104)

        if self._page_fully_typed():
            example = page.get("example")
            if example:
                self._draw_example(surface, example, panel.bottom - 74)
            self._draw_prompt(surface, page.get("prompt", DEFAULT_PROMPT), self.height - 60)

        if dots is not None:
            self._draw_page_dots(surface, dots[0], dots[1], panel.bottom + 20)

    def _draw_practice_hud(self, surface):
        # franja superior con las instrucciones según el dispositivo
        strip = pygame.Surface((self.width, 118), pygame.SRCALPHA)
        strip.fill((10, 8, 18, 200))
        surface.blit(strip, (0, 0))
        pygame.draw.line(surface, PANEL_BORDER, (0, 118), (self.width, 118), 2)

        if gamepad.prompts_active():
            msg_move = "Muévete con WASD."          # WASD -> icono de stick izq
            msg_aim = "Apunta y dispara con Flechas/Mouse (o RT/R2)."
        else:
            msg_move = "Muévete con W, A, S, D."
            msg_aim = "Apunta y dispara con el Ratón o las Flechas."
        hint = gamepad.render_prompt_line(self.font_md, msg_move, (210, 210, 220))
        hint2 = gamepad.render_prompt_line(self.font_md, msg_aim, (210, 210, 220))
        hint3 = self.font_md.render("¡Cuidado, el bug te persigue! Elimínalo para continuar.", True, (255, 120, 120))
        surface.blit(hint, hint.get_rect(center=(self.width // 2, 26)))
        surface.blit(hint2, hint2.get_rect(center=(self.width // 2, 60)))
        surface.blit(hint3, hint3.get_rect(center=(self.width // 2, 96)))

        # vida del jugador (abajo a la izquierda)
        if self.player:
            bar = pygame.Rect(64, self.height - 46, 200, 18)
            frac = max(0.0, self.player.hp / self.player.max_hp)
            pygame.draw.rect(surface, (12, 10, 18), bar.inflate(6, 6))
            pygame.draw.rect(surface, (60, 24, 30), bar)
            fill = bar.copy()
            fill.width = int(bar.width * frac)
            pygame.draw.rect(surface, (220, 70, 70), fill)
            pygame.draw.rect(surface, PANEL_BORDER, bar.inflate(6, 6), 2)
            if self.heart_frames:
                heart = pygame.transform.scale(self.heart_frames[0], (30, 30))
                surface.blit(heart, heart.get_rect(center=(bar.left - 26, bar.centery)))
            hp_lab = self.font_sm.render(f"{max(0, self.player.hp)}/{self.player.max_hp}", False, TEXT_MAIN)
            surface.blit(hp_lab, (bar.right + 12, bar.top))

    def draw(self, surface):
        if self.phase == TutorialPhase.TEXT_MAP:
            page = self.map_pages[self.map_page_index]
            self._draw_text_screen(surface, "TUTORIAL - MAPA", page,
                                   dots=(len(self.map_pages), self.map_page_index))

        elif self.phase == TutorialPhase.COMBAT_PRACTICE:
            surface.fill((13, 13, 17))
            cam_x, cam_y = int(self.cam_x), int(self.cam_y)
            if self.practice_bg:
                surface.blit(self.practice_bg, (cam_x, cam_y))

            if self.dummy_target:
                self.dummy_target.draw(surface, cam_x, cam_y)
                # barra de vida del bug
                e = self.dummy_target
                bar = pygame.Rect(0, 0, 52, 7)
                bar.center = (int(e.x) + cam_x, e.rect.top - 14 + cam_y)
                pygame.draw.rect(surface, (12, 10, 18), bar.inflate(4, 4))
                pygame.draw.rect(surface, (60, 24, 30), bar)
                fill = bar.copy()
                fill.width = int(bar.width * max(0.0, e.hp / e.max_hp))
                pygame.draw.rect(surface, (120, 220, 120), fill)
            if self.player:
                self.player.draw(surface, cam_x, cam_y)

            self._draw_practice_hud(surface)

            if self.revive_timer > 0:
                msg = self.font_md.render("¡Sin vida! Te revivimos: esto es práctica.", True, (255, 120, 120))
                msg.set_alpha(min(255, self.revive_timer * 4))
                surface.blit(msg, msg.get_rect(center=(self.width // 2, self.height - 90)))

            if self.victory_timer > 0:
                ok = render_3d_gradient_text("¡BUG ELIMINADO!", self.font_lg)
                surface.blit(ok, ok.get_rect(center=(self.width // 2, self.height // 2 - 40)))

        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            self._draw_text_screen(surface, "TUTORIAL - ENEMIGOS", self.enemies_page)

        elif self.phase == TutorialPhase.OUTRO:
            draw_dark_cross_bg(surface, self.width, self.height, self.timer)
            title = render_3d_gradient_text("¡TUTORIAL COMPLETADO!", self.font_lg)
            surface.blit(title, title.get_rect(center=(self.width // 2, self.height // 2 - 40)))
            msg = self.font_md.render("Ya estás listo para la experiencia real. ¡Disfrútala!", True, TEXT_MAIN)
            surface.blit(msg, msg.get_rect(center=(self.width // 2, self.height // 2 + 30)))
