# PROJECT_CONTEXT — Referencia técnica completa (para IAs y desarrolladores)

> **Propósito de este documento:** contiene TODO lo necesario para entender y
> modificar el proyecto **sin tener que releer el código fuente**. Si eres una IA
> trabajando en este repo, lee esto primero. Para reglas de estilo/prácticas ver
> también [`AGENTS.md`](AGENTS.md). Este archivo debe mantenerse actualizado
> cuando cambie la arquitectura.

---

## 0. Resumen ejecutivo

**Mega-Calabozo DAG** es un RPG top-down 2D en **Python + Pygame** (`pygame-ce`).
La malla curricular de Ingeniería en Sistemas de Información (59 materias) se
modela como un **DAG** (grafo dirigido acíclico): cada materia es un nodo, cada
prerrequisito una arista. El jugador navega el grafo y, para "aprobar" una
materia, supera una arena de combate **bullet-hell** top-down. Hay progresión por
energía/semestres, jefes, bestiario, tutorial y guardado en JSON.

- **Entry point:** `main.py` → `python main.py`.
- **Resolución interna fija:** `1280×720` (superficie virtual `screen`), escalada a
  la ventana real con letterbox 16:9.
- **Simulación a 60 Hz fijos** (fixed timestep) desacoplada del FPS de render.
- **Todo es frame-based** (velocidades en px/frame, cooldowns en frames), pero
  corre a 60 pasos/seg gracias al fixed timestep. **No** conviertas a delta-time
  variable (rompería colisiones/IA calibradas a 60 Hz).

---

## 1. Ejecución y dependencias

- Python 3.10+ (probado en 3.14). Dependencia única: `pygame-ce` (`import pygame`).
- Usa `pygame.display.get_desktop_sizes()`, `pygame.SCALED`, etc. → requiere
  pygame moderno.
- No hay `requirements.txt`. Instalar con `pip install pygame-ce`.

---

## 2. Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Entry point. Máquina de estados, bucle principal (fixed timestep), render, sistema de resolución/escalado, HUD y render del mapa, combate, helpers visuales del mapa. |
| `dag_engine.py` | `DagEngine`: DAG, orden topológico, camino crítico por DP, estados de nodo, desbloqueos. |
| `data.py` | `SUBJECTS`: dict con las 59 materias (`{id: {"name", "reqs":[...]}}`). |
| `map_generator.py` | `MapGenerator` / `Room`: layout del grafo por semestres, dibujo de nodos y aristas. |
| `player.py` | `Player` y `Bullet`. Movimiento 8-dir, disparo, vida, animación. |
| `enemy.py` | `Enemy` (base), `EnemyBullet`, y subclases: `BugEnemy`, `SpaghettiEnemy`, `MemoryLeakEnemy`, `DeadlineEnemy`, `MiniBoss`, `Boss`. |
| `enemy_ai.py` | `EnemyNavigator` (estado de ruta A*, anti-atasco) y `separation_delta` (separación entre enemigos). |
| `pathfinding.py` | `PathFinder`: rejilla A* generada desde el nivel; line-of-sight; zonas walkable/hazard. |
| `level.py` | `Level` (dataclass) + carga de arenas desde `levels/*.json`. |
| `collision_manager.py` | `CollisionManager`: colisiones por `Rect`, `move_and_collide` con resolución por ejes. |
| `collision_editor.py` | Editor interno de colisiones (tecla F2 en combate). |
| `animator.py` | `Animator`: animación de spritesheets, avance por tiempo real (independiente del FPS). |
| `menu.py` | Pantallas/menús: Disclaimer, Title, MainMenu, PlaySubMenu, SlotSelectMenu, PauseMenu, BestiaryMenu, OptionsMenu + helpers de dibujo. |
| `save_manager.py` | Guardado/carga JSON global y por slot. |
| `transitions.py` | `render_transition`: transiciones entre estados. |
| `tutorial.py` | `TutorialState`: flujo del tutorial por fases. |
| `assets/` | `fonts/` (VT323, BoldPixels), `images/backgrounds/` (`s1..s10.png`, `map_bg.png`, `floor_tile.png`, `bg_portada.jpg`), `images/enemies/`, `images/player/`, `images/ui/`. |
| `levels/` | Definiciones de arenas en `.json` (ej. `combat_default.json`, `s1.json`…). |
| `saves/` | `global_save.json` + `slot_1..3.json` (autogenerados). |

