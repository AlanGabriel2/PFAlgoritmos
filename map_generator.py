import pygame
import math
from data import SUBJECTS
from dag_engine import NodeState

# Constants
ROOM_WIDTH = 120
ROOM_HEIGHT = 60
MARGIN_X = 40
MARGIN_Y = 140


def _draw_edge_line(surface, a, b, color, width, outline=(12, 10, 18)):
    """Dibuja una arista con casing oscuro para dar contraste. Misma geometria."""
    pygame.draw.line(surface, outline, a, b, width + 3)
    pygame.draw.line(surface, color, a, b, width)

class Room:
    def __init__(self, node_id, name, x, y):
        self.id = node_id
        self.name = name
        self.rect = pygame.Rect(x, y, ROOM_WIDTH, ROOM_HEIGHT)
        # Wrap text
        self.lines = self._wrap_text(name, 15)

    def _wrap_text(self, text, max_chars):
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) <= max_chars:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())
        return lines

    def draw(self, surface, font, state, node_color=None):
        # Mismos estados; solo cambia la PRESENTACION (paleta, relieve, glifos).
        is_special = (self.id == "TIP10TEMTT1")
        r = self.rect

        if state == NodeState.UNLOCKED:
            fill = (232, 214, 168); bevel = (255, 245, 212); text_color = (66, 44, 22)
        elif state == NodeState.CLEANED:
            fill = (156, 200, 156); bevel = (214, 242, 214); text_color = (32, 60, 32)
        else:  # BLOQUEADO: apagado/desaturado, pero con texto legible
            fill = (92, 86, 104); bevel = (130, 122, 148); text_color = (182, 176, 196)

        # Sombra (drop shadow suave)
        sh = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 115), sh.get_rect(), border_radius=9)
        surface.blit(sh, (r.x + 4, r.y + 5))

        # Glow pulsante para nodos disponibles (o el nodo final aun pendiente)
        if state == NodeState.UNLOCKED or (is_special and state != NodeState.CLEANED):
            pulse = (math.sin(pygame.time.get_ticks() / 260.0) + 1) / 2.0
            gcol = node_color if node_color else ((255, 216, 110) if is_special else (255, 232, 170))
            grow = int(4 + pulse * 8)
            gr = r.inflate(grow, grow)
            glow_surf = pygame.Surface((gr.width, gr.height), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (gcol[0], gcol[1], gcol[2], int(40 + 70 * pulse)), glow_surf.get_rect(), border_radius=12)
            surface.blit(glow_surf, gr.topleft)

        # Cuerpo + bisel interior (sensacion de relieve)
        pygame.draw.rect(surface, fill, r, border_radius=8)
        pygame.draw.rect(surface, bevel, r.inflate(-4, -4), 1, border_radius=6)

        # Borde exterior + borde de camino critico / nodo especial
        pygame.draw.rect(surface, (22, 16, 12), r, 2, border_radius=8)
        if is_special:
            pygame.draw.rect(surface, (255, 205, 90), r, 3, border_radius=8)
        elif node_color:
            pygame.draw.rect(surface, node_color, r, 3, border_radius=8)

        # Glifo de estado (ANTES del texto: la legibilidad del texto tiene prioridad)
        self._draw_state_glyph(surface, state, is_special)

        # Texto con sombra sutil (mismo contenido y mismo wrap)
        y_offset = r.y + 5
        for line in self.lines:
            text_surface = font.render(line, False, text_color)
            text_rect = text_surface.get_rect(center=(r.centerx, y_offset + 10))
            surface.blit(font.render(line, False, (18, 14, 22)), (text_rect.x + 1, text_rect.y + 1))
            surface.blit(text_surface, text_rect)
            y_offset += 16

    def _draw_state_glyph(self, surface, state, is_special):
        r = self.rect
        gx, gy = r.right - 16, r.top + 5
        if is_special and state != NodeState.CLEANED:
            self._draw_star(surface, gx + 5, gy + 6, 6, (255, 212, 96))
        elif state == NodeState.CLEANED:
            pygame.draw.lines(surface, (34, 110, 34), False,
                              [(gx, gy + 6), (gx + 4, gy + 10), (gx + 12, gy + 1)], 3)
        elif state == NodeState.LOCKED:
            body = pygame.Rect(gx, gy + 5, 12, 8)
            pygame.draw.arc(surface, (206, 200, 218), (gx + 2, gy - 1, 8, 11), 0.15, math.pi - 0.15, 2)
            pygame.draw.rect(surface, (206, 200, 218), body, border_radius=2)
            pygame.draw.rect(surface, (34, 28, 44), body, 1, border_radius=2)

    def _draw_star(self, surface, cx, cy, rad, col):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = rad if i % 2 == 0 else rad * 0.45
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, (120, 78, 8), pts, 1)

