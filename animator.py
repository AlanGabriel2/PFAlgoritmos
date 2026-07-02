import pygame

_animation_cache = {}

class Animator:
    def __init__(self, spritesheet_path, frame_width, frame_height, rows, cols, animation_speed=0.15, transpose=False):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.animation_speed = animation_speed
        
        self.current_row = 0
        self.current_frame = 0.0
        self._last_update_ms = None

        cache_key = (spritesheet_path, frame_width, frame_height, rows, cols, transpose)
        if cache_key in _animation_cache:
            self.frames = _animation_cache[cache_key]
        else:
            self.frames = {} # dict of row_index -> list of surfaces
            self.load_spritesheet(spritesheet_path, rows, cols, transpose)
            _animation_cache[cache_key] = self.frames
        
    def load_spritesheet(self, path, rows, cols, transpose):
        try:
            sheet = pygame.image.load(path).convert_alpha()
            
            width, height = sheet.get_size()
            orig_frame_width = width // cols
            orig_frame_height = height // rows
            
            # Si transpose es True, invertimos filas y columnas
            num_states = cols if transpose else rows
            num_frames_per_state = rows if transpose else cols
            
            for i in range(num_states):
                self.frames[i] = []
                for j in range(num_frames_per_state):
                    col = i if transpose else j
                    row = j if transpose else i
                    
                    rect = pygame.Rect(col * orig_frame_width, row * orig_frame_height, orig_frame_width, orig_frame_height)
                    cell = pygame.Surface((orig_frame_width, orig_frame_height), pygame.SRCALPHA)
                    cell.blit(sheet, (0, 0), rect)
                    
                    # Como la imagen ya es transparente, usamos el cuadro delimitador exacto 
                    # para eliminar los espacios vacíos y centrar perfectamente la animación.
                    bbox = cell.get_bounding_rect()
                    
                    if bbox.width > 0 and bbox.height > 0:
                        image = pygame.Surface(bbox.size, pygame.SRCALPHA)
                        image.blit(cell, (0, 0), bbox)
                    else:
                        image = cell # Fallback por si el frame está totalmente vacío
                    
                    # Escalar al tamaño deseado en el juego, manteniendo la proporción exacta del personaje
                    # Tomamos la altura deseada (self.frame_height) y calculamos la anchura proporcional
                    if image.get_height() > 0:
                        aspect_ratio = image.get_width() / image.get_height()
                        new_width = max(1, int(self.frame_height * aspect_ratio))
                        image = pygame.transform.scale(image, (new_width, self.frame_height))
                        
                    self.frames[i].append(image)
        except Exception as e:
            print(f"Error loading spritesheet {path}: {e}")
            # Crear frames vacios como fallback
            for row in range(rows):
                self.frames[row] = []
                for col in range(cols):
                    surf = pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)
                    pygame.draw.rect(surf, (255, 0, 255), (0, 0, self.frame_width, self.frame_height))
                    self.frames[row].append(surf)

    def set_state(self, row_index):
        if self.current_row != row_index:
            self.current_row = row_index
            self.current_frame = 0.0

    def update(self):
        # Avance basado en tiempo real: la velocidad de animacion es independiente
        # del FPS de render. A 60 FPS coincide exactamente con el comportamiento previo
        # (animation_speed = cuadros de sprite por tick de 60 Hz).
        now = pygame.time.get_ticks()
        if self._last_update_ms is None:
            self._last_update_ms = now
        dt_ms = now - self._last_update_ms
        self._last_update_ms = now
        # Limitar dt para evitar saltos grandes tras una pausa o perdida de foco.
        if dt_ms < 0:
            dt_ms = 0
        elif dt_ms > 100:
            dt_ms = 100

        if self.current_row in self.frames:
            num_frames = len(self.frames[self.current_row])
            if num_frames > 0:
                self.current_frame += self.animation_speed * (dt_ms / (1000.0 / 60.0))
                if self.current_frame >= num_frames:
                    self.current_frame %= num_frames

    def get_current_image(self):
        if self.current_row in self.frames and len(self.frames[self.current_row]) > 0:
            return self.frames[self.current_row][int(self.current_frame)]
        return None
