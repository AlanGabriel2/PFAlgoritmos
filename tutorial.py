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

class TutorialState:
    def __init__(self, width, height, font_lg, font_md, font_sm):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.font_sm = font_sm
        
        self.phase = TutorialPhase.TEXT_MAP
        self.timer = 0
        
        # Combat practice entities
        self.player = None
        self.dummy_target = None
        self.collision_manager = load_combat_level(fallback_size=(width, height)).create_collision_manager()
        
        # UI messages
        self.map_msg = [
            "Bienvenido al Mega-Calabozo DAG.",
            "El mapa representa un Grafo Dirigido Aciclico (DAG).",
            "Cada habitacion es una 'materia' academica.",
            "Para avanzar, debes limpiar materias respetando sus pre-requisitos.",
            "Las materias de tu Camino Critico apareceran resaltadas.",
            "El Camino Critico dicta tu tiempo minimo de graduacion.",
            "",
            "(Presiona ESPACIO o ENTER para continuar)"
        ]
        
        self.combat_msg = [
            "Una vez en la habitacion, muevete con WASD o Flechas.",
            "Apunta y dispara con el clic del raton."
        ]
        
        self.enemies_msg = [
            "¡Si que sabes moverte!",
            "El calabozo esta lleno de enemigos academicos.",
            "Bugs, Codigo Spaghetti, Memory Leaks y el implacable Deadline.",
            "A continuacion, te presento el Bestiario...",
            "",
            "(Presiona ESPACIO o ENTER para ver el Bestiario)"
        ]

    def reset(self):
        self.phase = TutorialPhase.TEXT_MAP
        self.timer = 0
        self.player = None
        self.dummy_target = None
        self.collision_manager = load_combat_level(fallback_size=(self.width, self.height)).create_collision_manager()

    def handle_event(self, event, mouse_x, mouse_y):
        if self.phase == TutorialPhase.TEXT_MAP:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                self.phase = TutorialPhase.COMBAT_PRACTICE
                self.player = Player(self.width // 2, self.height // 2)
                # Spawn a dummy bug that doesn't move just to have a target
                self.dummy_target = BugEnemy(self.width // 2 + 200, self.height // 2)
                self.dummy_target.speed = 0
                self.timer = 0
                
        elif self.phase == TutorialPhase.COMBAT_PRACTICE:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.player.shoot(mouse_x, mouse_y)
                
        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            if event.type == pygame.KEYDOWN and event.key in [pygame.K_SPACE, pygame.K_RETURN]:
                self.phase = TutorialPhase.DONE
                return "GO_TO_BESTIARY"
                
        return None

    def update(self, keys, width, height):
        if self.phase == TutorialPhase.COMBAT_PRACTICE:
            # Player movement
            self.player.move(keys, width, height, self.collision_manager)
            self.player.update_bullets(width, height)
            
            # Allow arrow key shooting in tutorial
            dx, dy = 0, 0
            if keys[pygame.K_UP]: dy -= 1
            if keys[pygame.K_DOWN]: dy += 1
            if keys[pygame.K_LEFT]: dx -= 1
            if keys[pygame.K_RIGHT]: dx += 1
            if dx != 0 or dy != 0:
                self.player.shoot_angle(math.atan2(dy, dx))
            
            if self.dummy_target:
                self.dummy_target.animator.update()
                
                # Check bullets hitting dummy
                for b in self.player.bullets[:]:
                    if self.dummy_target and self.dummy_target.collides_with_bullet(b):
                        self.player.bullets.remove(b)
                        self.dummy_target.hp -= 10
                        if self.dummy_target.hp <= 0:
                            self.dummy_target = None
            
            # Progress phase if dummy killed
            if self.dummy_target is None:
                self.phase = TutorialPhase.TEXT_ENEMIES
                self.player = None

    def _draw_text_lines(self, surface, lines, y_start):
        for i, line in enumerate(lines):
            text = self.font_md.render(line, True, (255, 255, 255))
            rect = text.get_rect(center=(self.width // 2, y_start + i * 40))
            surface.blit(text, rect)

    def draw(self, surface):
        surface.fill((20, 20, 25))
        
        if self.phase == TutorialPhase.TEXT_MAP:
            title = self.font_lg.render("TUTORIAL - MAPA", True, (100, 255, 100))
            surface.blit(title, title.get_rect(center=(self.width // 2, self.height // 4)))
            self._draw_text_lines(surface, self.map_msg, self.height // 2)
            
        elif self.phase == TutorialPhase.COMBAT_PRACTICE:
            # Draw hints at top
            hint = self.font_md.render(self.combat_msg[0], True, (200, 200, 200))
            hint2 = self.font_md.render(self.combat_msg[1], True, (200, 200, 200))
            surface.blit(hint, hint.get_rect(center=(self.width // 2, 50)))
            surface.blit(hint2, hint2.get_rect(center=(self.width // 2, 90)))
            
            if self.dummy_target:
                self.dummy_target.draw(surface)
            if self.player:
                self.player.draw(surface)
                
        elif self.phase == TutorialPhase.TEXT_ENEMIES:
            title = self.font_lg.render("TUTORIAL - ENEMIGOS", True, (255, 100, 100))
            surface.blit(title, title.get_rect(center=(self.width // 2, self.height // 4)))
            self._draw_text_lines(surface, self.enemies_msg, self.height // 2)
