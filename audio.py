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

MUSIC_FADE_OUT_MS = 80
MUSIC_FADE_IN_MS = 100
SFX_MIN_INTERVAL_MS = 45   # evita que un mismo efecto se apile y sature en un frame
DUCK_FACTOR = 0.35         # atenuación de la música durante la pausa

# Ganancia relativa por efecto (1.0 = volumen general). Para nivelar a oído
# efectos de packs distintos sin editar los archivos.
SFX_GAIN = {
    "hit": 0.8,        # suena en cada bala conectada: mejor discreto
    "shoot": 0.55,     # dispara cada 0.25 s: es el efecto más frecuente del juego
    "enemy_shoot": 0.45,
    "miniboss_jump": 0.75,
    "miniboss_land": 0.85,
    "missile_charge": 0.65,
    "missile_launch": 0.70,
    "missile_impact": 0.90,
    "fire_ignite": 0.65,
    "boss_phase2_voice": 1.0,
}

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
    for name, sound in _sfx.items():
        sound.set_volume(_general * SFX_GAIN.get(name, 1.0))
    _apply_music_volume()


def set_music_duck(active):
    """Atenúa la música (pausa) sin detenerla."""
    global _duck
    _duck = DUCK_FACTOR if active else 1.0
    _apply_music_volume()


def _start_music(name, path, loop):
    global _current_track
    try:
        pygame.mixer.music.load(path)
        _apply_music_volume()
        pygame.mixer.music.play(-1 if loop else 0, fade_ms=MUSIC_FADE_IN_MS)
        _current_track = name
    except pygame.error as e:
        print(f"No se pudo reproducir la música '{path}': {e}")
        _current_track = None


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
            pygame.mixer.music.fadeout(MUSIC_FADE_OUT_MS)
            _current_track = None
        _report_missing("música: " + "/".join(candidates))
        return

    if chosen_name == _current_track and pygame.mixer.music.get_busy():
        return
    _start_music(chosen_name, chosen_path, loop)


def stop_music(fade_ms=MUSIC_FADE_OUT_MS):
    global _current_track
    if _enabled:
        pygame.mixer.music.fadeout(fade_ms)
    _current_track = None


def stop_all_sfx(fade_ms=180):
    """Desvanece efectos activos sin detener la música en streaming."""
    if _enabled:
        pygame.mixer.fadeout(max(0, int(fade_ms)))


def play_sfx(*names):
    """Reproduce el primer efecto disponible de la lista; silencioso si no hay ninguno.

    Acepta fallbacks igual que play_music: play_sfx("enemy_die_bug", "enemy_die")
    usa el efecto específico si existe y si no, el genérico.
    """
    if not _enabled or not names:
        return
    chosen, sound = None, None
    for name in names:
        sound = _sfx.get(name)
        if sound is not None:
            chosen = name
            break
    if sound is None:
        _report_missing("efecto: " + "/".join(names))
        return
    now = pygame.time.get_ticks()
    if now - _last_sfx_ms.get(chosen, -SFX_MIN_INTERVAL_MS) < SFX_MIN_INTERVAL_MS:
        return
    _last_sfx_ms[chosen] = now
    sound.play()


def _report_missing(key):
    if key not in _missing_reported:
        _missing_reported.add(key)
        print(f"[audio] Archivo no encontrado ({key}); se omite.")
