# AGENTS.md — Pygame Top-Down Collision Architecture

## Project role
Act as a senior Python/Pygame game-engine developer specializing in top-down RPG collision systems, enemy movement, map data, and pixel-art level implementation.

This project uses 2D pixel-art background images as visual maps. The background image is not the collision source. Collision must be handled with a separate logical collision layer.

## Main goal
Implement and maintain a professional, scalable collision system for a Python-only Pygame top-down RPG. The system must support the player, enemies, multiple maps, debug visualization, and future expansion to triggers, doors, interactable objects, and pathfinding.

## Core rules
- Do not detect collision directly from the rendered background image.
- Keep the visual background separate from the collision logic.
- Do not hardcode all colliders inside `main.py`.
- Do not destroy or rewrite unrelated working code.
- Prefer small, focused changes over large risky rewrites.
- Preserve existing game behavior unless the task specifically requires changing it.
- Use clear file/module separation.
- Use `pygame.Rect` for the first production-ready collision layer.
- Leave the architecture ready for future `pygame.mask` pixel-perfect collision if needed.
- The same collision system must work for the player and enemies.
- Always resolve movement by axis: move X, correct X collisions, then move Y, correct Y collisions.
- Add or preserve debug mode to visualize collision rectangles.
- When adding new map collision data, keep it editable and easy to adjust.

## Preferred architecture
Organize or refactor toward this structure when appropriate:

```text
project/
├── main.py
├── player.py
├── enemy.py
├── entity.py
├── level.py
├── collision_manager.py
├── camera.py                  # optional if the project uses a camera
├── assets/
│   └── backgrounds/
│       ├── laboratorio.png
│       ├── fabrica.png
│       └── vault.png
└── levels/
    ├── laboratorio.json
    ├── fabrica.json
    └── vault.json
```

If the project already has another structure, adapt to it instead of forcing this exact layout.

## Level data requirements
Each level should be able to define:

- level name
- background image path
- player spawn position
- map width and height
- colliders
- optional triggers
- optional enemy spawn points
- optional interactable zones
- optional doors/transitions

Preferred JSON example:

```json
{
  "name": "glitch_room",
  "background": "assets/backgrounds/glitch_room.png",
  "size": [1920, 1080],
  "player_spawn": [220, 520],
  "colliders": [
    { "name": "top_wall", "x": 0, "y": 0, "w": 1920, "h": 80 },
    { "name": "bottom_wall", "x": 0, "y": 1000, "w": 1920, "h": 80 },
    { "name": "left_wall", "x": 0, "y": 0, "w": 80, "h": 1080 },
    { "name": "right_wall", "x": 1840, "y": 0, "w": 80, "h": 1080 },
    { "name": "large_machine", "x": 760, "y": 420, "w": 280, "h": 180 }
  ],
  "triggers": []
}
```

## CollisionManager expectations
Create or maintain a `CollisionManager` class with responsibilities like:

```python
class CollisionManager:
    def __init__(self, colliders):
        self.colliders = colliders

    def check_collision(self, rect):
        ...

    def move_and_collide(self, entity, dx, dy):
        ...

    def draw_debug(self, surface, camera=None):
        ...
```

Implementation expectations:

- Store colliders as `pygame.Rect` objects.
- Keep optional collider metadata such as `name`, `type`, or `enabled` if useful.
- `move_and_collide(entity, dx, dy)` should mutate `entity.rect` safely.
- Correct collisions after moving on each axis.
- Do not let entities tunnel through obstacles under normal movement speeds.
- If speed is high, consider sub-stepping or clamping movement.

## Entity movement rules
Player and enemies should share the same collision flow.

Expected entity properties:

```python
entity.rect
entity.speed
```

Expected movement pattern:

```python
collision_manager.move_and_collide(entity, dx, dy)
```

Do not duplicate collision logic separately in `player.py` and `enemy.py`. If duplicate logic exists, refactor it into shared code.

## Player requirements
- Player must not pass through walls or objects.
- Player movement must feel smooth.
- Diagonal movement should not become faster unless the existing game intentionally allows that.
- Use the player collision box carefully. It is usually better to collide with the character's feet/body area rather than the full sprite rectangle if the sprite is taller than the actual body.

## Enemy requirements
- Enemies must use the same colliders as the player.
- Enemies must not pass through walls, machines, bookshelves, pipes, or large objects.
- If enemies follow the player, keep movement simple first, then prepare for pathfinding later.
- For future pathfinding, leave the code compatible with grid-based navigation, waypoints, or navigation nodes.

## Debug mode
Add or preserve a debug collision overlay.

Expected behavior:

- Press `F1` to toggle collider visualization.
- Draw colliders with rectangle outlines only.
- Debug drawing must account for camera offset if a camera exists.
- Debug mode must not affect gameplay.

Example:

```python
if debug_collisions:
    collision_manager.draw_debug(screen, camera)
```

## Camera and scaling rules
If the game uses a camera:

- Store entity positions and colliders in world coordinates.
- Convert to screen coordinates only when drawing.
- Do not store colliders in screen coordinates.

If the background is scaled:

- Keep a consistent coordinate system.
- Either scale the colliders by the same factor or load colliders in the actual world resolution.
- Document which approach the project uses.

## Map objects that should usually be collidable
For the pixel-art dungeon backgrounds in this project, make these objects solid when visually appropriate:

- walls
- borders of floating platforms
- desks and large tables
- CRT monitors and computer stations
- server racks and server pillars
- bookshelves
- columns
- large gears
- conveyor belts if they block movement
- metallic scales and sorting machines
- pipes and pipe clusters
- wire mesh fences
- barrels and crates
- robotic structures under construction
- cranes and gantries
- consoles
- central processors or cores
- biological pods or sci-fi capsules
- large vines, roots, or neural structures

Small decorative items may remain non-collidable unless they visually block the path.

## Collision data creation approach
When asked to create colliders for a new background:

1. Inspect the level/background layout.
2. Add simple rectangular colliders for all major obstacles.
3. Name each collider clearly.
4. Prefer fewer broad colliders at first instead of too many tiny ones.
5. Add debug visualization so the user can adjust positions.
6. Tell the user which JSON file or Python data file to edit.
7. Mention the coordinate system and map resolution used.

## Future expansion rules
Keep the design ready for:

- pixel-perfect collision with `pygame.mask`
- trigger zones
- doors and map transitions
- interactable objects
- damage zones
- enemy pathfinding
- collision layers
- moving platforms or moving obstacles
- editor tooling for drawing colliders visually

Do not implement these future systems unless the user asks, but avoid blocking them with poor architecture.

## Testing checklist
After modifying collision or movement code:

- Run the game if possible.
- Verify player cannot cross walls.
- Verify player cannot cross major objects.
- Verify enemies cannot cross the same colliders.
- Toggle debug mode with F1.
- Confirm colliders align with the map.
- Confirm camera offset does not break collision drawing.
- Confirm no unrelated visual or gameplay feature broke.

## Response format after changes
When finishing a task, summarize:

- files changed
- classes/functions added
- how to add a new collider
- how to toggle debug mode
- any assumptions made
- any remaining manual adjustments needed

Keep explanations practical and focused on what the user needs to continue building the game.