---

## 3. El DAG y sus algoritmos (`dag_engine.py`, `data.py`)

### 3.1 Datos (`data.py`)
`SUBJECTS` = `{ "TIP01BFT03": {"name": "PROGRAMACION I", "reqs": ["TIP..."]}, ... }`.
- **59 nodos.** El ID codifica el **semestre en los caracteres `[3:5]`**
  (`TIP01…` → semestre 1, `TIP10…` → 10). El nodo final de titulación es
  `TIP10TEMTT1`.
- `reqs` = lista de IDs prerrequisito. Aristas dirigidas `req → nodo`.

### 3.2 `DagEngine`
- `state: {node: NodeState}` con `NodeState.LOCKED | UNLOCKED | CLEANED`
  (strings `"LOCKED"/"UNLOCKED"/"CLEANED"`). Todos empiezan `LOCKED`.
- `calculate_dp()`: **orden topológico** (Kahn con in-degrees) + **DP** del camino
  más largo → `self.dp[node]` = profundidad máxima (nº de semestres para llegar a
  ese nodo). `par_score = max(dp.values())` = **tiempo récord ideal** (mínimo de
  semestres teóricos). Expuesto por `get_par_score()`.
- `calculate_critical_path()`: DFS hacia atrás desde los nodos con `dp == par_score`
  siguiendo aristas donde `dp[req] == dp[node]-1`. Guarda `critical_paths`,
  `critical_nodes`, y asigna colores: `node_colors[node]` y `edge_colors[(req,node)]`
  (lista de colores; una arista puede pertenecer a varias rutas). Paleta de **8
  colores** (Crimson, Emerald, Sapphire, Gold, Teal, Plum, Rust, Indigo).
- `update_unlocks()`: un nodo pasa a `UNLOCKED` cuando **todos** sus `reqs` están
  `CLEANED`. El nodo final `TIP10TEMTT1` (Mega-Candado) se desbloquea cuando
  `cleaned_count >= len(nodes)-1` (todo lo demás aprobado).
  - ⚠️ **HACK TEMPORAL (MODO PRUEBA):** al final de `update_unlocks()` hay un bucle
    que desbloquea **todos** los nodos `LOCKED` a `UNLOCKED` (líneas ~132-136).
    Por eso ahora mismo todo se puede jugar sin respetar prerequisitos. Para
    volver al comportamiento real, eliminar ese bloque.
- `clean_room(node)`: marca `UNLOCKED → CLEANED` (aprobar). Devuelve bool.

---

## 4. Máquina de estados y bucle principal (`main.py`)

### 4.1 Estados (`game_state`)
`DISCLAIMER_SCREEN → TITLE_SCREEN → MAIN_MENU → SLOT_SELECT → MAP → COMBAT`,
más `PAUSE`, `TUTORIAL`, `BESTIARY`, `OPTIONS`, `WIN`, `GAME_OVER`.
`previous_state` recuerda desde dónde se abrió `PAUSE`/`OPTIONS`/`BESTIARY`.

### 4.2 Bucle a paso fijo (fixed timestep) — clave
Constantes: `FIXED_FPS=60`, `FIXED_DT_MS=1000/60`, `MAX_SIM_STEPS=5`.
Cada iteración del `while running:`:
1. `frame_ms = clock.tick(0 if fps_limit=="unlimited" else fps_limit)` — ritmo de
   render.
2. `sim_accumulator += frame_ms`; se calcula `sim_steps = int(acc / FIXED_DT_MS)`
   (acumulador acotado a `MAX_SIM_STEPS` para evitar *spiral of death*).
   `render_scale = min(frame_ms/FIXED_DT_MS, MAX_SIM_STEPS)` (para efectos de
   render dependientes del tiempo, p. ej. transiciones).
3. Input/eventos: **una vez** por frame de render.
4. **Simulación:** el bloque de "Actualizaciones Continuas" (combate, tutorial,
   timers de UI) va dentro de `for _ in range(sim_steps):` → corre a 60 Hz reales
   sin importar el FPS. Aquí se decrementan `rest_animation_timer`,
   `map_message_timer`, `save_indicator_timer` (para que su duración no dependa del
   FPS).
