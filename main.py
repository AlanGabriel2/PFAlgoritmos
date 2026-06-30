import pygame
import sys
import random
import save_manager
import math
from transitions import render_transition

from dag_engine import DagEngine, NodeState
from map_generator import MapGenerator
from player import Player, init_player_assets
from enemy import BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy, MiniBoss, Boss
from menu import MainMenu, BestiaryMenu, PauseMenu, TitleScreen, OptionsMenu, DisclaimerScreen, PlaySubMenu, SlotSelectMenu
from tutorial import TutorialState

pygame.init()

# Configurar Pantalla
WIDTH, HEIGHT = 1024, 768
# Crear la ventana real y la superficie virtual para el juego
real_screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
screen = pygame.Surface((WIDTH, HEIGHT))
pygame.display.set_caption("Mega-Calabozo DAG")

# Inicializar assets del jugador
init_player_assets()

MAP_BG_IMG = None
try:
    MAP_BG_IMG = pygame.image.load("assets/images/backgrounds/map_bg.png").convert()
    MAP_BG_IMG = pygame.transform.scale(MAP_BG_IMG, (WIDTH, HEIGHT))
except Exception as e:
    print("No se pudo cargar el fondo del mapa:", e)

FLOOR_IMG = None
try:
    FLOOR_IMG = pygame.image.load("assets/images/backgrounds/floor_tile.png").convert()
    # Escalar para llenar la pantalla de combate
    FLOOR_IMG = pygame.transform.scale(FLOOR_IMG, (WIDTH, HEIGHT))
except Exception as e:
    print("No se pudo cargar el suelo:", e)

SAVE_ICON_IMG = None
try:
    SAVE_ICON_IMG = pygame.image.load("assets/images/ui/save.png").convert_alpha()
    # Forzar un aspecto cuadrado (40x40) para evitar que se vea muy ancha
    SAVE_ICON_IMG = pygame.transform.scale(SAVE_ICON_IMG, (40, 40))
except Exception as e:
    print("No se pudo cargar el icono de guardado:", e)

HEART_FRAMES = []
try:
    heart_sheet = pygame.image.load("assets/images/ui/vida_heart.png").convert_alpha()
    # La nueva imagen tiene 5 fotogramas en 1 fila
    hw = heart_sheet.get_width() // 5
    hh = heart_sheet.get_height() // 1
    
    for c in range(5):
        rect = pygame.Rect(c * hw, 0, hw, hh)
        frame = pygame.Surface((hw, hh), pygame.SRCALPHA)
        frame.blit(heart_sheet, (0, 0), rect)
        
        bbox = frame.get_bounding_rect()
        if bbox.width > 0 and bbox.height > 0:
            # Crear un cuadrado perfecto (400x400) para centrar y evitar deformación
            square = pygame.Surface((400, 400), pygame.SRCALPHA)
            offset_x = (400 - bbox.width) // 2
            offset_y = (400 - bbox.height) // 2
            square.blit(frame, (offset_x, offset_y), bbox)
            
            cropped = pygame.transform.scale(square, (28, 28)) # Tamaño reducido
            HEART_FRAMES.append(cropped)
except Exception as e:
    print("No se pudo cargar la animacion del corazon:", e)

# Fuentes
try:
    font_sm = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 20)
    font_md = pygame.font.Font("assets/fonts/VT323-Regular.ttf", 28)
    font_lg = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 56)
    font_title = pygame.font.Font("assets/packs/webfontkit-BoldPixels/boldpixels.ttf", 100)
except:
    font_sm = pygame.font.SysFont("Arial", 16)
    font_md = pygame.font.SysFont("Arial", 24)
    font_lg = pygame.font.SysFont("Arial", 48)
    font_title = pygame.font.SysFont("Arial", 80)

# Colores
BG_COLOR = (20, 20, 25)
TEXT_COLOR = (255, 255, 255)

import os

SEMESTER_BGS = {}