class MapGenerator:
    def __init__(self, dag_engine):
        self.engine = dag_engine
        self.rooms = {}
        self.edges = [] # Lista de tuplas ((start_x, start_y), (end_x, end_y), is_critical)
        self._generate_layout()

    def _generate_layout(self):
        # Agrupar nodos por Semestre usando el código (ej. TIP01 -> Semestre 1)
        levels = {}
        for node in self.engine.nodes:
            try:
                sem = int(node[3:5])
            except:
                sem = 1 # Fallback
            if sem not in levels:
                levels[sem] = []
            levels[sem].append(node)

        # Asignar coordenadas
        start_x = 50
        start_y = 50
        
        for level in sorted(levels.keys()):
            nodes_in_level = levels[level]
            # Espaciado horizontal
            x = start_x
            for node in nodes_in_level:
                self.rooms[node] = Room(node, SUBJECTS[node]['name'], x, start_y)
                x += ROOM_WIDTH + MARGIN_X
                
            start_y += ROOM_HEIGHT + MARGIN_Y
            
        # Generar aristas
        for node in self.engine.nodes:
            for req in SUBJECTS[node]['reqs']:
                if req in self.rooms:
                    req_room = self.rooms[req]
                    node_room = self.rooms[node]
                    
                    # Conectar parte inferior de req_room a la parte superior de node_room
                    start_pos = (req_room.rect.centerx, req_room.rect.bottom)
                    end_pos = (node_room.rect.centerx, node_room.rect.top)
                    
                    # Checar si la arista es parte del camino crítico y obtener su color
                    edge_color = self.engine.edge_colors.get((req, node), None)
                    
                    self.edges.append((start_pos, end_pos, edge_color))

    def draw(self, surface, font, camera_offset_x=0, camera_offset_y=0):
        # Dibujar aristas (mismos endpoints y misma logica de caminos criticos;
        # solo se mejora el acabado: casing oscuro para contraste y marcadores limpios).
        for start_pos, end_pos, edge_colors in self.edges:
            adj_start = (start_pos[0] + camera_offset_x, start_pos[1] + camera_offset_y)
            adj_end = (end_pos[0] + camera_offset_x, end_pos[1] + camera_offset_y)

            if not edge_colors:
                _draw_edge_line(surface, adj_start, adj_end, (126, 122, 142), 2)
                pygame.draw.circle(surface, (12, 10, 18), (int(adj_end[0]), int(adj_end[1])), 5)
                pygame.draw.circle(surface, (150, 146, 166), (int(adj_end[0]), int(adj_end[1])), 3)
            else:
                # Dibujar líneas paralelas para cada color
                n_colors = len(edge_colors)
                dx = adj_end[0] - adj_start[0]
                dy = adj_end[1] - adj_start[1]
                length = math.hypot(dx, dy)

                if length == 0:
                    continue

                # Vector normal (perpendicular) unitario
                nx = -dy / length
                ny = dx / length

                spacing = 4 # Espaciado entre líneas paralelas
                total_width = (n_colors - 1) * spacing
                start_offset = -total_width / 2.0

                edge_width = max(2, 6 // n_colors) if n_colors > 1 else 4

                for i, color in enumerate(edge_colors):
                    offset = start_offset + i * spacing
                    line_start = (adj_start[0] + nx * offset, adj_start[1] + ny * offset)
                    line_end = (adj_end[0] + nx * offset, adj_end[1] + ny * offset)
                    _draw_edge_line(surface, line_start, line_end, color, edge_width)
                # Marcadores al final (encima de las lineas, para que converjan limpios)
                for i, color in enumerate(edge_colors):
                    offset = start_offset + i * spacing
                    line_end = (int(adj_end[0] + nx * offset), int(adj_end[1] + ny * offset))
                    pygame.draw.circle(surface, color, line_end, edge_width + 1)

        # Dibujar habitaciones
        for node, room in self.rooms.items():
            # Ajustar el rectángulo de la habitación para el dibujado con cámara
            original_rect = room.rect.copy()
            room.rect.x += camera_offset_x
            room.rect.y += camera_offset_y
            
            state = self.engine.state[node]
            node_color = self.engine.node_colors.get(node, None)
            room.draw(surface, font, state, node_color)
            
            # Restaurar rectángulo
            room.rect = original_rect

    def get_room_at(self, x, y, camera_offset_x=0, camera_offset_y=0):
        for node, room in self.rooms.items():
            adj_rect = room.rect.copy()
            adj_rect.x += camera_offset_x
            adj_rect.y += camera_offset_y
            if adj_rect.collidepoint(x, y):
                return node
        return None
