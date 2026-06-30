import pygame
import math
import save_manager
from enemy import BugEnemy, SpaghettiEnemy, MemoryLeakEnemy, DeadlineEnemy, MiniBoss, Boss

def draw_purple_cross_bg(surface, width, height, time_offset=0):
    # Base dark purple
    surface.fill((25, 5, 45))
    # Draw faint crosses pattern
    cross_color = (40, 10, 70)
    spacing = 64
    offset_x = (time_offset // 2) % spacing
    offset_y = (time_offset // 2) % spacing
    
    for y in range(-spacing, height + spacing, spacing):
        for x in range(-spacing, width + spacing, spacing):
            px = x + offset_x
            py = y + offset_y
            pygame.draw.rect(surface, cross_color, (px - 2, py - 8, 4, 16))
            pygame.draw.rect(surface, cross_color, (px - 8, py - 2, 16, 4))

def render_3d_gradient_text(text, font):
    base_text = font.render(text, True, (255, 255, 255))
    w, h = base_text.get_size()
    
    # Create gradient surface
    grad_surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        ratio = y / max(1, h - 1)
        r = 255
        g = int(255 - ratio * 120)
        b = int(200 - ratio * 200)
        pygame.draw.line(grad_surf, (r, g, b), (0, y), (w, y))
        
    grad_surf.blit(base_text, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    
    # Create shadow
    shadow_depth = 6
    final_surf = pygame.Surface((w + shadow_depth, h + shadow_depth), pygame.SRCALPHA)
    
    shadow_text = font.render(text, True, (50, 0, 60))
    for i in range(shadow_depth, 0, -1):
        final_surf.blit(shadow_text, (i, i))
        
    final_surf.blit(grad_surf, (0, 0))
    return final_surf

def scale_to_cover(image, target_w, target_h):
    img_w, img_h = image.get_size()
    scale = max(target_w / img_w, target_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    scaled = pygame.transform.smoothscale(image, (new_w, new_h))
    
    surf = pygame.Surface((target_w, target_h))
    offset_x = (new_w - target_w) // 2
    offset_y = (new_h - target_h) // 2
    surf.blit(scaled, (-offset_x, -offset_y))
    return surf

class DisclaimerScreen:
    def __init__(self, width, height, font_lg, font_md):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.time = 0
        try:
            self.save_img = pygame.image.load("assets/images/ui/save.png").convert_alpha()
            # Forzar un aspecto cuadrado (60x60) para corregir la percepción de anchura
            self.save_img = pygame.transform.scale(self.save_img, (60, 60))
        except:
            self.save_img = None

    def handle_event(self, event):
        # Ya no requiere presionar tecla, pasa por tiempo
        return None

    def draw(self, surface):
        self.time += 1
        surface.fill((10, 10, 15)) # Fondo oscuro
        
        # Ícono animado de guardado
        cx = self.width // 2
        cy = self.height // 3
        
        if self.save_img:
            # Pálpito sutil
            scale_factor = 1.0 + 0.15 * abs(math.sin(self.time * 0.05))
            new_w = int(self.save_img.get_width() * scale_factor)
            new_h = int(self.save_img.get_height() * scale_factor)
            scaled_img = pygame.transform.smoothscale(self.save_img, (new_w, new_h))
            img_rect = scaled_img.get_rect(center=(cx, cy))
            surface.blit(scaled_img, img_rect)
        else:
            pygame.draw.circle(surface, (100, 255, 100), (cx, cy), 30, 4)
            arc_angle = (self.time * 5) % 360
            pygame.draw.arc(surface, (255, 255, 255), (cx-30, cy-30, 60, 60), math.radians(arc_angle), math.radians(arc_angle+90), 6)

        title = self.font_lg.render("AUTOGUARDADO ACTIVADO", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.width // 2, self.height // 2 - 20))
        surface.blit(title, title_rect)

        desc = self.font_md.render("Tu progreso se guardara automaticamente tras superar cada habitacion.", True, (200, 200, 200))
        desc_rect = desc.get_rect(center=(self.width // 2, self.height // 2 + 30))
        surface.blit(desc, desc_rect)

class TitleScreen:
    def __init__(self, width, height, font_title, font_md):
        self.width = width
        self.height = height
        self.font_title = font_title
        self.font_md = font_md
        self.time = 0
        try:
            self.title_img = pygame.image.load("assets/images/ui/titulo_juego.png").convert_alpha()
            self.title_img = pygame.transform.scale(self.title_img, (950, 518)) # Más grande
        except:
            self.title_img = None
            
        try:
            self.bg_img = pygame.image.load("assets/images/backgrounds/bg_portada.jpg").convert()
            self.bg_img = pygame.transform.scale(self.bg_img, (width, height))
        except:
            self.bg_img = None
        
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            return "START"
        return None
        
    def draw(self, surface):
        self.time += 1
        
        if hasattr(self, 'bg_img') and self.bg_img:
            surface.blit(self.bg_img, (0, 0))
            # Oscurecer la imagen para que resalte el texto
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 210)) # Opacidad de 0 a 255 (más oscuro en portada)
            surface.blit(overlay, (0, 0))
        else:
            draw_purple_cross_bg(surface, self.width, self.height, self.time)
        
        if self.title_img:
            # Un poco más abajo (casi en el medio)
            title_rect = self.title_img.get_rect(center=(self.width // 2, self.height // 2 - 40))
            surface.blit(self.title_img, title_rect)
        else:
            title_surf = render_3d_gradient_text("MEGA-CALABOZO DAG", self.font_title)
            title_rect = title_surf.get_rect(center=(self.width // 2, self.height // 2 - 40))
            surface.blit(title_surf, title_rect)
        
        # Blinking text
        if (self.time // 30) % 2 == 0:
            start_text = self.font_md.render("PRESIONA CUALQUIER TECLA", True, (255, 255, 200))
            # Subirlo más (acercarlo aún más al título)
            start_rect = start_text.get_rect(center=(self.width // 2, self.height - 180))
            
            # Shadow for start text
            shadow = self.font_md.render("PRESIONA CUALQUIER TECLA", True, (50, 0, 60))
            surface.blit(shadow, (start_rect.x + 3, start_rect.y + 3))
            surface.blit(start_text, start_rect)

class MainMenu:
    def __init__(self, width, height, font_lg, font_md):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.options = ["Jugar", "Tutorial", "Opciones", "Salir"]
        self.jugar_expanded = False
        self.selected_index = 0
        self.time = 0
        self.notification = ""
        self.notification_timer = 0
        try:
            self.title_img = pygame.image.load("assets/images/ui/titulo_juego.png").convert_alpha()
            # Escalar si es necesario
            self.title_img = pygame.transform.scale(self.title_img, (600, 200))
        except:
            self.title_img = None
            
        try:
            self.bg_img_raw = pygame.image.load("assets/images/backgrounds/bg_portada.jpg").convert()
            self.bg_w = int(self.width * 1.1)
            self.bg_h = int(self.height * 1.1)
            self.bg_img = pygame.transform.scale(self.bg_img_raw, (self.bg_w, self.bg_h))
        except:
            self.bg_img = None


    @property
    def current_options(self):
        opts = []
        has_any_save = any(save_manager.has_save(i) for i in range(1, 4))
        for opt in self.options:
            opts.append(opt)
            if opt == "Jugar" and self.jugar_expanded:
                if has_any_save:
                    opts.extend(["  Continuar Partida", "  Nueva Partida", "  Cargar Partida"])
                else:
                    opts.extend(["  Nueva Partida", "  Cargar Partida"])
        return opts

    def unlock_bestiary(self):
        if "Bestiario" not in self.options:
            self.options.insert(2, "Bestiario")

    def handle_event(self, event):
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
        return None

    def draw(self, surface, mouse_x, mouse_y):
        self.time += 1
        
        if hasattr(self, 'bg_img') and self.bg_img:
            # Calculate parallax offset based on mouse position relative to center
            # Mouse goes left -> image shifts right
            offset_x = -((mouse_x / self.width) - 0.5) * (self.bg_w - self.width)
            offset_y = -((mouse_y / self.height) - 0.5) * (self.bg_h - self.height)
            
            # Base position is centered to hide edges
            base_x = -(self.bg_w - self.width) // 2
            base_y = -(self.bg_h - self.height) // 2
            
            surface.blit(self.bg_img, (base_x + offset_x, base_y + offset_y))
            
            # Oscurecer la imagen para que resalte el texto
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            surface.blit(overlay, (0, 0))
        else:
            draw_purple_cross_bg(surface, self.width, self.height, self.time)
        
        title_y = self.height // 4
        
        # Animación sutil de leve pálpito (Scale pulse) para el estilo pixel art
        # La escala variará muy sutilmente entre 1.0 y 1.04
        scale_factor = 1.0 + 0.04 * abs(math.sin(self.time * 0.05))
        
        if self.title_img:
            new_w = int(self.title_img.get_width() * scale_factor)
            new_h = int(self.title_img.get_height() * scale_factor)
            # transform.scale usa nearest-neighbor, manteniendo los bordes duros de pixel art
            scaled_img = pygame.transform.scale(self.title_img, (new_w, new_h))
            title_rect = scaled_img.get_rect(center=(self.width // 2, title_y))
            surface.blit(scaled_img, title_rect)
        else:
            title_surf = render_3d_gradient_text("MEGA-CALABOZO DAG", self.font_lg)
            new_w = int(title_surf.get_width() * scale_factor)
            new_h = int(title_surf.get_height() * scale_factor)
            scaled_surf = pygame.transform.scale(title_surf, (new_w, new_h))
            title_rect = scaled_surf.get_rect(center=(self.width // 2, title_y))
            surface.blit(scaled_surf, title_rect)

        opts = self.current_options
        for i, option in enumerate(opts):
            is_submenu = option.startswith("  ")
            display_text = option.strip()
            
            if i == self.selected_index:
                if is_submenu:
                    color = (220, 220, 220)
                    text = self.font_md.render("- " + display_text + " -", True, color)
                    shadow = self.font_md.render("- " + display_text + " -", True, (100, 100, 100))
                else:
                    color = (255, 255, 255)
                    text = self.font_md.render("> " + display_text + " <", True, color)
                    shadow = self.font_md.render("> " + display_text + " <", True, (150, 0, 150))
            else:
                color = (180, 130, 210)
                if is_submenu:
                    color = (130, 130, 130) # Un poco más opaco/oscuro para submenu
                text = self.font_md.render(display_text, True, color)
                
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 45))
            if i == self.selected_index:
                surface.blit(shadow, (rect.x + 3, rect.y + 3))
            surface.blit(text, rect)

        if self.notification and self.notification_timer > 0:
            self.notification_timer -= 1
            # Dibujar notificación en la parte inferior
            notif_surf = self.font_md.render(self.notification, True, (255, 255, 100))
            notif_rect = notif_surf.get_rect(center=(self.width // 2, self.height - 40))
            # Fondo semitransparente
            bg_rect = pygame.Rect(notif_rect.x - 20, notif_rect.y - 10, notif_rect.width + 40, notif_rect.height + 20)
            s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 180))
            surface.blit(s, bg_rect.topleft)
            surface.blit(notif_surf, notif_rect)

class PlaySubMenu:
    def __init__(self, width, height, font_lg, font_md):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.options = ["Continuar Partida", "Nueva Partida", "Cargar Partida", "Regresar"]
        self.selected_index = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.options[self.selected_index]
            elif event.key == pygame.K_ESCAPE:
                return "Regresar"
        return None

    def draw(self, surface):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        
        title = self.font_lg.render("SELECCIONA MODO", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.width // 2, self.height // 4))
        surface.blit(title, title_rect)

        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_index else (150, 150, 150)
            text = self.font_md.render(option, True, color)
            if i == self.selected_index:
                text = self.font_md.render("> " + option + " <", True, (255, 255, 0))
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 60))
            surface.blit(text, rect)

class SlotSelectMenu:
    def __init__(self, width, height, font_lg, font_md, save_manager, mode):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.save_manager = save_manager
        self.mode = mode # "NUEVA" o "CARGAR"
        self.options = ["Slot 1", "Slot 2", "Slot 3", "Regresar"]
        self.selected_index = 0
        self.confirming_slot = None
        self.confirm_index = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.confirming_slot:
                if event.key == pygame.K_LEFT or event.key == pygame.K_RIGHT:
                    self.confirm_index = 1 - self.confirm_index
                elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    if self.confirm_index == 1:
                        return self.confirming_slot
                    else:
                        self.confirming_slot = None
                elif event.key == pygame.K_ESCAPE:
                    self.confirming_slot = None
                return None
            
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                selection = self.options[self.selected_index]
                if selection.startswith("Slot ") and self.mode == "NUEVA":
                    slot_num = int(selection.split(" ")[1])
                    if self.save_manager.has_save(slot_num):
                        self.confirming_slot = selection
                        self.confirm_index = 0 # Default to No
                        return None
                return selection
            elif event.key == pygame.K_ESCAPE:
                return "Regresar"
        return None

    def draw(self, surface):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        surface.blit(overlay, (0, 0))
        
        if self.confirming_slot:
            warn_t1 = self.font_md.render(f"¿Seguro que quieres sobreescribir el {self.confirming_slot}?", True, (255, 100, 100))
            warn_t2 = self.font_md.render("No podras recuperar la partida actual.", True, (200, 200, 200))
            surface.blit(warn_t1, warn_t1.get_rect(center=(self.width // 2, self.height // 2 - 30)))
            surface.blit(warn_t2, warn_t2.get_rect(center=(self.width // 2, self.height // 2 + 10)))
            
            opts = ["NO", "SI"]
            for idx, opt in enumerate(opts):
                color = (255, 255, 255) if idx == self.confirm_index else (150, 150, 150)
                text = self.font_md.render(f"> {opt} <" if idx == self.confirm_index else opt, True, color)
                rect = text.get_rect(center=(self.width // 2 - 60 + idx * 120, self.height // 2 + 80))
                surface.blit(text, rect)
            return

        t_str = "NUEVA PARTIDA" if self.mode == "NUEVA" else "CARGAR PARTIDA"
        title = self.font_lg.render(t_str, True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.width // 2, self.height // 4))
        surface.blit(title, title_rect)

        for i in range(3):
            slot_name = f"Slot {i+1}"
            has_save = self.save_manager.has_save(i+1)
            
            if self.mode == "CARGAR" and not has_save:
                color = (100, 100, 100) # Gris oscuro
                opt_str = f"{slot_name}: VACIO"
            else:
                color = (255, 255, 255) if i == self.selected_index else (150, 150, 150)
                opt_str = f"{slot_name}: {'EXISTE' if has_save else 'VACIO'}"
                
            if i == self.selected_index:
                text = self.font_md.render("> " + opt_str + " <", True, (255, 255, 0) if (self.mode=="NUEVA" or has_save) else (150, 150, 0))
            else:
                text = self.font_md.render(opt_str, True, color)
                
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 60))
            surface.blit(text, rect)

        # Regresar
        i = 3
        color = (255, 255, 255) if i == self.selected_index else (150, 150, 150)
        text = self.font_md.render("Regresar", True, color)
        if i == self.selected_index:
            text = self.font_md.render("> Regresar <", True, (255, 255, 0))
        rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 60 + 20))
        surface.blit(text, rect)

class PauseMenu:
    def __init__(self, width, height, font_lg, font_md):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.options = ["Continuar", "Guardar y Salir al menú principal"]
        self.selected_index = 0

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.options[self.selected_index]
            elif event.key == pygame.K_ESCAPE:
                return "Continuar" # Un-pause on escape
        return None

    def draw(self, surface):
        # Draw a semi-transparent overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        title = self.font_lg.render("PAUSA", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.width // 2, self.height // 4))
        surface.blit(title, title_rect)

        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_index else (150, 150, 150)
            text = self.font_md.render(option, True, color)
            
            if i == self.selected_index:
                text = self.font_md.render("> " + option + " <", True, (255, 255, 0))
                
            rect = text.get_rect(center=(self.width // 2, self.height // 2 + i * 60))
            surface.blit(text, rect)

class BestiaryMenu:
    def __init__(self, width, height, font_lg, font_md, font_sm, save_manager=None):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.font_sm = font_sm
        self.save_manager = save_manager
        
        # Instantiate dummy enemies to get their sprites and stats
        self.enemies_data = [
            {"class": BugEnemy, "name": "BUG", "desc": "Errores de codigo. Veloces, erraticos, pero fragiles."},
            {"class": SpaghettiEnemy, "name": "CODIGO SPAGHETTI", "desc": "Estructura desastrosa. Su movimiento es caotico e impredecible."},
            {"class": MemoryLeakEnemy, "name": "MEMORY LEAK", "desc": "Pequeno y persistente. Drena los recursos si lo ignoras."},
            {"class": DeadlineEnemy, "name": "EL RELOJ (DEADLINE)", "desc": "La entrega final. Se acelera agresivamente si intentas evadirlo."},
            {"class": MiniBoss, "name": "MINI BOSS (PARCIAL)", "desc": "Evaluacion critica. Extremadamente resistente, lanza temibles 'Examenes Reprobados' (F). Aparece al final de las rondas de la malla curricular."},
            {"class": Boss, "name": "MEGA BOSS (TITULACION)", "desc": "El obstaculo academico final. Defensa casi impenetrable. Te acribillara con feroces 'Tesis Rechazadas' mientras el jurado sigue enviando problemas sin cesar."}
        ]
        
        self.instances = []
        for data in self.enemies_data:
            enemy_instance = data["class"](0, 0)
            enemy_instance.animator.animation_speed = 0.05 # Slower animation for Bestiary
            self.instances.append(enemy_instance)
            
        self.current_index = 0
        
        # Load unlocks from global save
        self.unlocked_names = ["BUG", "CODIGO SPAGHETTI", "MEMORY LEAK", "EL RELOJ (DEADLINE)"]
        if self.save_manager:
            global_data = self.save_manager.load_global_save()
            self.unlocked_names = global_data.get("bestiary_unlocks", self.unlocked_names)
        
        # Load assets
        try:
            self.bg_img = pygame.image.load("assets/images/ui/bestiary_bg.png").convert()
            self.bg_img = pygame.transform.scale(self.bg_img, (self.width, self.height))
            
            arr_l = pygame.image.load("assets/images/ui/arrow_left.png").convert_alpha()
            self.arrow_left = pygame.transform.scale(arr_l, (64, 64))
            
            arr_r = pygame.image.load("assets/images/ui/arrow_right.png").convert_alpha()
            self.arrow_right = pygame.transform.scale(arr_r, (64, 64))
        except Exception as e:
            print("Error loading bestiary assets:", e)
            self.bg_img = None
            self.arrow_left = None
            self.arrow_right = None
            
        self.left_rect = None
        self.right_rect = None
        
    def unlock(self, name):
        if name not in self.unlocked_names:
            self.unlocked_names.append(name)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.current_index = (self.current_index - 1) % len(self.enemies_data)
            elif event.key == pygame.K_RIGHT:
                self.current_index = (self.current_index + 1) % len(self.enemies_data)
            elif event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                return "BACK"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if hasattr(self, 'left_rect') and self.left_rect and self.left_rect.collidepoint(event.pos):
                self.current_index = (self.current_index - 1) % len(self.enemies_data)
            elif hasattr(self, 'right_rect') and self.right_rect and self.right_rect.collidepoint(event.pos):
                self.current_index = (self.current_index + 1) % len(self.enemies_data)
        return None

    def draw(self, surface):
        if hasattr(self, 'bg_img') and self.bg_img:
            surface.blit(self.bg_img, (0, 0))
        else:
            surface.fill((11, 11, 11))
        
        # UI Top Left
        title = self.font_lg.render("ENEMIGOS", True, (255, 255, 255))
        surface.blit(title, (40, 40))
        
        current_data = self.enemies_data[self.current_index]
        enemy_name_str = current_data["name"]
        
        is_unlocked = enemy_name_str in self.unlocked_names
        
        # Draw Enemy or Silhouette
        enemy_inst = self.instances[self.current_index]
        enemy_inst.animator.update()
        img = enemy_inst.animator.get_current_image()
        
        name_y = self.height // 2 - 150
        desc_y = self.height // 2 + 120
        stats_y = self.height // 2 + 150
        
        if img:
            if not is_unlocked:
                # Create silhouette
                silhouette = img.copy()
                silhouette.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
                img = silhouette
                
            # Scale up for bestiary viewing
            scaled_img = pygame.transform.scale(img, (img.get_width() * 2, img.get_height() * 2))
            img_rect = scaled_img.get_rect(center=(self.width // 2, self.height // 2))
            
            surface.blit(scaled_img, img_rect)
            
            # Adjust text positions dynamically based on sprite size
            name_y = min(name_y, img_rect.top - 30)
            desc_y = max(desc_y, img_rect.bottom + 20)
            stats_y = max(stats_y, img_rect.bottom + 50)
            
            # Position arrows based on image width to avoid overlapping the sprite
            left_arrow_x = min(self.width // 2 - 200, img_rect.left - 50)
            right_arrow_x = max(self.width // 2 + 200, img_rect.right + 50)
        else:
            left_arrow_x = self.width // 2 - 200
            right_arrow_x = self.width // 2 + 200
            
        # Title Centered
        display_name = enemy_name_str if is_unlocked else "???"
        name_text = self.font_md.render(display_name, True, (255, 255, 255))
        surface.blit(name_text, name_text.get_rect(center=(self.width // 2, name_y)))
        
        # Draw Arrows
        if hasattr(self, 'arrow_left') and self.arrow_left:
            self.left_rect = self.arrow_left.get_rect(center=(left_arrow_x, self.height // 2))
            surface.blit(self.arrow_left, self.left_rect)
        else:
            left_arrow = self.font_lg.render("<", True, (255, 255, 255))
            self.left_rect = left_arrow.get_rect(center=(left_arrow_x, self.height // 2))
            surface.blit(left_arrow, self.left_rect)
            
        if hasattr(self, 'arrow_right') and self.arrow_right:
            self.right_rect = self.arrow_right.get_rect(center=(right_arrow_x, self.height // 2))
            surface.blit(self.arrow_right, self.right_rect)
        else:
            right_arrow = self.font_lg.render(">", True, (255, 255, 255))
            self.right_rect = right_arrow.get_rect(center=(right_arrow_x, self.height // 2))
            surface.blit(right_arrow, self.right_rect)
            
        # Draw Description and Stats
        if is_unlocked:
            desc_text = self.font_sm.render(current_data["desc"], True, (200, 200, 200))
            surface.blit(desc_text, desc_text.get_rect(center=(self.width // 2, desc_y)))
            
            stats_str = f"HP: {enemy_inst.max_hp}  |  Velocidad: {enemy_inst.speed}"
            stats_text = self.font_sm.render(stats_str, True, (255, 100, 100))
            surface.blit(stats_text, stats_text.get_rect(center=(self.width // 2, stats_y)))
        else:
            desc_text = self.font_sm.render("Aún no has encontrado a este enemigo.", True, (100, 100, 100))
            surface.blit(desc_text, desc_text.get_rect(center=(self.width // 2, desc_y)))
        
        # Back hint
        back_text = self.font_sm.render("ESC para salir", True, (150, 150, 150))
        surface.blit(back_text, (40, self.height - 40))

class OptionsMenu:
    def __init__(self, width, height, font_lg, font_md, font_sm, global_data=None):
        self.width = width
        self.height = height
        self.font_lg = font_lg
        self.font_md = font_md
        self.font_sm = font_sm
        
        self.options = ["Modo de Pantalla", "Resolución", "Volumen General", "Volumen Música", "Aplicar y Volver", "Volver sin guardar"]
        self.selected_index = 0
        
        self.fullscreen = global_data.get("fullscreen", True) if global_data else True
        self.available_resolutions = pygame.display.list_modes()
        if not self.available_resolutions:
            self.available_resolutions = [(1024, 768)]
        if (1024, 768) not in self.available_resolutions:
            self.available_resolutions.append((1024, 768))
            self.available_resolutions.sort(reverse=True)
            
        self.res_index = 0
        info = pygame.display.Info()
        
        saved_res = global_data.get("resolution", None) if global_data else None
        
        for i, res in enumerate(self.available_resolutions):
            if saved_res and res[0] == saved_res[0] and res[1] == saved_res[1]:
                self.res_index = i
                break
            elif not saved_res and res[0] == info.current_w and res[1] == info.current_h:
                self.res_index = i
                break
                
        self.general_volume = global_data.get("volume", 100) if global_data else 100
        self.music_volume = global_data.get("music_volume", 100) if global_data else 100
        self.time = 0
        
        try:
            self.bg_img = pygame.image.load("assets/images/ui/config_bg.png").convert()
            self.bg_img = scale_to_cover(self.bg_img, self.width, self.height)
        except Exception as e:
            print("Failed to load config_bg:", e)
            self.bg_img = None

    def update_width_height(self, w, h):
        self.width = w
        self.height = h
        if hasattr(self, 'bg_img') and self.bg_img:
            try:
                raw_bg = pygame.image.load("assets/images/ui/config_bg.png").convert()
                self.bg_img = scale_to_cover(raw_bg, self.width, self.height)
            except:
                self.bg_img = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_index = (self.selected_index - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.key == pygame.K_LEFT:
                self.adjust_option(-1)
            elif event.key == pygame.K_RIGHT:
                self.adjust_option(1)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                opt = self.options[self.selected_index]
                if opt == "Aplicar y Volver":
                    return {"action": "APPLY", "fullscreen": self.fullscreen, "res": self.available_resolutions[self.res_index], "gen_vol": self.general_volume, "mus_vol": self.music_volume}
                elif opt == "Volver sin guardar":
                    return {"action": "BACK"}
                else:
                    self.adjust_option(1)
        return None
        
    def adjust_option(self, direction):
        opt = self.options[self.selected_index]
        if opt == "Modo de Pantalla":
            self.fullscreen = not self.fullscreen
        elif opt == "Resolución":
            self.res_index = (self.res_index + direction) % len(self.available_resolutions)
        elif opt == "Volumen General":
            self.general_volume = max(0, min(100, self.general_volume + direction * 10))
        elif opt == "Volumen Música":
            self.music_volume = max(0, min(100, self.music_volume + direction * 10))

    def draw(self, surface):
        self.time += 1
        
        if hasattr(self, 'bg_img') and self.bg_img:
            surface.blit(self.bg_img, (0, 0))
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180)) # Oscurecer la imagen de opciones
            surface.blit(overlay, (0, 0))
        else:
            draw_purple_cross_bg(surface, self.width, self.height, self.time)
        
        title_surf = render_3d_gradient_text("OPCIONES", self.font_lg)
        title_rect = title_surf.get_rect(center=(self.width // 2, self.height // 5))
        surface.blit(title_surf, title_rect)
        
        start_y = self.height // 3
        spacing = 50
        
        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_index else (150, 150, 150)
            prefix = "> " if i == self.selected_index else "  "
            suffix = " <" if i == self.selected_index else "  "
            
            value_str = ""
            if option == "Modo de Pantalla":
                value_str = "Completa" if self.fullscreen else "Ventana"
            elif option == "Resolución":
                r = self.available_resolutions[self.res_index]
                value_str = f"{r[0]}x{r[1]}"
            elif option == "Volumen General":
                value_str = f"{self.general_volume}%"
            elif option == "Volumen Música":
                value_str = f"{self.music_volume}%"
                
            display_text = f"{prefix}{option}: {value_str}{suffix}" if value_str else f"{prefix}{option}{suffix}"
            
            text_surf = self.font_md.render(display_text, True, color)
            shadow = self.font_md.render(display_text, True, (50, 0, 50))
            
            rect = text_surf.get_rect(center=(self.width // 2, start_y + i * spacing))
            surface.blit(shadow, (rect.x + 2, rect.y + 2))
            surface.blit(text_surf, rect)
            
        help_text = self.font_sm.render("Usa las FLECHAS para moverte y cambiar valores. ENTER para seleccionar.", True, (200, 200, 200))
        surface.blit(help_text, help_text.get_rect(center=(self.width // 2, self.height - 40)))
