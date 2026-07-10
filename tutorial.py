import pygame
import math
from player import Player
from enemy import BugEnemy
from level import load_combat_level

class TutorialPhase:
    TEXT_MAP = 0
    COMBAT_PRACTICE = 1
    TEXT_ENEMIES = 2
    DONE = 3
    OUTRO = 4

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
        
        # Combat practice entities
        self.player = None
        self.dummy_target = None
        self.collision_manager = load_combat_level(fallback_size=(width, height)).create_collision_manager()
        
        # UI messages
        self.map_pages = [
            [
                "Bienvenido al Mega-Calabozo DAG.",
                "Este mapa es una malla curricular",
                "de la carrera de Sistemas de Información.",
                "Cada habitación es una 'materia' académica.",
                "Haz un clic en el nodo y presiona ENTER, o",
                "haz doble clic para entrar a la materia.",
                "",
                "(Presiona ESPACIO o ENTER para continuar)"
            ],
            [
                "El color de las materias y aristas es importante:",
                "Los 8 colores de las aristas muestran los",
                "8 posibles caminos críticos.",
                "Además, el fondo de las batallas cambiará visualmente",
                "dependiendo de en qué semestre te encuentres.",
                "",
                "(Presiona ESPACIO o ENTER para continuar)"
            ],
            [
                "¿Cómo calculamos los caminos críticos?",
                "Usamos Programación Dinámica sobre el grafo (DAG):",
                "primero ordenamos las materias con un Orden Topológico",
                "(algoritmo de Kahn) y luego calculamos para cada materia",
                "su cadena más larga de prerrequisitos.",
                "El valor máximo define el 'Tiempo Récord' de la carrera.",
                "",
                "(Presiona ESPACIO o ENTER para continuar)"
            ],
            [
                "Mecánicas de supervivencia:",
                "Cada combate consume 1 punto de Energía.",
                "Si te quedas sin energía, debes pulsar ESPACIO en el",
                "mapa para 'Descansar', recuperando la energía pero",
                "avanzando al siguiente semestre.",
                "",
                "(Presiona ESPACIO o ENTER para continuar)"
            ],
            [
                "Tu objetivo final es la Titulación.",
                "Limpia todas las materias respetando prerrequisitos.",
                "Al final te enfrentarás al Mega Boss.",
                "Cuida tu Vida (HP), si llega a 0, fallarás el intento.",
                "",
                "(Presiona ESPACIO o ENTER para practicar combate)"
            ]
        ]
        
        self.combat_msg = [
            "Mueve tu personaje EXCLUSIVAMENTE con W, A, S, D.",
            "Apunta y dispara con el Ratón o con las Flechas Direccionales.",
            "¡Cuidado, el enemigo contraataca! Intenta eliminarlo."
        ]
        
        self.enemies_msg = [
            "Ahora ya manejas los controles básicos.",
            "El calabozo está lleno de enemigos académicos.",
            "Bugs, Código Spaghetti, Memory Leaks y el implacable Deadline.",
            "A continuación, te presento el Bestiario...",
            "",
            "(Presiona ESPACIO o ENTER para ver el Bestiario)"
        ]

    def reset(self):
        self.phase = TutorialPhase.TEXT_MAP
        self.map_page_index = 0
        self.timer = 0
        self.player = None
        self.dummy_target = None
        self.collision_manager = load_combat_level(fallback_size=(self.width, self.height)).create_collision_manager()

    def handle_event(self, event, mouse_x, mouse_y):
        if self.phase == TutorialPhase.TEXT_MAP:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                if self.map_page_index < len(self.map_pages) - 1:
                    self.map_page_index += 1
                else:
                    self.phase = TutorialPhase.COMBAT_PRACTICE
                    self.player = Player(self.width // 2, self.height // 2)
                    # Spawn a dummy bug that doesn't move just to have a target
                    self.dummy_target = BugEnemy(self.width // 2 + 200, self.height // 2)
                    self.dummy_target.speed = 0
                    self.dummy_target.hp = 100 # High HP to avoid instant kill
                    self.timer = 0
                
        elif self.phase == TutorialPhase.COMBAT_PRACTICE:
            pass # Shooting moved to update to allow holding mouse button
                
        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                return "GO_TO_BESTIARY"
                
        elif self.phase == TutorialPhase.OUTRO:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                self.phase = TutorialPhase.DONE
                return "FINISH_TUTORIAL"
                
        return None

    def update(self, keys, width, height, mouse_x=None, mouse_y=None):
        self.timer += 1
        if self.phase == TutorialPhase.COMBAT_PRACTICE:
            # Player movement
            self.player.move(keys, width, height, self.collision_manager)
            self.player.update_bullets(width, height)
            
            # Continuous mouse shooting with the same virtual-screen coordinates used in combat.
            if mouse_x is None or mouse_y is None:
                mouse_x, mouse_y = pygame.mouse.get_pos()
            if pygame.mouse.get_pressed()[0]:
                self.player.shoot_angle(math.atan2(mouse_y - self.player.y, mouse_x - self.player.x))

            # Allow arrow key shooting in tutorial
            dx, dy = 0, 0
            if keys[pygame.K_UP]: dy -= 1
            if keys[pygame.K_DOWN]: dy += 1
            if keys[pygame.K_LEFT]: dx -= 1
            if keys[pygame.K_RIGHT]: dx += 1
            if dx != 0 or dy != 0:
                self.player.shoot_angle(math.atan2(dy, dx))
            
            if self.dummy_target:
                self.dummy_target.update(self.player.x, self.player.y, width, height, self.collision_manager, None, [self.dummy_target])
                
                # Check bullets hitting dummy
                for b in self.player.bullets[:]:
                    if self.dummy_target and self.dummy_target.collides_with_bullet(b):
                        self.player.bullets.remove(b)
                        self.dummy_target.hp -= 10
                        if self.dummy_target.hp <= 0:
                            self.dummy_target = None
                            
                # Dummy damages player
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
                                
            # Check player death in tutorial
            if self.player.hp <= 0:
                self.player.hp = self.player.max_hp # Revive instantly to practice
            
            # Progress phase if dummy killed
            if self.dummy_target is None:
                self.phase = TutorialPhase.TEXT_ENEMIES
                self.player = None
        elif self.phase == TutorialPhase.OUTRO:
            if self.timer >= 150:
                self.phase = TutorialPhase.DONE
                return "FINISH_TUTORIAL"
        return None

    def _draw_text_lines(self, surface, lines, y_start):
        for i, line in enumerate(lines):
            center_y = y_start + i * 40
            if self._is_prompt_line(line):
                self._draw_prompt(surface, line, center_y)
                continue
            text = self.font_md.render(line, True, (255, 255, 255))
            rect = text.get_rect(center=(self.width // 2, center_y))
            surface.blit(text, rect)

    def _is_prompt_line(self, line):
        return line.strip().startswith("(Presiona")

    def _draw_prompt(self, surface, line, center_y):
        text = self.font_md.render(line, True, (185, 185, 185))
        text.set_alpha(150)
        rect = text.get_rect(center=(self.width // 2, center_y))
        surface.blit(text, rect)

    def draw(self, surface):
        surface.fill((20, 20, 25))
        
        if self.phase == TutorialPhase.TEXT_MAP:
            title = self.font_lg.render("TUTORIAL - MAPA", True, (100, 255, 100))
            surface.blit(title, title.get_rect(center=(self.width // 2, self.height // 4)))
            if self.map_page_index == 4:
                body_lines = [line for line in self.map_pages[self.map_page_index] if not self._is_prompt_line(line)]
                self._draw_text_lines(surface, body_lines, self.height // 2 - 92)
            else:
                self._draw_text_lines(surface, self.map_pages[self.map_page_index], self.height // 2 - 50)

            # Draw visual examples
            if self.map_page_index == 3: # Energía
                energy_text = self.font_lg.render("Ejemplo:  Energia: 5/5", True, (255, 255, 100))
                surface.blit(energy_text, energy_text.get_rect(center=(self.width // 2, self.height - 100)))
            elif self.map_page_index == 4: # Vida (Corazones)
                if self.heart_frames and len(self.heart_frames) > 0:
                    hx = self.width // 2
                    hy = self.height - 175
                    
                    # Animate decreasing health
                    frame_idx = len(self.heart_frames) - 1 - ((self.timer // 30) % len(self.heart_frames))
                    
                    large_heart = pygame.transform.scale(self.heart_frames[frame_idx], (84, 84))
                    surface.blit(large_heart, large_heart.get_rect(center=(hx, hy)))
                    
                    hp_example = self.font_md.render("Vida (Se reduce al recibir daño)", True, (255, 100, 100))
                    surface.blit(hp_example, hp_example.get_rect(center=(self.width // 2, hy - 60)))
                self._draw_prompt(surface, "(Presiona ESPACIO o ENTER para practicar combate)", self.height - 72)

            
        elif self.phase == TutorialPhase.COMBAT_PRACTICE:
            # Draw hints at top
            hint = self.font_md.render(self.combat_msg[0], True, (200, 200, 200))
            hint2 = self.font_md.render(self.combat_msg[1], True, (200, 200, 200))
            hint3 = self.font_md.render(self.combat_msg[2], True, (255, 100, 100))
            surface.blit(hint, hint.get_rect(center=(self.width // 2, 40)))
            surface.blit(hint2, hint2.get_rect(center=(self.width // 2, 80)))
            surface.blit(hint3, hint3.get_rect(center=(self.width // 2, 120)))
            
            if self.dummy_target:
                self.dummy_target.draw(surface)
            if self.player:
                self.player.draw(surface)
                
        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            title = self.font_lg.render("TUTORIAL - ENEMIGOS", True, (255, 100, 100))
            surface.blit(title, title.get_rect(center=(self.width // 2, self.height // 4)))
            self._draw_text_lines(surface, self.enemies_msg, self.height // 2)
            
        elif self.phase == TutorialPhase.OUTRO:
            surface.fill((10, 10, 15))
            msg = self.font_md.render("Ya estás listo para la experiencia real. ¡Disfrútala!", True, (255, 255, 255))
            surface.blit(msg, msg.get_rect(center=(self.width // 2, self.height // 2)))
