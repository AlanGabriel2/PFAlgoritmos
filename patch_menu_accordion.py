import re

def patch_menu():
    with open('menu.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. MainMenu init
    if 'self.jugar_expanded = False' not in code:
        code = code.replace(
            'self.options = ["Jugar", "Tutorial", "Opciones", "Salir"]\n        self.selected_index = 0',
            'self.options = ["Jugar", "Tutorial", "Opciones", "Salir"]\n        self.jugar_expanded = False\n        self.selected_index = 0'
        )

    # 2. current_options property
    if 'def current_options(self):' not in code:
        prop_str = """
    @property
    def current_options(self):
        opts = []
        for opt in self.options:
            opts.append(opt)
            if opt == "Jugar" and self.jugar_expanded:
                opts.extend(["  Continuar Partida", "  Nueva Partida", "  Cargar Partida"])
        return opts

    def unlock_bestiary"""
        code = code.replace('    def unlock_bestiary', prop_str)

    # 3. handle_event
    old_handle = """    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.options[self.selected_index]
        return None"""
    
    new_handle = """    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            opts = self.current_options
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(opts)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(opts)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                selection = opts[self.selected_index]
                if selection == "Jugar":
                    self.jugar_expanded = not self.jugar_expanded
                    if not self.jugar_expanded and self.selected_index >= len(self.current_options):
                        self.selected_index = self.current_options.index("Jugar")
                return selection.strip()
        return None"""
    code = code.replace(old_handle, new_handle)

    # 4. draw loop options
    old_draw_loop = """        for i, option in enumerate(self.options):
            if i == self.selected_index:
                color = (255, 255, 255)
                text = self.font_md.render("> " + option + " <", True, color)
                shadow = self.font_md.render("> " + option + " <", True, (150, 0, 150))
                rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 50))
                surface.blit(shadow, (rect.x + 3, rect.y + 3))
            else:
                color = (180, 130, 210) # Pale purple
                text = self.font_md.render(option, True, color)
                rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 50))
                
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 50))
                
            surface.blit(text, rect)"""

    new_draw_loop = """        opts = self.current_options
        for i, option in enumerate(opts):
            if i == self.selected_index:
                color = (255, 255, 255)
                text = self.font_md.render("> " + option + " <", True, color)
                shadow = self.font_md.render("> " + option + " <", True, (150, 0, 150))
            else:
                color = (180, 130, 210)
                if option.startswith("  "):
                    color = (200, 200, 200)
                text = self.font_md.render(option, True, color)
                
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 45))
            if i == self.selected_index:
                surface.blit(shadow, (rect.x + 3, rect.y + 3))
            surface.blit(text, rect)"""
    code = code.replace(old_draw_loop, new_draw_loop)

    with open('menu.py', 'w', encoding='utf-8') as f:
        f.write(code)

def patch_main():
    with open('main.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. MainMenu events in main
    old_main_menu_events = """            elif game_state == "MAIN_MENU":
                action = main_menu.handle_event(event)
                if action == "Jugar":
                    trigger_transition("PLAY_SUB_MENU", "SLIDE_LEFT", 0.05)
                elif action == "Tutorial":
                    tutorial_state.reset()
                    trigger_transition("TUTORIAL", "SLIDE_LEFT", 0.05)
                elif action == "Bestiario":
                    trigger_transition("BESTIARY", "PIXELATE", 0.03)
                elif action == "Opciones":
                    trigger_transition("OPTIONS", "SLIDE_LEFT", 0.05)
                elif action == "Salir":
                    running = False
            elif game_state == "PLAY_SUB_MENU":
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
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)"""
    
    new_main_menu_events = """            elif game_state == "MAIN_MENU":
                action = main_menu.handle_event(event)
                if action == "Continuar Partida":
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
                elif action == "Nueva Partida":
                    current_slot_mode = "NUEVA"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
                elif action == "Cargar Partida":
                    current_slot_mode = "CARGAR"
                    slot_select_menu = SlotSelectMenu(WIDTH, HEIGHT, font_lg, font_md, save_mgr, current_slot_mode)
                    trigger_transition("SLOT_SELECT", "SLIDE_LEFT", 0.05)
                elif action == "Tutorial":
                    tutorial_state.reset()
                    trigger_transition("TUTORIAL", "SLIDE_LEFT", 0.05)
                elif action == "Bestiario":
                    trigger_transition("BESTIARY", "PIXELATE", 0.03)
                elif action == "Opciones":
                    trigger_transition("OPTIONS", "SLIDE_LEFT", 0.05)
                elif action == "Salir":
                    running = False"""
    code = code.replace(old_main_menu_events, new_main_menu_events)

    # 2. Fix SLOT_SELECT Regresar
    if 'trigger_transition("PLAY_SUB_MENU", "SLIDE_RIGHT", 0.05)' in code:
        code = code.replace('trigger_transition("PLAY_SUB_MENU", "SLIDE_RIGHT", 0.05)',
                            'trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)')

    # 3. Remove PLAY_SUB_MENU from drawing logic
    if 'elif game_state in ["MAIN_MENU", "PLAY_SUB_MENU", "SLOT_SELECT"]:' in code:
        code = code.replace(
            'elif game_state in ["MAIN_MENU", "PLAY_SUB_MENU", "SLOT_SELECT"]:',
            'elif game_state in ["MAIN_MENU", "SLOT_SELECT"]:'
        ).replace(
            '            if game_state == "PLAY_SUB_MENU":\n                play_sub_menu.draw(screen)\n            elif game_state == "SLOT_SELECT":\n                slot_select_menu.draw(screen)',
            '            if game_state == "SLOT_SELECT":\n                slot_select_menu.draw(screen)'
        )

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(code)

if __name__ == "__main__":
    patch_menu()
    patch_main()
    print("Done")
