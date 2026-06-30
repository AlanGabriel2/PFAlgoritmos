import pygame
import math
from data import SUBJECTS
from dag_engine import NodeState

# Constants
ROOM_WIDTH = 120
ROOM_HEIGHT = 60
MARGIN_X = 40
MARGIN_Y = 140

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
        # Colores Temáticos
        color = (150, 140, 120) # BLOQUEADO (Grisáceo polvoriento / marrón)
        if state == NodeState.UNLOCKED:
            color = (230, 210, 160) # DESBLOQUEADO (Pergamino)
        elif state == NodeState.CLEANED:
            color = (160, 210, 160) # COMPLETADO (Pergamino verdoso)

        # Sombra (Drop Shadow)
        shadow_rect = self.rect.copy()
        shadow_rect.x += 4
        shadow_rect.y += 4
        pygame.draw.rect(surface, (10, 10, 15), shadow_rect, border_radius=8)
        
        # Efecto de pulso para nodos desbloqueados o críticos
        if state == NodeState.UNLOCKED:
            pulse = (math.sin(pygame.time.get_ticks() / 200.0) + 1) / 2.0
            glow_rect = self.rect.inflate(int(pulse * 10), int(pulse * 10))
            glow_color = node_color if node_color else (255, 230, 150)
            
            # Dibujar un borde difuminado/brillante
            glow_surf = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (*glow_color, int(100 * pulse)), glow_surf.get_rect(), border_radius=12)
            surface.blit(glow_surf, glow_rect.topleft)

        # Dibujar el rectángulo de la habitación con esquinas redondeadas
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        
        # Borde
        border_color = node_color if node_color else (60, 40, 20)
        border_width = 5 if node_color else 3
        pygame.draw.rect(surface, border_color, self.rect, border_width, border_radius=8)

        # Dibujar el texto
        y_offset = self.rect.y + 5
        for line in self.lines:
            # El texto siempre es marrón oscuro para mantener legibilidad
            text_color = (40, 20, 10)
            text_surface = font.render(line, False, text_color)
            text_rect = text_surface.get_rect(center=(self.rect.centerx, y_offset + 10))
            surface.blit(text_surface, text_rect)
            y_offset += 16

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
        # Dibujar aristas
        for start_pos, end_pos, edge_colors in self.edges:
            adj_start = (start_pos[0] + camera_offset_x, start_pos[1] + camera_offset_y)
            adj_end = (end_pos[0] + camera_offset_x, end_pos[1] + camera_offset_y)
            
            if not edge_colors:
                pygame.draw.line(surface, (100, 100, 100), adj_start, adj_end, 2)
                pygame.draw.circle(surface, (100, 100, 100), adj_end, 4)
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
                    offset_x = nx * offset
                    offset_y = ny * offset
                    
                    line_start = (adj_start[0] + offset_x, adj_start[1] + offset_y)
                    line_end = (adj_end[0] + offset_x, adj_end[1] + offset_y)
                    
                    pygame.draw.line(surface, color, line_start, line_end, edge_width)
                    # Marcador (un poco desplazado hacia el centro al final para convergir)
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
