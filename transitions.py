import pygame
import math

def render_transition(surface, old_surf, new_surf, t_type, progress, width, height):
    """
    Renderiza la transición directamente sobre surface.
    progress va de 0.0 a 1.0.
    """
    # Empezamos limpiando
    surface.fill((0, 0, 0))
    
    if t_type == "SLIDE_LEFT":
        # old_surf se va a la izquierda, new_surf entra por la derecha
        offset_x = int(width * progress)
        surface.blit(old_surf, (-offset_x, 0))
        surface.blit(new_surf, (width - offset_x, 0))
        
    elif t_type == "SLIDE_RIGHT":
        # old_surf se va a la derecha, new_surf entra por la izquierda
        offset_x = int(width * progress)
        surface.blit(old_surf, (offset_x, 0))
        surface.blit(new_surf, (-width + offset_x, 0))
        
    elif t_type == "CIRCLE":
        # Círculo que se cierra y se abre.
        # De 0.0 a 0.5: se cierra sobre old_surf
        # De 0.5 a 1.0: se abre sobre new_surf
        max_radius = math.hypot(width/2, height/2)
        if progress < 0.5:
            # 0.0 -> r=max, 0.5 -> r=0
            p = progress * 2
            r = max_radius * (1 - p)
            surface.blit(old_surf, (0, 0))
        else:
            # 0.5 -> r=0, 1.0 -> r=max
            p = (progress - 0.5) * 2
            r = max_radius * p
            surface.blit(new_surf, (0, 0))
            
        # Para hacer el efecto de iris, dibujamos una máscara circular
        # Hay formas más eficientes, pero una máscara negra con un hoyo transparente funciona.
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 255))
        pygame.draw.circle(mask, (0, 0, 0, 0), (width//2, height//2), int(r))
        surface.blit(mask, (0, 0))
        
    elif t_type == "PIXELATE":
        # Bajamos la resolución y la subimos
        # 0.0 -> pixel_size = 1, 0.5 -> pixel_size = max (ej 32)
        if progress < 0.5:
            p = progress * 2
            surf_to_draw = old_surf
        else:
            p = 1.0 - ((progress - 0.5) * 2)
            surf_to_draw = new_surf
            
        pixel_size = max(1, int(64 * p))
        
        if pixel_size > 1:
            small = pygame.transform.scale(surf_to_draw, (width // pixel_size, height // pixel_size))
            pixelated = pygame.transform.scale(small, (width, height))
            surface.blit(pixelated, (0, 0))
        else:
            surface.blit(surf_to_draw, (0, 0))
            
    else: # FADE
        # 0.0 a 0.5 -> old_surf con overlay negro creciente
        # 0.5 a 1.0 -> new_surf con overlay negro decreciente
        fade_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        if progress < 0.5:
            p = progress * 2
            alpha = int(255 * p)
            surface.blit(old_surf, (0, 0))
        else:
            p = (progress - 0.5) * 2
            alpha = int(255 * (1 - p))
            surface.blit(new_surf, (0, 0))
            
        fade_surf.fill((0, 0, 0, alpha))
        surface.blit(fade_surf, (0, 0))
