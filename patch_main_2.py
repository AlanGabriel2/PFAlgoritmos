import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 7. Draw WIN state return logic
if 'save_mgr.delete_save(current_slot)' not in code:
    win_input = '''elif game_state == "WIN":
            win_ts = font_lg.render(f"¡PROYECTO DE TITULACION APROBADO! ¡HAS GANADO!", False, (0, 255, 0))'''
    new_win_input = '''elif game_state == "WIN":
            if event.type == pygame.KEYDOWN:
                save_mgr.delete_save(current_slot)
                main_menu.notification = "¡Nuevo enemigo desbloqueado! La experiencia es rejugable."
                main_menu.notification_timer = 300
                trigger_transition("MAIN_MENU", "FADE", 0.05)
                
            win_ts = font_lg.render(f"¡PROYECTO DE TITULACION APROBADO! ¡HAS GANADO!", False, (0, 255, 0))'''
    code = code.replace(win_input, new_win_input)
    
    # And change text in WIN state
    old_text = '''restart_ts = font_md.render("Presiona 'R' para jugar de nuevo.", False, TEXT_COLOR)'''
    new_text = '''restart_ts = font_md.render("Presiona cualquier tecla para regresar al menu.", False, TEXT_COLOR)'''
    code = code.replace(old_text, new_text)

# 8. Draw new screens
if 'elif game_state == "PLAY_SUB_MENU":' not in code:
    draw_pause = '''if game_state == "PAUSE":'''
    new_draw_pause = '''if game_state == "DISCLAIMER_SCREEN":
            disclaimer_screen.draw(screen)
        elif game_state == "PLAY_SUB_MENU":
            play_sub_menu.draw(screen)
        elif game_state == "SLOT_SELECT":
            slot_select_menu.draw(screen)
        elif game_state == "PAUSE":'''
    code = code.replace(draw_pause, new_draw_pause)

# 9. Draw save indicator
if 'save_indicator_timer -= 1' not in code:
    draw_ui = '''if trans_state["active"]:'''
    new_draw_ui = '''if save_indicator_timer > 0:
            save_indicator_timer -= 1
            pygame.draw.circle(screen, (100, 255, 100), (WIDTH - 40, HEIGHT - 40), 15, 3)
            arc_angle = (save_indicator_timer * 10) % 360
            import math
            pygame.draw.arc(screen, (255, 255, 255), (WIDTH - 55, HEIGHT - 55, 30, 30), math.radians(arc_angle), math.radians(arc_angle+90), 4)
            s_text = font_sm.render("Guardando...", True, (200, 255, 200))
            screen.blit(s_text, (WIDTH - 40 - s_text.get_width()//2, HEIGHT - 20))
            
        if trans_state["active"]:'''
    code = code.replace(draw_ui, new_draw_ui)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)