5. **Render:** una vez. Dibuja según `game_state` sobre `screen` (1280×720).
6. Transición (si activa): `trans_state["progress"] += speed * render_scale`.
7. `present_virtual_surface(screen, real_screen, aspect_mode)` + `pygame.display.flip()`.

**Implicación:** subir el FPS no acelera el juego (lógica siempre 60 Hz) ni lo
hace visiblemente más fluido en movimiento (no hay interpolación); su beneficio
real es menor latencia de input.

---

## 5. Sistema de resolución y escalado (`main.py`)

- `WIDTH, HEIGHT = 1280, 720`. `screen = pygame.Surface((WIDTH,HEIGHT))` es el
  **lienzo virtual** donde se dibuja TODO. `real_screen` es la ventana real.
- `apply_display_mode(resolution, fullscreen)`:
  - **Fullscreen:** `set_mode((w,h), FULLSCREEN | SCALED)`. `SCALED` deja que SDL
    escale a la pantalla física **sin cambiar el modo de video del hardware**
    (evita el fallback a 800×600 en monitores que no soportan el modo pedido).
    Fallback a `(0,0) FULLSCREEN` nativo si falla.
  - **Ventana:** limita la resolución al **área útil del escritorio**
    (`get_desktop_size()` menos márgenes: −20 ancho, −80 alto) para que la ventana
    no quede fuera de pantalla.
- `get_viewport_transform(target_size, aspect_mode)` → `(scale, offset_x, offset_y,
  scaled_w, scaled_h)`. `aspect_mode`: `"fit"` (letterbox, barras) o `"fill"`
  (recorta). Default `"fit"`.
- `present_virtual_surface(...)`: escala el lienzo virtual al `real_screen` con
  letterbox.
- `window_to_virtual(pos, target_size, aspect_mode)`: convierte coords del mouse
  reales → espacio virtual. Se llama cada frame: `mouse_x, mouse_y =
  window_to_virtual(pygame.mouse.get_pos(), real_screen.get_size(), aspect_mode)`.
- `F11` = toggle fullscreen. La resolución/aspecto se configuran en Opciones y se
  guardan en `global_save.json`.

---

## 6. Sistema de FPS (`main.py`)

- `VALID_FPS_LIMITS = [30, 60, 120, 144, 165, 240, "unlimited"]`, default `60`.
- `sanitize_fps_limit(v)`: valida; cualquier valor inválido/corrupto → `60`.
- `fps_limit` se carga de `global_save["fps_limit"]` y se aplica en `clock.tick()`.
  `"unlimited"` → `tick(0)`.
- La simulación SIEMPRE es 60 Hz (ver §4.2), así que cambiar FPS nunca altera la
  velocidad del juego.

---

## 7. Animación (`animator.py`)

- `Animator(spritesheet, frame_w, frame_h, rows, cols, animation_speed)`. Cachea
  frames recortados (bounding box) y escalados por altura.
- `set_state(row)` / `update()` / `get_current_image()`.
- **`update()` avanza por TIEMPO REAL** (usa `pygame.time.get_ticks()`, con clamp
  de dt a 100 ms): `current_frame += animation_speed * dt_ms/(1000/60)`. Así la
  velocidad de animación es independiente del FPS de render (a 60 FPS = comportamiento
  clásico). `animation_speed` = cuadros de sprite por "tick de 60 Hz".
- Estados de animación del jugador/enemigos: `0`=idle, `1`=walk/move, `2`=attack.

---

## 8. Mapa: layout, render y cámara (`map_generator.py` + sección MAP de `main.py`)

### 8.1 Layout (`MapGenerator._generate_layout`) — NO cambiar sin querer
- Nodos agrupados por semestre (`int(node[3:5])`), una fila por semestre.
- Constantes: `ROOM_WIDTH=120`, `ROOM_HEIGHT=60`, `MARGIN_X=40`, `MARGIN_Y=140`.
  Fila i empieza en `start_x=50`; `start_y` inicia en 50 y baja `ROOM_HEIGHT+MARGIN_Y`.
- El grafo real ocupa aprox. `x[50,1290]` (ancho ~1240) y `y[50,1910]` (alto ~1860,
  10 semestres). Es más alto que la pantalla → scroll vertical.
