import json
import os

SAVE_DIR = "saves"

if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

GLOBAL_SAVE = os.path.join(SAVE_DIR, "global_save.json")

def load_global_save():
    if os.path.exists(GLOBAL_SAVE):
        with open(GLOBAL_SAVE, "r") as f:
            try:
                return json.load(f)
            except:
                pass
    # Defaults
    return {
        "bestiary_unlocks": ["BUG", "CODIGO SPAGHETTI", "MEMORY LEAK", "EL RELOJ (DEADLINE)"],
        "volume": 0.5,
        "resolution": 0 # 0=1280x720, 1=Full Screen
    }

def save_global_save(data):
    with open(GLOBAL_SAVE, "w") as f:
        json.dump(data, f, indent=4)

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
    with open(get_slot_path(slot_index), "w") as f:
        json.dump(data, f, indent=4)

def load_game(slot_index):
    if has_save(slot_index):
        with open(get_slot_path(slot_index), "r") as f:
            try:
                return json.load(f)
            except:
                return None
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
