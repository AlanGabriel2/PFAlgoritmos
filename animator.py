import pygame
from statistics import median

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

    # Todos los fotogramas de una hoja comparten escala y lienzo. Antes cada bbox
    # se forzaba por separado a target_height: un brazo extendido o un efecto hacía
    # que el cuerpo cambiara de tamaño y que los pies vibraran entre fotogramas.
    # La primera animación (idle) define la altura visual de referencia.
    reference_images = native.get(0) or next(iter(native.values()), [])
    reference_heights = [image.get_height() for image in reference_images if image.get_height() > 0]
    reference_height = median(reference_heights) if reference_heights else max(1, target_height)
    uniform_scale = target_height / max(1, reference_height)

    scaled_by_state = {}
    canvas_w = 1
    canvas_h = 1
    for state, images in native.items():
        scaled_by_state[state] = []
        for image in images:
            new_w = max(1, int(round(image.get_width() * uniform_scale)))
            new_h = max(1, int(round(image.get_height() * uniform_scale)))
            scaled = pygame.transform.scale(image, (new_w, new_h))
            scaled_by_state[state].append(scaled)
            canvas_w = max(canvas_w, new_w)
            canvas_h = max(canvas_h, new_h)

    frames = {}
    for state, images in scaled_by_state.items():
        frames[state] = []
        for image in images:
            canvas = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            # Anclaje común: centro inferior (pies/contacto con el suelo).
            x = (canvas_w - image.get_width()) // 2
            y = canvas_h - image.get_height()
            canvas.blit(image, (x, y))
            frames[state].append(canvas)

    _scaled_cache[key] = frames
    return frames


def preload_spritesheet(path, frame_height, rows, cols, transpose=False):
    """Precalienta el caché de una hoja (corte nativo + escala dada) sin crear un
    Animator. Útil para pantallas de carga. Es idempotente y barato tras la 1ª vez.
    """
    _get_scaled_frames(path, int(frame_height), rows, cols, transpose)


class Animator:
    def __init__(self, spritesheet_path, frame_width, frame_height, rows, cols,
                 animation_speed=0.15, transpose=False, state_speeds=None):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.animation_speed = animation_speed
        self.state_speeds = dict(state_speeds or {})

        self.current_row = 0
        self.current_frame = 0.0
        self._last_update_ms = None

        # Los frames vienen del caché compartido: el primer uso de la hoja hace el
        # corte nativo (una vez) y el escalado a esta altura (una vez por escala).
        self.frames = _get_scaled_frames(spritesheet_path, frame_height, rows, cols, transpose)

    @staticmethod
    def _pad_frame(image, canvas_size):
        """Alinea un frame al centro inferior de un lienzo compartido."""
        canvas_w, canvas_h = canvas_size
        canvas = pygame.Surface(canvas_size, pygame.SRCALPHA)
        x = (canvas_w - image.get_width()) // 2
        y = canvas_h - image.get_height()
        canvas.blit(image, (x, y))
        return canvas

    def replace_state_from_sheet(self, state, spritesheet_path, rows, cols,
                                 frame_height=None, transpose=False):
        """Sustituye un estado con un clip externo y mantiene el mismo pivote.

        Los frames se leen por filas. Esto permite que acciones amplias (ataques,
        muerte, aparición) vivan en hojas propias sin invadir las celdas de idle o
        movimiento.
        """
        height = int(frame_height or self.frame_height)
        clip_states = _get_scaled_frames(spritesheet_path, height, rows, cols, transpose)
        clip = [frame for row in sorted(clip_states) for frame in clip_states[row]]
        if not clip:
            return

        all_frames = [frame for images in self.frames.values() for frame in images] + clip
        canvas_w = max(frame.get_width() for frame in all_frames)
        canvas_h = max(frame.get_height() for frame in all_frames)
        canvas_size = (canvas_w, canvas_h)

        for row, images in list(self.frames.items()):
            self.frames[row] = [self._pad_frame(frame, canvas_size) for frame in images]
        self.frames[state] = [self._pad_frame(frame, canvas_size) for frame in clip]

    def set_state(self, row_index):
        if self.current_row != row_index:
            self.current_row = row_index
            self.current_frame = 0.0

    def update(self, dt_ms=None):
        # Avance basado en tiempo real: la velocidad de animacion es independiente
        # del FPS de render. A 60 FPS coincide exactamente con el comportamiento previo
        # (animation_speed = cuadros de sprite por tick de 60 Hz).
        #
        # `dt_ms` puede inyectarse desde el game loop (hit-stop = dt_ms=0, tests
        # deterministas). Sin argumento conserva el comportamiento previo: mide el
        # tiempo real con pygame.time.get_ticks().
        if dt_ms is None:
            now = pygame.time.get_ticks()
            if self._last_update_ms is None:
                self._last_update_ms = now
            dt_ms = now - self._last_update_ms
            self._last_update_ms = now
        # Limitar dt para evitar saltos grandes tras una pausa o perdida de foco.
        # Aplica tambien al dt inyectado para que ambos caminos se comporten igual.
        if dt_ms < 0:
            dt_ms = 0
        elif dt_ms > 100:
            dt_ms = 100

        if self.current_row in self.frames:
            num_frames = len(self.frames[self.current_row])
            if num_frames > 0:
                speed = self.state_speeds.get(self.current_row, self.animation_speed)
                self.current_frame += speed * (dt_ms / (1000.0 / 60.0))
                if self.current_frame >= num_frames:
                    self.current_frame %= num_frames

    def get_current_image(self):
        if self.current_row in self.frames and len(self.frames[self.current_row]) > 0:
            return self.frames[self.current_row][int(self.current_frame)]
        return None