- `self.rooms: {id: Room}` y `self.edges: [(start_pos, end_pos, edge_colors)]`.
  `edge_colors` es `None` (arista normal) o lista de colores (camino crítico).
- `get_room_at(x, y, cam_x, cam_y)` = hitbox de selección (rect + offset cámara).

### 8.2 Render del mapa
Orden en `main.py` (estado MAP): `MAP_BG_IMG` → `get_map_overlay()` (viñeta) →
`map_gen.draw()` (aristas y nodos) → highlight de selección → tooltip → HUD.
- `Room.draw(surface, font, state, node_color)`: cuerpo redondeado, sombra, bisel
  (relieve), borde exterior + borde de color si es crítico/especial. Glifos de
  estado (dibujados antes del texto para no tapar legibilidad): candado
  (`LOCKED`), check (`CLEANED`), estrella (nodo especial `TIP10TEMTT1`). Texto con
  sombra. Paleta por estado: bloqueado = apagado morado-gris (texto claro),
  disponible = pergamino, completado = verde.
- Aristas: `_draw_edge_line()` añade un *casing* oscuro bajo la línea para
  contraste. Normales en gris; críticas como líneas paralelas por color (misma
  matemática: normal unitario, `spacing=4`, `edge_width = max(2, 6//n)`).

### 8.3 HUD y UI del mapa (helpers en `main.py`)
Paleta central `MAP_UI` (panel, bordes, acento dorado, texto). Estilo **pixel-art
duro** (rellenos planos, sin degradados suaves):
- `draw_pixel_panel(surface, rect, title_h, accent, fill)`: panel con contorno
  duro + bisel + remaches en esquinas. Usado por el tooltip.
- `draw_map_hud(surface, semester, par, energy, max_energy)`: barra superior de
  **104 px**. Muestra "MALLA CURRICULAR" + subtítulo, bloques SEMESTRE / TIEMPO
  RÉCORD (par_score), **ENERGÍA como gemas/cristales pixelados**
  (`draw_energy_crystal`, lleno = energía disponible), y pie con controles.
- `draw_energy_crystal(surface, cx, cy, filled)`: diamante pixelado escalonado.
- `draw_selection_highlight(surface, rect)`: marco duro parpadeante + corner
  brackets (sin glow suave).
- `draw_subject_tooltip(surface, engine, selected_node, sel_rect)`: panel pixel-art
  con nombre de la materia (título), separador y lista de prerrequisitos coloreados
  (verde = ya cursado). Se voltea a la izquierda si no cabe a la derecha; se ajusta
  para no salir por abajo.
- `build_map_overlay()/get_map_overlay()`: viñeteado ambiental sutil cacheado.

### 8.4 Cámara del mapa y su clamp
- `camera_x, camera_y` = offset de dibujo. Se mueve con: arrastre (clic derecho),
  selección por defecto (centra el nodo), navegación con flechas (centra el nodo
  vecino), y al cargar partida.
- `clamp_map_camera(cx, cy)` (nested en `main`): limita la cámara para no arrastrar
  al vacío. `pad=140` (aire permitido), `hud_top=104` (considera el HUD para que la
  primera fila baje por debajo del HUD y se vea completa). Se aplica tras CADA
  cambio de cámara. Con el layout actual: rango X≈[-170,110], Y≈[-1330,194].
- ⚠️ El delta del arrastre usa coords **crudas** de la ventana (no virtuales), así
  que la velocidad del arrastre difiere ligeramente si la ventana ≠ 1280×720.

---

## 9. Jugador (`player.py`)

- `Player(x, y, scale)`: `speed=5` (px/frame), `hp=100`, `max_hp=100`, `radius≈30`,
  `rect` ~51×57 (escalado), `shoot_cooldown=15` (frames), `state` (0/1/2), `flip`.
- `move(keys, w, h, collision_manager)`: 8 direcciones (WASD), diagonal ×`1/√2`,
  resuelve con `collision_manager.move_and_collide`.
- `shoot(target)/shoot_angle(angle)`: crea `Bullet` si `shoot_cooldown==0`; fija
  cooldown 15 y `state=2`.
- `Bullet`: `speed=10` px/frame, `radius=8`, sprite (`player/0.png`,`1.png`) o texto
  "0"/"1". Colisión por distancia euclidiana.
