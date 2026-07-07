import pygame

from level import DEFAULT_HAZARD_DAMAGE, DEFAULT_HAZARD_DAMAGE_COOLDOWN

class CollisionEditor:
    def __init__(self, level, collision_manager):
        self.level = level
        self.manager = collision_manager
        pygame.font.init()
        self.font = pygame.font.SysFont("Arial", 16)
        
        # State: IDLE, CREATING, DRAGGING, RESIZING
        self.state = "IDLE"
        
        self.selected_type = "solid" # "solid", "hazard", "walkable"
        self.selected_index = -1 # Index of selected item within its list
        self.selected_list_type = "solid" # Which list the selected item belongs to
        
        self.drag_start = (0, 0)
        self.creating_start = (0, 0)
        self.creating_current = (0, 0)
        
        # For moving
        self.initial_rect = None
        
        # For resizing
        self.resize_handle = None # TL, T, TR, R, BR, B, BL, L
        self.handle_size = 12
        self.min_size = 16

    def handle_event(self, event, mx, my, cam_x=0, cam_y=0):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left click
                world_x, world_y = self.screen_to_world((mx, my), cam_x, cam_y)
                
                # Check for resize handle click first
                if self.selected_index != -1:
                    handle = self.get_handle_at(world_x, world_y)
                    if handle:
                        self.state = "RESIZING"
                        self.resize_handle = handle
                        self.drag_start = (world_x, world_y)
                        self.initial_rect = self.get_selected_rect().copy()
                        return

                # Check for selection / moving
                clicked_type, clicked_idx = self.get_collider_at(world_x, world_y)
                if clicked_type is not None:
                    self.selected_list_type = clicked_type
                    self.selected_index = clicked_idx
                    self.state = "DRAGGING"
                    self.drag_start = (world_x, world_y)
                    self.initial_rect = self.get_selected_rect().copy()
                else:
                    self.state = "CREATING"
                    self.creating_start = (world_x, world_y)
                    self.creating_current = (world_x, world_y)
                    self.selected_index = -1

        elif event.type == pygame.MOUSEMOTION:
            world_x, world_y = self.screen_to_world((mx, my), cam_x, cam_y)
            if self.state == "CREATING":
                self.creating_current = (world_x, world_y)
            elif self.state == "DRAGGING":
                dx = world_x - self.drag_start[0]
                dy = world_y - self.drag_start[1]
                rect = self.get_selected_rect()
                if rect and self.initial_rect:
                    rect.x = int(self.initial_rect.x + dx)
                    rect.y = int(self.initial_rect.y + dy)
            elif self.state == "RESIZING":
                dx = world_x - self.drag_start[0]
                dy = world_y - self.drag_start[1]
                self.apply_resize(dx, dy)
                
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                if self.state == "CREATING":
                    self.finish_creation()
                self.state = "IDLE"
                
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                self.delete_selected()
            elif event.key == pygame.K_h:
                self.toggle_selected_type()
            elif event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                self.save_level()

    def screen_to_world(self, screen_pos, cam_x, cam_y):
        return (screen_pos[0] - cam_x, screen_pos[1] - cam_y)
        
    def get_list_by_type(self, t):
        if t == "solid": return self.level.colliders, self.level.collider_metadata
        if t == "hazard": return self.level.hazard_zones, self.level.hazard_metadata
        if t == "walkable": return self.level.walkable_zones, self.level.walkable_metadata
        return [], []

    def get_collider_at(self, x, y):
        # Check in reverse order (top first)
        types = ["walkable", "hazard", "solid"]
        for t in types:
            rects, _ = self.get_list_by_type(t)
            for i in range(len(rects)-1, -1, -1):
                if rects[i].collidepoint(x, y):
                    return t, i
        return None, -1

    def get_selected_rect(self):
        if self.selected_index == -1: return None
        rects, _ = self.get_list_by_type(self.selected_list_type)
        if 0 <= self.selected_index < len(rects):
            return rects[self.selected_index]
        return None

    def get_handle_at(self, x, y):
        rect = self.get_selected_rect()
        if not rect: return None
        handles = self.get_handles_for_rect(rect)
        for handle_name, h_rect in handles.items():
            if h_rect.collidepoint(x, y):
                return handle_name
        return None
        
    def get_handles_for_rect(self, rect):
        s = self.handle_size
        return {
            "TL": pygame.Rect(rect.left - s/2, rect.top - s/2, s, s),
            "T": pygame.Rect(rect.centerx - s/2, rect.top - s/2, s, s),
            "TR": pygame.Rect(rect.right - s/2, rect.top - s/2, s, s),
            "R": pygame.Rect(rect.right - s/2, rect.centery - s/2, s, s),
            "BR": pygame.Rect(rect.right - s/2, rect.bottom - s/2, s, s),
            "B": pygame.Rect(rect.centerx - s/2, rect.bottom - s/2, s, s),
            "BL": pygame.Rect(rect.left - s/2, rect.bottom - s/2, s, s),
            "L": pygame.Rect(rect.left - s/2, rect.centery - s/2, s, s)
        }

    def apply_resize(self, dx, dy):
        rect = self.get_selected_rect()
        if not rect or not self.initial_rect: return
        
        new_rect = self.initial_rect.copy()
        h = self.resize_handle
        
        if "L" in h:
            new_rect.left = min(self.initial_rect.left + dx, self.initial_rect.right - self.min_size)
            new_rect.width = self.initial_rect.right - new_rect.left
        if "R" in h:
            new_rect.width = max(self.min_size, self.initial_rect.width + dx)
        if "T" in h:
            new_rect.top = min(self.initial_rect.top + dy, self.initial_rect.bottom - self.min_size)
            new_rect.height = self.initial_rect.bottom - new_rect.top
        if "B" in h:
            new_rect.height = max(self.min_size, self.initial_rect.height + dy)
            
        rect.update(new_rect)

    def finish_creation(self):
        x1, y1 = self.creating_start
        x2, y2 = self.creating_current
        x = int(min(x1, x2))
        y = int(min(y1, y2))
        w = int(max(self.min_size, abs(x2 - x1)))
        h = int(max(self.min_size, abs(y2 - y1)))
        
        rect = pygame.Rect(x, y, w, h)
        rects, meta = self.get_list_by_type("solid")
        rects.append(rect)
        meta.append({"name": f"new_{len(rects)}", "type": "solid", "enabled": True})
        
        self.selected_list_type = "solid"
        self.selected_index = len(rects) - 1
        
        self.sync_manager()

    def delete_selected(self):
        if self.selected_index == -1: return
        rects, meta = self.get_list_by_type(self.selected_list_type)
        if 0 <= self.selected_index < len(rects):
            rects.pop(self.selected_index)
            meta.pop(self.selected_index)
        self.selected_index = -1
        self.sync_manager()

    def toggle_selected_type(self):
        if self.selected_index == -1: return
        rects, meta = self.get_list_by_type(self.selected_list_type)
        if not (0 <= self.selected_index < len(rects)): return
        
        r = rects.pop(self.selected_index)
        m = meta.pop(self.selected_index)
        
        # Cycle solid -> hazard -> walkable -> solid
        if self.selected_list_type == "solid":
            next_t = "hazard"
        elif self.selected_list_type == "hazard":
            next_t = "walkable"
        else:
            next_t = "solid"
            
        n_rects, n_meta = self.get_list_by_type(next_t)
        m["type"] = next_t
        if next_t == "hazard":
            m.setdefault("damage", DEFAULT_HAZARD_DAMAGE)
            m.setdefault("damage_cooldown", DEFAULT_HAZARD_DAMAGE_COOLDOWN)
        n_rects.append(r)
        n_meta.append(m)
        
        self.selected_list_type = next_t
        self.selected_index = len(n_rects) - 1
        
        self.sync_manager()

    def save_level(self):
        self.level.save_to_file()
        print(f"Nivel guardado de forma segura: {self.level.name}.json")

    def sync_manager(self):
        # Update collision manager's internal lists to match the level's modified lists
        self.manager.colliders = [r.copy() for r in self.level.colliders]
        self.manager.metadata = [m.copy() for m in self.level.collider_metadata]
        self.manager.walkable_zones = [r.copy() for r in self.level.walkable_zones]
        self.manager.walkable_metadata = [m.copy() for m in self.level.walkable_metadata]
        # the manager doesn't manage hazards directly for physics, but just in case, we sync what we need.

    def draw(self, screen, cam_x=0, cam_y=0):
        # Draw colliders (red)
        for i, r in enumerate(self.level.colliders):
            color = (255, 50, 50, 100)
            if self.selected_list_type == "solid" and i == self.selected_index: color = (50, 255, 50, 150)
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill(color)
            screen.blit(s, (r.x + cam_x, r.y + cam_y))
            pygame.draw.rect(screen, (255, 100, 100), r.move(cam_x, cam_y), 1)

        # Draw hazards (yellow/magenta)
        for i, r in enumerate(self.level.hazard_zones):
            color = (255, 255, 0, 100)
            if self.selected_list_type == "hazard" and i == self.selected_index: color = (50, 255, 50, 150)
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill(color)
            screen.blit(s, (r.x + cam_x, r.y + cam_y))
            pygame.draw.rect(screen, (255, 255, 100), r.move(cam_x, cam_y), 1)
            
        # Draw walkable (cyan)
        for i, r in enumerate(self.level.walkable_zones):
            color = (50, 200, 255, 100)
            if self.selected_list_type == "walkable" and i == self.selected_index: color = (50, 255, 50, 150)
            s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            s.fill(color)
            screen.blit(s, (r.x + cam_x, r.y + cam_y))
            pygame.draw.rect(screen, (100, 200, 255), r.move(cam_x, cam_y), 1)

        # Draw handles for selected
        rect = self.get_selected_rect()
        if rect:
            handles = self.get_handles_for_rect(rect)
            for h_rect in handles.values():
                h_rect_screen = h_rect.move(cam_x, cam_y)
                pygame.draw.rect(screen, (255, 255, 255), h_rect_screen)
                pygame.draw.rect(screen, (0, 0, 0), h_rect_screen, 1)
                
            info = f"Sel: {self.selected_list_type} {self.selected_index} | Pos: {int(rect.x)},{int(rect.y)} Size: {int(rect.w)}x{int(rect.h)}"
            t = self.font.render(info, True, (255, 255, 255))
            screen.blit(t, (10, 100))

        # Draw creation rect
        if self.state == "CREATING":
            x = min(self.creating_start[0], self.creating_current[0])
            y = min(self.creating_start[1], self.creating_current[1])
            w = abs(self.creating_current[0] - self.creating_start[0])
            h = abs(self.creating_current[1] - self.creating_start[1])
            cr = pygame.Rect(x, y, w, h).move(cam_x, cam_y)
            pygame.draw.rect(screen, (255, 255, 255), cr, 2)
            
        # HUD
        hud = ["=== COLLISION EDITOR ===",
               "Arrastrar: Crear / Mover / Redimensionar",
               "H: Cambiar Tipo (Solid/Hazard/Walkable)",
               "Supr: Borrar",
               "Ctrl+S: Guardar en JSON",
               "F2: Salir"]
        y_off = 130
        for line in hud:
            t = self.font.render(line, True, (200, 200, 255))
            screen.blit(t, (10, y_off))
            y_off += 20
