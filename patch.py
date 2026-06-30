import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'from transitions import render_transition' not in code:
    code = code.replace('import math\n', 'import math\nfrom transitions import render_transition\n')

# Define Transition State in main
trans_def = """    trans_state = {
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
"""

# Replace old transition vars
old_trans_vars = """    transitioning = False
    transition_alpha = 0
    next_state = None
    transition_speed = 15"""

if old_trans_vars in code:
    code = code.replace(old_trans_vars, trans_def)

# Ignore input if transitioning
code = code.replace('if transitioning:', 'if trans_state["active"]:')

# TITLE_SCREEN logic
code = code.replace(
"""                if action == "START":
                    transitioning = True
                    main_menu.time = 0
                    next_state = "MAIN_MENU\"""",
"""                if action == "START":
                    main_menu.time = 0
                    trigger_transition("MAIN_MENU", "FADE", 0.03)"""
)

# Replace all simple game_state assignments. We will manually map them.
replacements = {
    'game_state = "MAP"': 'trigger_transition("MAP", "CIRCLE", 0.04)',
    'game_state = "TUTORIAL"': 'trigger_transition("TUTORIAL", "SLIDE_LEFT", 0.05)',
    'game_state = "BESTIARY"': 'trigger_transition("BESTIARY", "PIXELATE", 0.03)',
    'game_state = "OPTIONS"': 'trigger_transition("OPTIONS", "SLIDE_LEFT", 0.05)',
    'game_state = previous_state': 'trigger_transition(previous_state, "FADE", 0.08)',
    'game_state = "MAIN_MENU"': 'trigger_transition("MAIN_MENU", "SLIDE_RIGHT", 0.05)',
    'game_state = "PAUSE"': 'trigger_transition("PAUSE", "FADE", 0.08)',
    'game_state = "COMBAT"': 'trigger_transition("COMBAT", "CIRCLE", 0.03)',
    'game_state = "WIN"': 'trigger_transition("WIN", "FADE", 0.02)',
    'game_state = "GAME_OVER"': 'trigger_transition("GAME_OVER", "FADE", 0.02)',
}

# DO NOT replace game_state == checks or game_state = "TITLE_SCREEN" (the initial declaration)
# So we only replace indented ones with exact match
for k, v in replacements.items():
    code = re.sub(r'(\s+)' + re.escape(k) + r'(?=\n|\r)', r'\1' + v, code)

# Finally, replace the old transition rendering block at the end of the drawing phase
old_render_block = """        # Transición suave
        if transitioning:
            transition_alpha += transition_speed
            if transition_speed > 0 and transition_alpha >= 255:
                transition_alpha = 255
                game_state = next_state
                transition_speed = -15
            elif transition_speed < 0 and transition_alpha <= 0:
                transition_alpha = 0
                transitioning = False
                transition_speed = 15
                
            fade_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade_surf.fill((0, 0, 0, max(0, min(255, int(transition_alpha)))))
            screen.blit(fade_surf, (0, 0))"""

new_render_block = """        # Renderizar transición
        if trans_state["active"]:
            trans_state["progress"] += trans_state["speed"]
            if trans_state["progress"] >= 1.0:
                trans_state["progress"] = 1.0
                trans_state["active"] = False
            
            # Dibujamos encima del 'screen' que ya tiene el nuevo estado
            render_transition(screen, trans_state["old_surf"], screen.copy(), trans_state["type"], trans_state["progress"], WIDTH, HEIGHT)"""

code = code.replace(old_render_block, new_render_block)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('Success')