- HP en combate se dibuja como **7 corazones** (`HEART_FRAMES`, 5 fotogramas por
  corazón según fracción de vida). `display_hp` suaviza la animación de pérdida.

---

## 10. Enemigos (`enemy.py`)

`Enemy(x,y,radius,speed,hp,sheet,...)` base. `update()` = `move_logic` → planificar
con `EnemyNavigator.plan_movement` (A*) → resolver colisión → `record_result` →
`_update_cooldowns_and_bullets`. `collides_with_player/bullet` por distancia.
Atributos IA: `ai_smartness` (0..1), `separation_weight`, `navigator`,
`ignores_map_collision`.

Roster (radio, velocidad px/frame, HP):

| Clase | r | speed | hp | Notas |
|---|---|---|---|---|
| `BugEnemy` | 20 | 3.0 | 20 | Rápido, frágil. anim 0.08, smart 0.9. |
| `SpaghettiEnemy` | 29 | 1.5 | 40 | Movimiento errático (ángulo ±0.5 rand). |
| `MemoryLeakEnemy` | 24 | 2.0 | 30 | Persistente, smart 0.95. |
| `DeadlineEnemy` | 36 | 1.0 | 25 | Acelera a speed 4 si el jugador está a <150; aura roja pulsante en `state=2`. |
| `MiniBoss` | 90 | 1.2 | 150 | Aparece al final de rondas en nodos de **camino crítico**. Salta obstáculos (jump AI con validación de aterrizaje) y lanza **artillería de área** (misiles → explosiones → zonas de fuego con daño por tick). Muchos timers de fase. |
| `Boss` | 105 | 0.8 | 500 | Nodo final `TIP10TEMTT1`. `ignores_map_collision` (vuela). Dispara anillos de 8 balas ("tesis"). |

`EnemyBullet(x,y,angle, speed, color, radius, b_type)`: `b_type` `"normal"/"miniboss"/"boss"`
cambia el dibujo (F reprobada / tomo de tesis). Daños en combate (ver §11).

---

## 11. Combate (`main.py`, estado COMBAT)

- `start_combat(room_id)`: `energy -= 1`, carga el nivel de la arena, crea `Player`
  en `player_spawn`, spawnea 3-6 enemigos aleatorios (`BugEnemy, SpaghettiEnemy,
  MemoryLeakEnemy, DeadlineEnemy`). Si el nodo es final → `Boss`; si es crítico (y
  no final) con 1 ola → `MiniBoss`.
- Olas: `max_waves = 1 + semester_counter // 2`, `wave_timer=300` frames entre olas;
  nuevas olas aparecen desde una "puerta" (`world*0.85, world*0.22`). En la última
  ola de un nodo crítico se añade `MiniBoss`.
- Daño: contacto normal 10 (jefes 20), bala enemiga 15, bala del jugador 10 al
  enemigo; `attack_cooldown` del enemigo 30 (jefes 45). Daño de área del MiniBoss
  vía `collect_area_damage_events`.
- **Victoria** (última ola sin enemigos): `level_passed_timer=120` → `clean_room` +
  `update_unlocks` + **autosave** (`save_indicator_timer=120`). Si era el final →
  `WIN`; si no → vuelve a `MAP`.
- **Derrota** (`hp<=0`): `level_failed_timer=120` → vuelve a `MAP`.
- Textos de daño flotantes (`floating_texts`), suben y se desvanecen (`life`).
- Cámara de combate `combat_cam_x/y` sigue al jugador con clamp al tamaño del mundo
  (`clamp_camera_axis`, `update_combat_camera`).

---

## 12. Colisiones (`collision_manager.py`)

- `CollisionManager(colliders, metadata, walkable_zones, walkable_metadata,
  max_step=8)`. Colliders = `pygame.Rect`.
- `move_and_collide(entity, dx, dy)`: subdivide el movimiento en pasos ≤ `max_step`
  y resuelve **por ejes** (primero X, luego Y): si hay colisión, empuja fuera
  (`rect.right = min(collider.left)` etc.). Si hay `walkable_zones`, además impide
  salirse de ellas. Devuelve `{"x":bool,"y":bool}` (bloqueo por eje). La entidad
  debe exponer `.rect` y opcionalmente `.x/.y` + `sync_rect_to_position` /
  `sync_position_to_rect`.
