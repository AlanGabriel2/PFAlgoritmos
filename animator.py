import pygame

# Frames cortados a tamaño NATIVO (sin escalar), por spritesheet. Esta es la parte
# CARA (leer disco + convert_alpha + recortar cada frame + bounding-rect) y se hace
# UNA sola vez por hoja, independientemente de la escala del nivel.
_native_cache = {}

# Frames ya escalados a una altura objetivo concreta. Derivarlos del corte nativo es
# barato (solo transform.scale), así que niveles con distinta escala comparten el
# mismo corte nativo y solo pagan el reescalado la primera vez.
_scaled_cache = {}


def _magenta_frame(size):
    size = max(1, int(size))
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (255, 0, 255), (0, 0, size, size))
    return surf


def _load_native_frames(path, rows, cols, transpose):
    """Corta la hoja a tamaño nativo, recortando el espacio vacío de cada frame.

    Cacheado por (path, rows, cols, transpose): el trabajo caro (disco + decode +
    bounding-rect) se hace una única vez, aunque el sprite se use luego a varias
    escalas. Devuelve dict {estado: [Surface, ...]} o None si falla la carga.
    """
    key = (path, rows, cols, transpose)
    cached = _native_cache.get(key)
    if cached is not None:
        return cached

    frames = {}
    try:
        sheet = pygame.image.load(path).convert_alpha()

        width, height = sheet.get_size()
        orig_frame_width = width // cols
        orig_frame_height = height // rows

        # Si transpose es True, invertimos filas y columnas
        num_states = cols if transpose else rows
        num_frames_per_state = rows if transpose else cols

        for i in range(num_states):
            frames[i] = []
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
                    image = cell  # Fallback por si el frame está totalmente vacío

                frames[i].append(image)
    except Exception as e:
        print(f"Error loading spritesheet {path}: {e}")
        frames = None

    _native_cache[key] = frames
    return frames


def _get_scaled_frames(path, target_height, rows, cols, transpose):
    """Frames escalados a `target_height` de altura (ancho proporcional exacto).

    Cacheado por altura objetivo; se derivan del corte nativo, así que el coste es
    solo el de unos pocos transform.scale (barato). Si no hay corte nativo válido,
    genera frames magenta de relleno.
    """
    key = (path, rows, cols, transpose, int(target_height))
    cached = _scaled_cache.get(key)
    if cached is not None:
        return cached

    native = _load_native_frames(path, rows, cols, transpose)
    if native is None:
        # Fallback: rectángulos magenta como marcador de error.
        frames = {row: [_magenta_frame(target_height) for _ in range(cols)] for row in range(rows)}
        _scaled_cache[key] = frames
        return frames

    frames = {}
    for state, images in native.items():
        frames[state] = []
        for image in images:
            if image.get_height() > 0:
                aspect_ratio = image.get_width() / image.get_height()
                new_width = max(1, int(target_height * aspect_ratio))
                image = pygame.transform.scale(image, (new_width, int(target_height)))
            frames[state].append(image)

    _scaled_cache[key] = frames
    return frames


def preload_spritesheet(path, frame_height, rows, cols, transpose=False):
    """Precalienta el caché de una hoja (corte nativo + escala dada) sin crear un
    Animator. Útil para pantallas de carga. Es idempotente y barato tras la 1ª vez.
    """
    _get_scaled_frames(path, int(frame_height), rows, cols, transpose)


class Animator:
    def __init__(self, spritesheet_path, frame_width, frame_height, rows, cols, animation_speed=0.15, transpose=False):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.animation_speed = animation_speed

        self.current_row = 0
        self.current_frame = 0.0
        self._last_update_ms = None

        # Los frames vienen del caché compartido: el primer uso de la hoja hace el
        # corte nativo (una vez) y el escalado a esta altura (una vez por escala).
        self.frames = _get_scaled_frames(spritesheet_path, frame_height, rows, cols, transpose)

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
