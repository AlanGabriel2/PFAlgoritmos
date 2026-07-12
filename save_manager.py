import json
import os
import tempfile

SAVE_DIR = "saves"


def _atomic_write_json(path, data):
    """Escritura atómica: si el juego se cierra a media escritura, el archivo
    anterior queda intacto (se escribe a un temporal y luego se reemplaza)."""
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

GLOBAL_SAVE = os.path.join(SAVE_DIR, "global_save.json")

DEFAULT_GLOBAL_SAVE = {
    "bestiary_unlocks": ["BUG", "CODIGO SPAGHETTI", "MEMORY LEAK", "EL RELOJ (DEADLINE)"],
    "volume": 100,
    "music_volume": 100,
    "resolution": [1280, 720],
    "fullscreen": True,
    "aspect_mode": "fit",
    "fps_limit": 60,
    "tutorial_completed": False,
    "gamepad_rumble": True,
    "gamepad_deadzone": "media"
}

VALID_DEADZONES = ("baja", "media", "alta")

def _default_global_save():
    data = DEFAULT_GLOBAL_SAVE.copy()
    data["bestiary_unlocks"] = list(DEFAULT_GLOBAL_SAVE["bestiary_unlocks"])
    return data

def _normalize_percent(value, fallback=100):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if 0 <= parsed <= 1:
        parsed *= 100
    return max(0, min(100, int(round(parsed))))

def load_global_save():
    data = None
    if os.path.exists(GLOBAL_SAVE):
        try:
            with open(GLOBAL_SAVE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            data = None

    merged = _default_global_save()
    if isinstance(data, dict):
        merged.update(data)

    if not isinstance(merged.get("bestiary_unlocks"), list):
        merged["bestiary_unlocks"] = list(DEFAULT_GLOBAL_SAVE["bestiary_unlocks"])
    merged["volume"] = _normalize_percent(merged.get("volume"), DEFAULT_GLOBAL_SAVE["volume"])
    merged["music_volume"] = _normalize_percent(merged.get("music_volume"), DEFAULT_GLOBAL_SAVE["music_volume"])
    merged["gamepad_rumble"] = bool(merged.get("gamepad_rumble", True))
    if merged.get("gamepad_deadzone") not in VALID_DEADZONES:
        merged["gamepad_deadzone"] = DEFAULT_GLOBAL_SAVE["gamepad_deadzone"]
    return merged

def save_global_save(data):
    _atomic_write_json(GLOBAL_SAVE, data)

def get_slot_path(slot_index):
    return os.path.join(SAVE_DIR, f"slot_{slot_index}.json")

def has_save(slot_index):
    return os.path.exists(get_slot_path(slot_index))

def delete_save(slot_index):
    if has_save(slot_index):
        os.remove(get_slot_path(slot_index))

def save_game(slot_index, engine, semester_counter, energy, max_energy, camera_x, camera_y):
    data = {
        "semester_counter": semester_counter,
        "energy": energy,
        "max_energy": max_energy,
        "camera_x": camera_x,
        "camera_y": camera_y,
        "nodes_state": engine.state
    }
    _atomic_write_json(get_slot_path(slot_index), data)

def load_game(slot_index):
    if has_save(slot_index):
        try:
            with open(get_slot_path(slot_index), "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None
    return None

def get_latest_slot():
    # Returns the slot with the most recent modification time
    latest_slot = -1
    latest_time = 0
    for i in range(1, 4):
        if has_save(i):
            mtime = os.path.getmtime(get_slot_path(i))
            if mtime > latest_time:
                latest_time = mtime
                latest_slot = i
    return latest_slot if latest_slot != -1 else 1