- `check_collision(rect)`, `get_collisions(rect)`, `draw_debug(...)`.

---

## 13. Pathfinding (`pathfinding.py`) e IA de navegación (`enemy_ai.py`)

- `PathFinder(level, ...)`: construye una **rejilla A*** desde el nivel
  (`cell_size` de `level.pathfinding_cell_size`, def 24). Grillas cacheadas por
  tamaño de agente. Considera `colliders` (bloquean), `walkable_zones` (obligan a
  estar dentro) y `hazard_zones` (coste extra `hazard_cost=8`, con fallback si no
  hay ruta limpia).
- `find_path(start, goal, agent_size)` → `PathResult(points, found, used_hazards)`.
  `has_line_of_sight(...)` para atajo directo. `is_position_walkable(...)`,
  `nearest_walkable_cell(...)`. Heurística octil (movimiento en 8 direcciones, con
  chequeo de esquinas para no cortar diagonales por muros).
- `EnemyNavigator` (por enemigo): modos `direct` / `astar` / `astar_hazard` /
  `fallback` / `unstuck`. Repathing periódico, detección de atasco (`stuck_frames`,
  `collision_frames`) y **recuperación** (busca puntos tangentes para rodear
  obstáculos). `separation_delta` empuja enemigos para que no se apilen.
- Debug de rutas/saltos: `draw_enemy_ai_debug` (tecla F4).

---

## 14. Niveles (`level.py`)

- `Level` (dataclass): `name, background, size, player_spawn, colliders(+metadata),
  hazard_zones(+metadata), walkable_zones(+metadata), enemy_spawns, doors,
  triggers, interactables, character_scale (def 0.7), pathfinding_cell_size (def 24)`.
- `load_combat_level(room_id)`: intenta `room_id.json` → `sXX.json` (semestre del ID
  vía `level_key_from_room_id`, que extrae `TIP(\d\d)`) → `combat_default.json` →
  `build_default_combat_level` (arena vacía con bordes).
- **Esquema JSON de nivel:** `{"name","background","size":[w,h],"player_spawn":[x,y],
  "character_scale","pathfinding_cell_size","enemy_spawns":[[x,y]...],
  "colliders":[{"x","y","w","h","name","type","enabled"}...],"hazard_zones":[{...,"damage"}],
  "walkable_zones":[{...}], "triggers", "doors", "interactables"}`.
- `create_collision_manager()` y `load_background()` (escala el fondo al tamaño del
  mundo). `save_to_file()` usado por el editor de colisiones (con backup `.bak`).

---

## 15. Guardado (`save_manager.py`)

- **Global** `saves/global_save.json`:
  `{"bestiary_unlocks":[...], "volume", "resolution":[w,h], "fullscreen":bool,
  "aspect_mode":"fit|fill", "tutorial_completed":bool, "music_volume", "fps_limit"}`.
  `load_global_save()` devuelve defaults si falta/está corrupto.
- **Slot** `saves/slot_{1..3}.json`:
  `{"semester_counter","energy","max_energy","camera_x","camera_y","nodes_state": engine.state}`.
- `save_game(slot, engine, semester, energy, max_energy, cam_x, cam_y)`,
  `load_game(slot)`, `has_save`, `delete_save`, `get_latest_slot()` (por mtime).
- Autosave tras superar cada sala (ver §11). Al ganar el juego se borra el slot
  (`delete_save`).

---

## 16. Menús (`menu.py`)

Clases: `DisclaimerScreen` (splash autoguardado, auto-avanza), `TitleScreen`
("presiona cualquier tecla"), `MainMenu` (Jugar→Continuar/Nueva/Cargar, Tutorial,
Bestiario [tras tutorial], Opciones, Salir; con parallax de fondo), `PlaySubMenu`,
`SlotSelectMenu` (3 slots, confirmación de sobrescritura), `PauseMenu`,
`BestiaryMenu` (galería de enemigos con flechas), `OptionsMenu` (modo pantalla,
resolución, relación de aspecto, límite de FPS, volumen general/música, aplicar,
volver).

