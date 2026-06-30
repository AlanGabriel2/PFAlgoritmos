import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Imports
if 'import save_manager' not in code:
    code = code.replace('import random\n', 'import random\nimport save_manager\n')

# 2. Main loop init
if 'save_mgr = save_manager' not in code:
    code = code.replace('def main():\n', 'def main():\n    save_mgr = save_manager\n    global_data = save_mgr.load_global_save()\n')
    
    code = code.replace('game_state = "TITLE_SCREEN"', 'game_state = "DISCLAIMER_SCREEN"')
    
    code = code.replace('title_screen = TitleScreen(WIDTH, HEIGHT, font_title, font_md)', 
        'title_screen = TitleScreen(WIDTH, HEIGHT, font_title, font_md)\n    disclaimer_screen = DisclaimerScreen(WIDTH, HEIGHT, font_lg, font_md)\n    play_sub_menu = PlaySubMenu(WIDTH, HEIGHT, font_lg, font_md)\n    current_slot_mode = None\n    slot_select_menu = None\n    save_indicator_timer = 0\n    current_slot = 1\n')
    
    code = code.replace('bestiary_menu = BestiaryMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm)',
        'bestiary_menu = BestiaryMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm, save_mgr)')
        
# 3. Main event loop (DISCLAIMER)
if 'if game_state == "TITLE_SCREEN":' in code and 'DISCLAIMER_SCREEN' not in code:
    code = code.replace('if game_state == "TITLE_SCREEN":', 
        '''if game_state == "DISCLAIMER_SCREEN":
                action = disclaimer_screen.handle_event(event)
                if action == "NEXT":
                    trigger_transition("TITLE_SCREEN", "FADE", 0.05)
            elif game_state == "TITLE_SCREEN":''')

# 4. Main event loop (Jugar -> PLAY_SUB_MENU)
if 'elif action == "Jugar":\n                    trigger_transition("MAP", "CIRCLE", 0.04)' in code:
    code = code.replace('elif action == "Jugar":\n                    trigger_transition("MAP", "CIRCLE", 0.04)',
        'elif action == "Jugar":\n                    trigger_transition("PLAY_SUB_MENU", "SLIDE_LEFT", 0.05)')

# 5. Play sub menus event loops
if 'elif game_state == "PAUSE":' in code and 'PLAY_SUB_MENU' not in code:
    submenus = '''elif game_state == "PLAY_SUB_MENU":
                action = play_sub_menu.handle_event(event)
                if action == "Regresar":
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
                elif action == "Continuar Partida":
                    slot = save_mgr.get_latest_slot()
                    data = save_mgr.load_game(slot)
                    if data:
                        current_slot = slot
                        semester_counter = data["semester_counter"]
                        energy = data["energy"]
                        max_energy = data["max_energy"]
                        camera_x = data["camera_x"]
                        camera_y = data["camera_y"]
                        engine.state = data["nodes_state"]
                        trigger_transition("MAP", "CIRCLE", 0.04)
                    else:
                        main_menu.notification = "No hay partida guardada."
                        main_menu.notification_timer = 180
                        trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
                elif action == "Nueva Partida":
                    current_slot_mode = "NUEVA"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
                elif action == "Cargar Partida":
                    current_slot_mode = "CARGAR"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
            elif game_state == "SLOT_SELECT":
                action = slot_select_menu.handle_event(event)
                if action == "Regresar":
                    trigger_transition("PLAY_SUB_MENU", "SLIDE_RIGHT", 0.05)
                elif action and action.startswith("Slot"):
                    slot = int(action.split(" ")[1])
                    if current_slot_mode == "NUEVA":
                        current_slot = slot
                        engine = DagEngine()
                        map_gen = MapGenerator(engine)
                        semester_counter = 1
                        energy = 6
                        max_energy = 6
                        camera_x, camera_y = 0, 0
                        trigger_transition("MAP", "CIRCLE", 0.04)
                    elif current_slot_mode == "CARGAR":
                        data = save_mgr.load_game(slot)
                        if data:
                            current_slot = slot
                            semester_counter = data["semester_counter"]
                            energy = data["energy"]
                            max_energy = data["max_energy"]
                            camera_x = data["camera_x"]
                            camera_y = data["camera_y"]
                            engine.state = data["nodes_state"]
                            trigger_transition("MAP", "CIRCLE", 0.04)
            elif game_state == "PAUSE":'''
    code = code.replace('elif game_state == "PAUSE":', submenus)

# 6. Save in combat
if '# AUTOSAVE' not in code:
    combat_win = '''if current_room == "TIP10TEMTT1":'''
    new_combat_win = '''# AUTOSAVE
                save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                save_indicator_timer = 120
                
                if current_room == "TIP10TEMTT1":
                    global_data["bestiary_unlocks"] = list(set(global_data.get("bestiary_unlocks", []) + ["MEGA BOSS (TITULACION)"]))
                    save_mgr.save_global_save(global_data)
                    bestiary_menu.unlocked_names = global_data["bestiary_unlocks"]
'''
    code = code.replace(combat_win, new_combat_win)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)