def get_semester_bg(room_id, width, height):
    if not room_id or len(room_id) < 5:
        return FLOOR_IMG
        
    try:
        semester_num = int(room_id[3:5])
    except:
        return FLOOR_IMG
        
    if semester_num in SEMESTER_BGS:
        return SEMESTER_BGS[semester_num]
        
    # Intentar cargar la imagen (probando .png y .jpg)
    loaded_img = None
    base_path = f"assets/images/backgrounds/s{semester_num}"
    
    if os.path.exists(f"{base_path}.png"):
        loaded_img = pygame.image.load(f"{base_path}.png").convert()
    elif os.path.exists(f"{base_path}.jpg"):
        loaded_img = pygame.image.load(f"{base_path}.jpg").convert()
        
    if loaded_img:
        scaled_img = pygame.transform.scale(loaded_img, (width, height))
        SEMESTER_BGS[semester_num] = scaled_img
        return scaled_img
        
    return FLOOR_IMG

ARENA_W = int(WIDTH * 1.5)
ARENA_H = int(HEIGHT * 1.5)

def draw_floor(surface, room_id, offset_x=0, offset_y=0):
    bg = get_semester_bg(room_id, ARENA_W, ARENA_H)
    if bg:
        surface.blit(bg, (offset_x, offset_y))
    else:
        pygame.draw.rect(surface, (40, 30, 30), (0, 0, WIDTH, HEIGHT))