- **`PauseMenu` es contextual:** `options` es una *property* que depende de
  `self.in_combat`. En combate añade **"Guardar y regresar al mapa"** además de
  "Guardar y Salir al menú principal". Se configura con `set_context(in_combat)`
  al pausar (True desde COMBAT, False desde MAP).
- **`OptionsMenu`** devuelve un dict `{"action":"APPLY"|"BACK", "res","fullscreen",
  "aspect_mode","gen_vol","mus_vol","fps_limit"}` que `main.py` aplica y guarda.
  Construye la lista de resoluciones desde `pygame.display.list_modes()` + una lista
  común.
- **`frame_delta(obj)`** (helper de módulo): devuelve "frames a 60 fps" transcurridos
  por tiempo real; se usa en los `draw()` de los menús (`self.time += frame_delta(self)`)
  para que las animaciones de UI (latido de títulos, pulso del ícono de guardado,
  duración de notificaciones) NO se aceleren a FPS altos.

---

## 17. Transiciones (`transitions.py`)

`render_transition(surface, old_surf, new_surf, t_type, progress, width, height)`.
Tipos: `"FADE"` (default), `"SLIDE_LEFT"`, `"SLIDE_RIGHT"`, `"CIRCLE"`, `"PIXELATE"`.
En `main.py`, `trans_state` guarda `{active, progress, speed, type, old_surf}`;
`trigger_transition(target, t_type, speed)` inicia la transición y cambia
`game_state`. El progreso avanza escalado por `render_scale` (independiente del FPS).

---

## 18. Tutorial (`tutorial.py`)

`TutorialState` con `TutorialPhase`: `TEXT_MAP(0)` → `COMBAT_PRACTICE` →
`TEXT_ENEMIES` → (va al Bestiario) → `OUTRO(4)` → `DONE`. Enseña mapa, energía,
vida (corazones), disparo y bestiario. `update()` corre en la simulación a 60 Hz
(sus timers son frame-based correctos). Devuelve acciones como `"GO_TO_BESTIARY"` y
`"FINISH_TUTORIAL"`.

---

## 19. Controles y teclas de depuración

**Mapa:** WASD/flechas o mouse para navegar/seleccionar; `ENTER` o doble clic
izquierdo para entrar; **clic derecho + arrastrar** = mover cámara; `ESPACIO`/`R` =
descansar (avanza semestre, recarga energía); `ESC` = pausa.
**Combate:** WASD mover; disparar con mouse o flechas; `ESC` pausa.
**Bestiario:** flechas / rueda para navegar.
**Debug (combate):** `F1` colisiones, `F2` editor de colisiones, `F3` etiquetas,
`F4` rutas de IA. **Global:** `F11` fullscreen.

---

## 20. Prácticas y reglas (resumen de `AGENTS.md`)

1. **Colisiones disociadas del arte:** usar `pygame.Rect` lógicos, nunca los píxeles
   de las imágenes.
2. **Escalado relativo:** todo se dibuja en el lienzo 1280×720 y la cámara/escalado
   traduce a la pantalla real.
3. **Persistencia de eventos:** no limpiar el estado de UI de forma abrupta.
4. **Independencia en JSON:** mapas/colisiones se definen en `levels/*.json`, nunca
   hardcodeados en el bucle principal.

---

## 21. Gotchas / notas para no romper nada

- **`update_unlocks()` tiene un desbloqueo total temporal** (§3.2). Todo el mapa
  aparece jugable ahora mismo.
- **No conviertas el juego a delta-time variable.** Todo es frame-based y la
  simulación fija a 60 Hz lo mantiene correcto; el sistema de colisiones y la IA de
  salto/pathfinding del MiniBoss están calibrados a pasos discretos de 60 Hz.
- **No muevas posiciones de nodos ni cambies `self.edges`/`get_room_at`** salvo que
  sea el objetivo. La geometría del mapa es estática.
- **El lienzo virtual es 1280×720.** No hardcodees para otras resoluciones; el
  letterbox y `window_to_virtual` se encargan del resto.
- Fuentes: `assets/fonts/VT323-Regular.ttf` (texto) y
  `assets/packs/webfontkit-BoldPixels/boldpixels.ttf` (títulos). Hay fallback a
  fuentes del sistema si no cargan.

---

_Mantén este documento sincronizado con el código. Es la fuente de verdad para IAs
y desarrolladores que entren al proyecto._
