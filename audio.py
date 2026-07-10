"""Sistema de audio del juego: música de fondo y efectos de sonido.

Convención de archivos (formatos aceptados: .ogg, .wav, .mp3):
  - Música:  assets/audio/music/<pista>.ogg   (menu, map, combat, boss, boss_final, win)
  - Efectos: assets/audio/sfx/<nombre>.wav    (shoot, hit, hurt, enemy_die, click,
                                               level_clear, level_failed, pause)

Todo es tolerante a fallos: si falta un archivo o no hay dispositivo de audio,
las llamadas simplemente no suenan (el juego nunca truena por audio). Los efectos
que faltan se reportan una sola vez en consola para facilitar depuración.

Volúmenes (0-100, vienen del menú de opciones y del save global):
  - general: volumen maestro; escala los efectos Y la música.
  - música:  volumen propio de la música; el volumen final es general * música.
"""
import os
import pygame

MUSIC_DIR = os.path.join("assets", "audio", "music")
SFX_DIR = os.path.join("assets", "audio", "sfx")
AUDIO_EXTS = (".ogg", ".wav", ".mp3")

MUSIC_FADE_MS = 600
SFX_MIN_INTERVAL_MS = 45   # evita que un mismo efecto se apile y sature en un frame
DUCK_FACTOR = 0.35         # atenuación de la música durante la pausa

_enabled = False
_sfx = {}                  # nombre -> pygame.mixer.Sound
_general = 1.0
_music = 1.0
_duck = 1.0
_current_track = None
_last_sfx_ms = {}
_missing_reported = set()


def _find_file(directory, name):
    for ext in AUDIO_EXTS:
        path = os.path.join(directory, name + ext)
        if os.path.isfile(path):
            return path
    return None


def _load_sfx_bank():
    if not os.path.isdir(SFX_DIR):
        return
    for filename in os.listdir(SFX_DIR):
        stem, ext = os.path.splitext(filename)
        if ext.lower() not in AUDIO_EXTS or stem in _sfx:
            continue
        try:
            _sfx[stem] = pygame.mixer.Sound(os.path.join(SFX_DIR, filename))
        except pygame.error as e:
            print(f"No se pudo cargar el efecto '{filename}': {e}")


def init(general_pct=100, music_pct=100):
    """Inicializa el mixer y carga el banco de efectos. Llamar una vez al arrancar."""
    global _enabled
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
        _enabled = True
    except pygame.error as e:
        print(f"Audio deshabilitado (sin dispositivo de sonido): {e}")
        _enabled = False
        return
    _load_sfx_bank()
    set_volumes(general_pct, music_pct)


def _clamp_pct(value):
    try:
        return max(0.0, min(100.0, float(value))) / 100.0
    except (TypeError, ValueError):
        return 1.0


def _apply_music_volume():
    if _enabled:
        pygame.mixer.music.set_volume(_general * _music * _duck)


def set_volumes(general_pct, music_pct):
    """Aplica los volúmenes del menú de opciones (0-100 cada uno)."""
    global _general, _music
    _general = _clamp_pct(general_pct)
    _music = _clamp_pct(music_pct)
    if not _enabled:
        return
    for sound in _sfx.values():
        sound.set_volume(_general)
    _apply_music_volume()


def set_music_duck(active):
    """Atenúa la música (pausa) sin detenerla."""
    global _duck
    _duck = DUCK_FACTOR if active else 1.0
    _apply_music_volume()


def play_music(*candidates, loop=True):
    """Reproduce la primera pista disponible de la lista de candidatas.

    Permite fallbacks: play_music("boss", "combat") usa boss.ogg si existe y si
    no, combat.ogg. Si la pista pedida ya está sonando, no hace nada. Si no hay
    ninguna candidata disponible, la música actual se desvanece hasta el silencio.
    """
    global _current_track
    if not _enabled:
        return
    chosen_name, chosen_path = None, None
    for name in candidates:
        path = _find_file(MUSIC_DIR, name)
        if path:
            chosen_name, chosen_path = name, path
            break

    if chosen_name is None:
        if _current_track is not None:
            pygame.mixer.music.fadeout(MUSIC_FADE_MS)
            _current_track = None
        _report_missing("música: " + "/".join(candidates))
        return

    if chosen_name == _current_track and pygame.mixer.music.get_busy():
        return
    try:
        pygame.mixer.music.load(chosen_path)
        _apply_music_volume()
        pygame.mixer.music.play(-1 if loop else 0, fade_ms=MUSIC_FADE_MS)
        _current_track = chosen_name
    except pygame.error as e:
        print(f"No se pudo reproducir la música '{chosen_path}': {e}")
        _current_track = None


def stop_music(fade_ms=MUSIC_FADE_MS):
    global _current_track
    if _enabled:
        pygame.mixer.music.fadeout(fade_ms)
    _current_track = None


def play_sfx(name):
    """Reproduce un efecto del banco; silencioso si no existe el archivo."""
    if not _enabled:
        return
    sound = _sfx.get(name)
    if sound is None:
        _report_missing("efecto: " + name)
        return
    now = pygame.time.get_ticks()
    if now - _last_sfx_ms.get(name, -SFX_MIN_INTERVAL_MS) < SFX_MIN_INTERVAL_MS:
        return
    _last_sfx_ms[name] = now
    sound.play()


def _report_missing(key):
    if key not in _missing_reported:
        _missing_reported.add(key)
        print(f"[audio] Archivo no encontrado ({key}); se omite.")