def main():
    save_mgr = save_manager
    global_data = save_mgr.load_global_save()
    global screen, real_screen
    clock = pygame.time.Clock()
    
    # Inicializar Sistemas del Juego
    engine = DagEngine()
    map_gen = MapGenerator(engine)
    par_score = engine.get_par_score()
    
    # Variables de Estado del Juego
    game_state = "DISCLAIMER_SCREEN" # TITLE_SCREEN, MAIN_MENU, TUTORIAL, BESTIARY, MAP, COMBAT, WIN, GAME_OVER
    semester_counter = 1
    max_energy = 6
    energy = 6
    rest_animation_timer = 0
    
    title_screen = TitleScreen(WIDTH, HEIGHT, font_title, font_md)
    disclaimer_screen = DisclaimerScreen(WIDTH, HEIGHT, font_lg, font_md)
    play_sub_menu = PlaySubMenu(WIDTH, HEIGHT, font_lg, font_md)
    current_slot_mode = None
    slot_select_menu = None
    save_indicator_timer = 0
    current_slot = 1
    main_menu = MainMenu(WIDTH, HEIGHT, font_lg, font_md)
    bestiary_menu = BestiaryMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm, save_mgr)
    tutorial_state = TutorialState(WIDTH, HEIGHT, font_lg, font_md, font_sm)
    pause_menu = PauseMenu(WIDTH, HEIGHT, font_lg, font_md)
    options_menu = OptionsMenu(WIDTH, HEIGHT, font_lg, font_md, font_sm, global_data)
    previous_state = None
    
    # Variables de la Cámara del Mapa
    camera_x, camera_y = 0, 0
    dragging = False
    last_mouse_pos = (0, 0)
    selected_node = None
    
    current_room = None
    combat_player = None
    enemies = []
    
    combat_cam_x, combat_cam_y = 0, 0
    
    current_wave = 1
    max_waves = 1
    wave_timer = 0
    
    floating_texts = [] # Lista para almacenar los números de daño flotantes
    
    trans_state = {
        "active": False,
        "progress": 0.0,
        "speed": 0.04,
        "type": "FADE",
        "old_surf": None
    }
    
    def trigger_transition(target, t_type="FADE", speed=0.04):
        nonlocal game_state
        trans_state["active"] = True
        trans_state["progress"] = 0.0
        trans_state["speed"] = speed
        trans_state["type"] = t_type
        trans_state["old_surf"] = screen.copy()
        game_state = target

    
    running = True
    while running:
        # Escalar coordenadas del ratón
        window_w, window_h = real_screen.get_size()
        scale_x = WIDTH / window_w
        scale_y = HEIGHT / window_h
        raw_mx, raw_my = pygame.mouse.get_pos()
        mouse_x = int(raw_mx * scale_x)
        mouse_y = int(raw_my * scale_y)
        
        keys = pygame.key.get_pressed()
        
        # Selección por defecto
        if game_state == "MAP" and (selected_node is None or engine.state[selected_node] == NodeState.CLEANED):
            unlocked = [n for n in engine.nodes if engine.state[n] == NodeState.UNLOCKED]
            if unlocked:
                selected_node = unlocked[0]
                if selected_node in map_gen.rooms:
                    camera_x = WIDTH//2 - map_gen.rooms[selected_node].rect.centerx
                    camera_y = HEIGHT//2 - map_gen.rooms[selected_node].rect.centery

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
            if trans_state["active"]:
                continue
                
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                pygame.display.toggle_fullscreen()
                
            if game_state == "TITLE_SCREEN":
                action = title_screen.handle_event(event)
                if action == "START":
                    main_menu.time = 0
                    trigger_transition("MAIN_MENU", "FADE", 0.03)
                    
            elif game_state == "MAIN_MENU":
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
                    running = False
            elif game_state == "SLOT_SELECT":
                action = slot_select_menu.handle_event(event)
                if action == "Regresar":
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
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
            elif game_state == "PAUSE":
                action = pause_menu.handle_event(event)
                if action == "Continuar":
                    trigger_transition(previous_state, "FADE", 0.08)
                elif action == "Guardar y Salir al menú principal":
                    save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
            elif game_state == "BESTIARY":
                action = bestiary_menu.handle_event(event)
                if action == "BACK":
                    trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
            elif game_state == "TUTORIAL":
                action = tutorial_state.handle_event(event, mouse_x, mouse_y)
                if action == "GO_TO_BESTIARY":
                    main_menu.unlock_bestiary()
                    trigger_transition("BESTIARY", "PIXELATE", 0.03)
                    
            elif game_state == "OPTIONS":
                action = options_menu.handle_event(event)
                if action:
                    if action["action"] == "BACK":
                        trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
                    elif action["action"] == "APPLY":
                        res = action["res"]
                        fullscreen = action["fullscreen"]
                        gen_vol = action["gen_vol"]
                        
                        global_data["resolution"] = res
                        global_data["fullscreen"] = fullscreen
                        global_data["volume"] = gen_vol
                        save_mgr.save_global_save(global_data)
                        
                        flags = 0
                        if fullscreen:
                            flags |= pygame.FULLSCREEN
                            real_screen = pygame.display.set_mode((0, 0), flags)
                        else:
                            real_screen = pygame.display.set_mode(res, flags)
                        # We don't change internal WIDTH/HEIGHT so game logic remains at 1024x768
                        trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)
            elif game_state == "MAP":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    previous_state = "MAP"
                    trigger_transition("PAUSE", "FADE", 0.08)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 3: # Clic derecho para arrastrar
                        dragging = True
                        last_mouse_pos = event.pos
                    elif event.button == 1: # Clic izquierdo para seleccionar habitación
                        clicked_node = map_gen.get_room_at(mouse_x, mouse_y, camera_x, camera_y)
                        if clicked_node and engine.state[clicked_node] == NodeState.UNLOCKED:
                            selected_node = clicked_node # La seleccionamos y entramos
                            if energy > 0:
                                current_room = clicked_node
                                trigger_transition("COMBAT", "CIRCLE", 0.03)
                                energy -= 1
                                combat_player = Player(ARENA_W//2, ARENA_H//2)
                                enemy_types = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]
                                
                                current_wave = 1
                                max_waves = 1 + (semester_counter // 2)
                                wave_timer = 300 # 5 segundos a 60fps
                                
                                enemies = [random.choice(enemy_types)(random.randint(100, ARENA_W-100), random.randint(100, ARENA_H-100)) for _ in range(random.randint(3, 6))]
                                if current_room == "TIP10TEMTT1":
                                    enemies.append(Boss(ARENA_W//2, 100))
                                if current_room in engine.critical_nodes and current_room != "TIP10TEMTT1" and max_waves == 1:
                                    enemies.append(MiniBoss(random.randint(200, ARENA_W-200), random.randint(200, ARENA_H-200)))
                            else:
                                print("¡No hay suficiente energía! Descansa para avanzar de semestre.")
                                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3:
                        dragging = False
                        
                elif event.type == pygame.MOUSEMOTION:
                    if dragging:
                        dx, dy = event.pos[0] - last_mouse_pos[0], event.pos[1] - last_mouse_pos[1]
                        camera_x += dx
                        camera_y += dy
                        last_mouse_pos = event.pos
                        
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r or event.key == pygame.K_SPACE: # Descansar / Avanzar Semestre
                        energy = max_energy
                        semester_counter += 1
                        engine.update_unlocks()
                        rest_animation_timer = 90 # 1.5 seconds animation
                        
                    elif event.key == pygame.K_RETURN: # Entrar con Enter
                        if selected_node and engine.state[selected_node] == NodeState.UNLOCKED:
                            if energy > 0:
                                current_room = selected_node
                                trigger_transition("COMBAT", "CIRCLE", 0.03)
                                energy -= 1
                                combat_player = Player(ARENA_W//2, ARENA_H//2)
                                enemy_types = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]
                                
                                current_wave = 1
                                max_waves = 1 + (semester_counter // 2)
                                wave_timer = 300
                                
                                enemies = [random.choice(enemy_types)(random.randint(100, ARENA_W-100), random.randint(100, ARENA_H-100)) for _ in range(random.randint(3, 6))]
                                if current_room == "TIP10TEMTT1":
                                    enemies.append(Boss(ARENA_W//2, 100))
                                if current_room in engine.critical_nodes and current_room != "TIP10TEMTT1" and max_waves == 1:
                                    enemies.append(MiniBoss(random.randint(200, ARENA_W-200), random.randint(200, ARENA_H-200)))
                            else:
                                print("¡No hay suficiente energía! Descansa para avanzar de semestre.")
                                
                    elif event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                        if selected_node and selected_node in map_gen.rooms:
                            current_rect = map_gen.rooms[selected_node].rect
                            best_dist = float('inf')
                            best_node = None
                            for n, r in map_gen.rooms.items():
                                if n == selected_node or engine.state[n] == NodeState.CLEANED: continue
                                dx_ = r.rect.centerx - current_rect.centerx
                                dy_ = r.rect.centery - current_rect.centery
                                dist = math.hypot(dx_, dy_)
                                
                                valid = False
                                if event.key == pygame.K_UP and dy_ < -abs(dx_): valid = True
                                elif event.key == pygame.K_DOWN and dy_ > abs(dx_): valid = True
                                elif event.key == pygame.K_LEFT and dx_ < -abs(dy_): valid = True
                                elif event.key == pygame.K_RIGHT and dx_ > abs(dy_): valid = True
                                
                                if valid and dist < best_dist:
                                    best_dist = dist
                                    best_node = n
                            if best_node:
                                selected_node = best_node
                                target_room = map_gen.rooms[selected_node]
                                camera_x = WIDTH//2 - target_room.rect.centerx
                                camera_y = HEIGHT//2 - target_room.rect.centery
                        
            elif game_state == "COMBAT":
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    previous_state = "COMBAT"
                    trigger_transition("PAUSE", "FADE", 0.08)
                # Disparar con el ratón
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    combat_player.shoot_angle(math.atan2((mouse_y - combat_cam_y) - combat_player.y, (mouse_x - combat_cam_x) - combat_player.x))
            elif game_state in ["WIN", "GAME_OVER"]:
                if event.type == pygame.KEYDOWN and (event.key == pygame.K_r or event.key == pygame.K_SPACE):
                    main()
                    return

        # Actualizaciones Continuas (teclas presionadas)
        if game_state == "DISCLAIMER_SCREEN":
            if disclaimer_screen.time > 200 and not trans_state["active"]:
                trigger_transition("TITLE_SCREEN", "FADE", 0.03)
        elif game_state == "TUTORIAL":
            tutorial_state.update(keys, WIDTH, HEIGHT)
        elif game_state == "COMBAT":
            # Disparar con flechas (soporta diagonales)
            dx, dy = 0, 0
            if keys[pygame.K_UP]: dy -= 1
            if keys[pygame.K_DOWN]: dy += 1
            if keys[pygame.K_LEFT]: dx -= 1
            if keys[pygame.K_RIGHT]: dx += 1
            
            if dx != 0 or dy != 0:
                combat_player.shoot_angle(math.atan2(dy, dx))
                
            # Mouse drag shooting
            if pygame.mouse.get_pressed()[0]:
                combat_player.shoot_angle(math.atan2((mouse_y - combat_cam_y) - combat_player.y, (mouse_x - combat_cam_x) - combat_player.x))
                
            combat_player.move(keys, ARENA_W, ARENA_H)
            combat_player.update_bullets(ARENA_W, ARENA_H)
            
            # Camera logic (smooth follow)
            target_cam_x = WIDTH // 2 - combat_player.x
            target_cam_y = HEIGHT // 2 - combat_player.y
            
            # Clamping camera to boundaries
            target_cam_x = min(0, max(-(ARENA_W - WIDTH), target_cam_x))
            target_cam_y = min(0, max(-(ARENA_H - HEIGHT), target_cam_y))
            
            combat_cam_x += (target_cam_x - combat_cam_x) * 0.1
            combat_cam_y += (target_cam_y - combat_cam_y) * 0.1
            
            for enemy in enemies:
                enemy.update(combat_player.x, combat_player.y, ARENA_W, ARENA_H)
                
                if isinstance(enemy, MiniBoss):
                    bestiary_menu.unlock("MINI BOSS (PARCIAL)")
                elif isinstance(enemy, Boss):
                    bestiary_menu.unlock("MEGA BOSS (TITULACIÓN)")
                
                # El jugador recibe daño por contacto
                if enemy.collides_with_player(combat_player) and enemy.attack_cooldown == 0:
                    combat_player.hp -= 20 if isinstance(enemy, (MiniBoss, Boss)) else 10
                    enemy.attack_cooldown = 45 if isinstance(enemy, (MiniBoss, Boss)) else 30
                    if combat_player.hp <= 0:
                        game_state = "MAP" # Expulsado al pasillo
                        print("¡Fuiste derrotado! La habitación sigue siendo hostil.")
                        
                # El jugador recibe daño por balas enemigas
                for b in enemy.bullets[:]:
                    dist = math.hypot(combat_player.x - b.x, combat_player.y - b.y)
                    if dist < (combat_player.radius + b.radius):
                        combat_player.hp -= 15
                        if b in enemy.bullets:
                            enemy.bullets.remove(b)
                        if combat_player.hp <= 0:
                            trigger_transition("MAP", "CIRCLE", 0.04)
                            print("¡Fuiste derrotado por un proyectil!")
            
            # Las balas golpean a los enemigos
            for b in combat_player.bullets[:]:
                for e in enemies[:]:
                    if e.collides_with_bullet(b):
                        damage = 10
                        e.hp -= damage
                        
                        # Generar texto flotante de daño
                        floating_texts.append({
                            "text": str(damage),
                            "x": e.x,
                            "y": e.y - 20,
                            "life": 40,
                            "color": (255, 50, 50)
                        })
                        
                        if b in combat_player.bullets:
                            combat_player.bullets.remove(b)
                        if e.hp <= 0:
                            enemies.remove(e)
            
            # Actualizar textos flotantes
            for ft in floating_texts[:]:
                ft["y"] -= 1.5  # Subir
                ft["life"] -= 1 # Desvanecerse
                if ft["life"] <= 0:
                    floating_texts.remove(ft)
            
            # Spawnear nuevas rondas
            if current_wave < max_waves:
                wave_timer -= 1
                if wave_timer <= 0:
                    current_wave += 1
                    wave_timer = 300 # Reset timer para la siguiente ola
                    
                    # Spawn desde la puerta (ARENA_W*0.85, ARENA_H*0.22)
                    door_x, door_y = int(ARENA_W * 0.85), int(ARENA_H * 0.22)
                    enemy_types = [BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy]
                    
                    for _ in range(random.randint(3, 5)):
                        ex = door_x + random.randint(-20, 20)
                        ey = door_y + random.randint(-20, 20)
                        enemies.append(random.choice(enemy_types)(ex, ey))
                        
                    if current_wave == max_waves and current_room in engine.critical_nodes and current_room != "TIP10TEMTT1":
                        enemies.append(MiniBoss(door_x, door_y))

            # Revisar si la habitación está limpia (solo si ya estamos en la última ronda)
            if current_wave == max_waves and not enemies:
                engine.clean_room(current_room)
                engine.update_unlocks()
                
                # AUTOSAVE
                save_mgr.save_game(current_slot, engine, semester_counter, energy, max_energy, camera_x, camera_y)
                save_indicator_timer = 120
                
                if current_room == "TIP10TEMTT1":
                    global_data["bestiary_unlocks"] = list(set(global_data.get("bestiary_unlocks", []) + ["MEGA BOSS (TITULACION)"]))
                    save_mgr.save_global_save(global_data)
                    bestiary_menu.unlocked_names = global_data["bestiary_unlocks"]

                    trigger_transition("WIN", "FADE", 0.02)
                else:
                    trigger_transition("MAP", "CIRCLE", 0.04)
                
        # Dibujado
        screen.fill(BG_COLOR)
        
        if game_state == "DISCLAIMER_SCREEN":
            disclaimer_screen.draw(screen)
        elif game_state == "TITLE_SCREEN":
            title_screen.draw(screen)
        elif game_state in ["MAIN_MENU", "SLOT_SELECT"]:
            main_menu.draw(screen, mouse_x, mouse_y)
            if game_state == "SLOT_SELECT":
                slot_select_menu.draw(screen)
        elif game_state == "OPTIONS":
            options_menu.draw(screen)
        elif game_state == "BESTIARY":
            bestiary_menu.draw(screen)
        elif game_state == "TUTORIAL":
            tutorial_state.draw(screen)
        elif game_state == "MAP" or (game_state == "PAUSE" and previous_state == "MAP"):
            if MAP_BG_IMG:
                screen.blit(MAP_BG_IMG, (0, 0))
                
            map_gen.draw(screen, font_sm, camera_x, camera_y)
            
            if selected_node and selected_node in map_gen.rooms:
                sel_rect = map_gen.rooms[selected_node].rect.copy()
                sel_rect.x += camera_x
                sel_rect.y += camera_y
                pygame.draw.rect(screen, (255, 255, 0), sel_rect, 4, border_radius=8)
                
                # Tooltip de Prerrequisitos
                reqs = engine.subjects[selected_node]['reqs']
                req_lines = [f"Materia: {engine.subjects[selected_node]['name']}", "Prerrequisitos:"]
                
                if selected_node == "TIP10TEMTT1":
                    cleaned_count = sum(1 for n in engine.nodes if engine.state[n] == NodeState.CLEANED)
                    total_req = len(engine.nodes) - 1
                    req_lines.append(f"- Completar todas las materias ({cleaned_count}/{total_req})")
                elif not reqs:
                    req_lines.append("- Ninguno")
                else:
                    for r in reqs:
                        req_lines.append(f"- {engine.subjects[r]['name']}")
                
                tt_surfaces = [font_sm.render(line, False, (255, 255, 255)) for line in req_lines]
                tt_surfaces[0] = font_sm.render(req_lines[0], False, (255, 255, 100)) # Highlight name
                
                max_w = max(s.get_width() for s in tt_surfaces)
                tt_h = sum(s.get_height() for s in tt_surfaces) + 10
                tt_w = max_w + 20
                
                tt_x = sel_rect.right + 15
                tt_y = sel_rect.top
                if tt_x + tt_w > WIDTH: # No salir de la pantalla por la derecha
                    tt_x = sel_rect.left - tt_w - 15
                    
                tt_bg = pygame.Surface((tt_w, tt_h))
                tt_bg.set_alpha(240)
                tt_bg.fill((20, 20, 30))
                screen.blit(tt_bg, (tt_x, tt_y))
                pygame.draw.rect(screen, (100, 100, 150), (tt_x, tt_y, tt_w, tt_h), 2)
                
                cy = tt_y + 5
                for s in tt_surfaces:
                    screen.blit(s, (tt_x + 10, cy))
                    cy += s.get_height()
            
            # Capa de Interfaz (UI) panel de fondo
            hud_rect = pygame.Surface((WIDTH, 110))
            hud_rect.set_alpha(200)
            hud_rect.fill((10, 10, 10))
            screen.blit(hud_rect, (0, 0))
            pygame.draw.line(screen, (200, 200, 200), (0, 110), (WIDTH, 110), 2)
            
            ui_text = [
                f"MALLA CURRICULAR (MAPA DAG) | Semestre: {semester_counter} | Tiempo Record: {par_score}",
                f"Energia: {energy}/{max_energy}",
                "Mover: WASD | Disparar: Flechas/Mouse | Entrar: ENTER | Descansar: ESPACIO"
            ]
            
            y_off = 15
            for line in ui_text:
                ts = font_md.render(line, False, TEXT_COLOR)
                screen.blit(ts, (15, y_off))
                y_off += 30
                
            # Animación de descanso
            if rest_animation_timer > 0:
                rest_animation_timer -= 1
                alpha = int((rest_animation_timer / 90) * 255)
                
                overlay = pygame.Surface((WIDTH, HEIGHT))
                overlay.set_alpha(alpha // 3) # Capa semitransparente verde
                overlay.fill((50, 200, 50))
                screen.blit(overlay, (0, 0))
                
                # Textos flotantes
                offset_y = (90 - rest_animation_timer) * 1.5 # Sube progresivamente
                msg = font_lg.render("Zzz... DESCANSO COMPLETADO", True, (150, 255, 150))
                msg.set_alpha(alpha)
                screen.blit(msg, msg.get_rect(center=(WIDTH // 2, HEIGHT // 2 - offset_y)))
                
                msg2 = font_md.render("¡ENERGÍA RESTAURADA AL MÁXIMO!", True, (255, 255, 255))
                msg2.set_alpha(alpha)
                screen.blit(msg2, msg2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50 - offset_y)))
                
        elif game_state == "COMBAT" or (game_state == "PAUSE" and previous_state == "COMBAT"):
            draw_floor(screen, current_room, combat_cam_x, combat_cam_y)
            combat_player.draw(screen, combat_cam_x, combat_cam_y)
            for e in enemies:
                e.draw(screen, combat_cam_x, combat_cam_y)
                
            # Dibujar textos flotantes de daño
            for ft in floating_texts:
                alpha = min(255, int((ft["life"] / 40.0) * 255))
                dmg_surf = font_md.render(ft["text"], True, ft["color"])
                dmg_surf.set_alpha(alpha)
                rect = dmg_surf.get_rect(center=(int(ft["x"] + combat_cam_x), int(ft["y"] + combat_cam_y)))
                screen.blit(dmg_surf, rect)
                
            # UI de Combate - Panel superior
            hud_rect = pygame.Surface((WIDTH, 60))
            hud_rect.set_alpha(180)
            hud_rect.fill((10, 10, 10))
            screen.blit(hud_rect, (0, 0))
            pygame.draw.line(screen, (150, 150, 150), (0, 60), (WIDTH, 60), 2)
            
            # Dibujar barra de vida gráfica del jugador (Top-Left)
            if HEART_FRAMES and len(HEART_FRAMES) == 5:
                max_hearts = 7
                hp_per_heart = combat_player.max_hp / max_hearts
                
                # Suavizar la animación de pérdida de vida
                if not hasattr(combat_player, 'display_hp'):
                    combat_player.display_hp = combat_player.hp
                if combat_player.display_hp > combat_player.hp:
                    combat_player.display_hp -= 2.0  # Animación rápida
                elif combat_player.display_hp < combat_player.hp:
                    combat_player.display_hp = combat_player.hp
                
                current_hp = combat_player.display_hp
                
                bar_x = 15
                bar_y = 15
                for i in range(max_hearts):
                    heart_hp = current_hp - (i * hp_per_heart)
                    heart_hp = max(0, min(hp_per_heart, heart_hp))
                    fraction = heart_hp / hp_per_heart
                    frame_idx = int(round(fraction * 4)) # 0 a 4 (5 fotogramas)
                    frame_idx = max(0, min(4, frame_idx))
                    
                    screen.blit(HEART_FRAMES[frame_idx], (bar_x + i * 32, bar_y)) # Separación ajustada (32px)
            else:
                hp_text = font_md.render("Vida:", False, (255, 255, 255))
                screen.blit(hp_text, (15, 15))
                
                bar_x = 15 + hp_text.get_width() + 10
                bar_y = 18
                bar_w = 200
                bar_h = 24
                
                hp_ratio = max(0, combat_player.hp / combat_player.max_hp)
                pygame.draw.rect(screen, (80, 20, 20), (bar_x, bar_y, bar_w, bar_h)) # Fondo de la barra
                pygame.draw.rect(screen, (255, 50, 50), (bar_x, bar_y, bar_w * hp_ratio, bar_h)) # Relleno de vida
                pygame.draw.rect(screen, (255, 255, 255), (bar_x, bar_y, bar_w, bar_h), 2) # Borde de la barra
                
                # Texto de vida numérico
                hp_num = font_sm.render(f"{max(0, int(combat_player.hp))}/{combat_player.max_hp}", False, (255, 255, 255))
                screen.blit(hp_num, (bar_x + bar_w//2 - hp_num.get_width()//2, bar_y + 2))

            # Título de la sala (Top-Right)
            room_name = engine.subjects[current_room]['name']
            title = f"Limpiando: {room_name}"
            title_color = (255, 255, 255)
            
            if current_room in engine.critical_nodes:
                title += " [CAMINO CRITICO]"
                title_color = engine.node_colors.get(current_room, (255, 100, 100))
                
            room_ts = font_md.render(title, False, title_color)
            # Alineado a la derecha para no chocar con la barra de vida
            screen.blit(room_ts, (WIDTH - room_ts.get_width() - 20, 15))
            
        elif game_state == "WIN":
            if event.type == pygame.KEYDOWN:
                save_mgr.delete_save(current_slot)
                main_menu.notification = "¡Nuevo enemigo desbloqueado! La experiencia es rejugable."
                main_menu.notification_timer = 300
                trigger_transition("MAIN_MENU", "FADE", 0.05)
                
            win_ts = font_lg.render(f"¡PROYECTO DE TITULACION APROBADO! ¡HAS GANADO!", False, (0, 255, 0))
            stat_ts = font_md.render(f"Te tomo {semester_counter} Semestres. (El record ideal era {par_score})", False, TEXT_COLOR)
            restart_ts = font_md.render("Presiona cualquier tecla para regresar al menu.", False, TEXT_COLOR)
            
            screen.blit(win_ts, (WIDTH//2 - win_ts.get_width()//2, HEIGHT//2 - 50))
            screen.blit(stat_ts, (WIDTH//2 - stat_ts.get_width()//2, HEIGHT//2))
            screen.blit(restart_ts, (WIDTH//2 - restart_ts.get_width()//2, HEIGHT//2 + 50))
            
        elif game_state == "GAME_OVER":
            go_ts = font_lg.render("TE HAS QUEDADO SIN ENERGIA.", False, (255, 0, 0))
            restart_ts = font_md.render("Presiona 'R' para reintentar el nivel.", False, TEXT_COLOR)
            screen.blit(go_ts, (WIDTH//2 - go_ts.get_width()//2, HEIGHT//2 - 50))
            screen.blit(restart_ts, (WIDTH//2 - restart_ts.get_width()//2, HEIGHT//2 + 50))

        if game_state == "PAUSE":
            pause_menu.draw(screen)

        # Renderizar transición
        if save_indicator_timer > 0:
            save_indicator_timer -= 1
            # Fondo oscuro semitransparente
            s = pygame.Surface((180, 50), pygame.SRCALPHA)
            s.fill((0, 0, 0, 100)) # Alpha mucho más transparente (antes 200)
            screen.blit(s, (WIDTH - 200, HEIGHT - 70))
            
            # Círculo e icono (tamaño intermedio)
            icon_x, icon_y = WIDTH - 170, HEIGHT - 45
            if SAVE_ICON_IMG:
                scale_factor = 1.0 + 0.15 * abs(math.sin(save_indicator_timer * 0.1))
                new_w = int(SAVE_ICON_IMG.get_width() * scale_factor)
                new_h = int(SAVE_ICON_IMG.get_height() * scale_factor)
                scaled_img = pygame.transform.smoothscale(SAVE_ICON_IMG, (new_w, new_h))
                img_rect = scaled_img.get_rect(center=(icon_x, icon_y))
                screen.blit(scaled_img, img_rect)
            else:
                pygame.draw.circle(screen, (100, 255, 100), (icon_x, icon_y), 17, 3)
                arc_angle = (save_indicator_timer * 12) % 360
                pygame.draw.arc(screen, (255, 255, 255), (icon_x - 17, icon_y - 17, 34, 34), math.radians(arc_angle), math.radians(arc_angle+100), 4)
            
            # Texto
            s_text = font_sm.render("Guardando...", True, (255, 255, 255))
            screen.blit(s_text, (icon_x + 25, icon_y - s_text.get_height()//2))
            
        if trans_state["active"]:
            trans_state["progress"] += trans_state["speed"]
            if trans_state["progress"] >= 1.0:
                trans_state["progress"] = 1.0
                trans_state["active"] = False
            
            # Dibujamos encima del 'screen' que ya tiene el nuevo estado
            render_transition(screen, trans_state["old_surf"], screen.copy(), trans_state["type"], trans_state["progress"], WIDTH, HEIGHT)

        # Escalado final: estirar la superficie interna a la ventana real
        scaled_surf = pygame.transform.scale(screen, real_screen.get_size())
        real_screen.blit(scaled_surf, (0, 0))
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
    pygame.quit()
    sys.exit()
