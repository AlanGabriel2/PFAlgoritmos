# Mega-Calabozo DAG - Contexto Técnico del Proyecto

Este documento sirve como un mapa integral de la arquitectura, estructura de archivos y lógicas base implementadas en el proyecto **Mega-Calabozo DAG**. Está diseñado para proporcionar contexto técnico rápido y detallado para cualquier IA o desarrollador que entre al proyecto.

## 1. Descripción General del Proyecto
Es un RPG Top-Down 2D desarrollado enteramente en **Python con Pygame**. La premisa principal es que el jugador debe avanzar por un **Grafo Dirigido Acíclico (DAG)** que representa la malla curricular de la carrera de Ingeniería en Sistemas de Información. 
- Cada nodo es una materia.
- Las aristas representan los pre-requisitos de las materias (8 colores distintos para identificar 8 caminos críticos posibles).
- El jugador debe superar arenas de combate (Shooter/Bullet-Hell Top-Down) para "aprobar" las materias.
- Cuenta con un sistema de progresión, bestiario, configuraciones y guardado local mediante JSON.

---

## 2. Estructura de Directorios y Archivos Base
El directorio raíz contiene todos los scripts modulares del juego.

### Archivos Principales de Python
- `main.py`: Punto de entrada del juego. Controla la máquina de estados principal (`MAIN_MENU`, `MAP`, `COMBAT`, `TUTORIAL`, `BESTIARY`, etc.), el bucle de juego principal (Main Loop), la renderización orquestada, manejo de inputs a nivel global y las transiciones.
- `dag_engine.py`: Contiene la clase `DAGEngine`. Es el cerebro lógico del mapa. Define la topología del grafo, nodos (materias), posiciones (x,y), dependencias, colores de aristas, cálculo de semestre actual, validaciones de nodos desbloqueados e implementa el ordenamiento topológico.
- `menu.py`: Contiene las clases de interfaz gráfica: `MainMenu`, `SlotSelectMenu`, `PauseMenu`, `BestiaryMenu`, `OptionsMenu` y pantallas de inicio.
- `player.py`: Contiene la clase `Player` / `CombatPlayer`. Lógica de movimiento en 8 direcciones (WASD), mecánicas de disparo (mouse o flechas), vida (HP), cooldowns de ataque, hitbox (radio de colisión) y animación.
- `enemy.py`: Sistema de herencia de enemigos (`Enemy` como base, luego subclases `BugEnemy`, `SpaghettiEnemy`, `MemoryLeakEnemy`, `DeadlineEnemy`, `MiniBoss`, `Boss`). Contienen lógicas de actualización, físicas, cooldown de ataque y generación de proyectiles.
- `enemy_ai.py` / `pathfinding.py`: Lógica avanzada de persecución, comportamiento y algoritmos de búsqueda de ruta (A*) si están implementados para la navegación en el mapa de combate.
- `level.py`: Maneja el cargado del escenario (arena de combate). Contiene `load_combat_level`, cargando configuraciones JSON y los fondos estáticos de acuerdo con el nivel del semestre (ej. `s1.png` a `s10.png`).
- `collision_manager.py`: Posee la clase `CollisionManager`. Extrae datos JSON del nivel actual y define obstáculos estáticos `pygame.Rect`. Aplica algoritmos de resolución de colisiones por ejes (`move_and_collide`) para evitar clipping del jugador o enemigos en las paredes/obstáculos.
- `tutorial.py`: Implementa `TutorialState`. Un flujo aislado para jugadores nuevos que enseña a navegar el mapa, consumir energía, disparar y el sistema del Bestiario.
- `save_manager.py`: Clase `SaveManager` que lee y escribe archivos JSON. Administra datos globales (opciones, tutorial) y progreso de Slots de guardado (nodos superados, energía, semestre actual).
- `transitions.py`: Módulos visuales para enmascarar transiciones entre estados (Fade, Slide, Pixelate).
- `collision_editor.py` / `map_generator.py`: Herramientas de desarrollo internas para dibujar colisiones visualmente y generar los JSON de los niveles.

### Carpetas de Recursos (Assets)
`assets/`
- **`fonts/`**: `VT323-Regular.ttf` (Fuente pixel art usada globalmente) y subcarpeta de webfontkit.
- **`images/backgrounds/`**: Fondos de las batallas correspondientes a los 10 semestres (`s1.png` ... `s10.png`), el fondo del grafo (`map_bg.png`), la portada (`bg_portada.jpg`) y baldosas base (`floor_tile.png`). 
- **`images/enemies/`**: Spritesheets de las variantes de enemigos (ej. `bug_sheet.png`, `boss_sheet.png`, etc.).
- **`images/player/`**: Spritesheets del protagonista (`player_sheet.png`).
- **`images/ui/`**: Recursos de interfaz. Botones, íconos de guardado (`save.png`), corazones animados (`vida_heart.png`), título del juego (`titulo_juego.png`), flechas del bestiario y fondos (`bestiary_bg.png`).

### Otras Carpetas Importantes
- `levels/`: Archivos `.json` (ej. `combat_default.json`) generados por los editores internos que definen el array de rectángulos "solidos" para cada arena.
- `saves/`: Aquí se auto-generan `global_save.json` (progreso general) y `slot_1.json`, etc.

---

## 3. Lógica Fundamental y Arquitectura

### Máquina de Estados (State Machine)
El juego se divide en los siguientes `game_state` controlados en `main.py`:
1. `TITLE`: Pantalla de inicio con "Presiona una tecla".
2. `MAIN_MENU`: Botones Jugar, Tutorial, Opciones, Salir.
3. `SLOT_SELECT`: Cargar o Crear Partida.
4. `MAP`: Navegación visual interactiva en el DAG. Se dibujan nodos y aristas. Se puede hacer pan (clic central) o zoom.
5. `COMBAT`: Bucle activo de Bullet-Hell/Shooter. Se instancian listas de `Enemy`, el jugador, los proyectiles y el `CollisionManager`. 
6. `PAUSE`: Superposición pausada del combate.
7. `TUTORIAL` / `BESTIARY` / `OPTIONS`: Interfaces secundarias.

### Lógica de Combate y Colisiones
- **Movimiento**: Se separan los ejes. Primero se suma a `X`, se chequea colisión con todos los `Rect` devueltos por `CollisionManager.get_colliders()`, si hay impacto se empuja afuera. Luego a `Y`. Así se previene quedar atrapado en esquinas.
- **Combate de Enemigos**: Se eligen enemigos al azar basándose en listas dependiendo si el mapa es crítico (invoca `MiniBoss`) o final (invoca `Boss`).
- **Proyectiles**: Objetos voladores con un vector `(dx, dy)`. Comprueban intersecciones mediante la distancia euclidiana entre el centro del proyectil y el centro (radio) del objetivo `math.hypot(x2-x1, y2-y1) < (r1 + r2)`.

### Lógica de Progresión (DAG Engine)
- Variables Clave: `semester_counter`, `energy`, `max_energy`.
- Para cursar una materia, su nodo requiere `energy >= 1`.
- Si `energy == 0`, el jugador pulsa 'Descansar'. Esto incrementa `semester_counter` y recarga la `energy` (representando el paso al siguiente periodo lectivo).
- Un nodo solo se puede jugar si todos sus nodos "predecesores" (materias requisitos) están en la lista de nodos "aprobados".

### Renderizado UI Dinámico
Se emplea `pygame.transform.scale` y `pygame.transform.smoothscale` para que elementos como el Menú, el Bestiario y las Opciones no se distorsionen groseramente. Además se calculan Aspect Ratios y relaciones desde la clase de configuración (escalado global, padding dinámico para monitores distintos).

---

## 4. Prácticas y Reglas del Proyecto (AGENTS.md)
*NOTA: Siempre revisar estas reglas al escribir nuevo código.*
1. **Colisiones Disociadas**: Nunca detectar colisiones usando los píxeles de las imágenes de fondo. Usar capas puramente matemáticas/lógicas (`pygame.Rect`).
2. **Escalado Relativo**: Todas las posiciones del mapa deben usar un sistema coordenado que la cámara traduzca a las coordenadas de renderización del monitor del jugador.
3. **Persistencia de Eventos**: Asegurarse de no limpiar (clear) el estado de UI abruptamente.
4. **Independencia en JSON**: Los mapas y colisiones deben crearse y modificarse en los archivos `levels/*.json`, y NUNCA hardcodearse en el bucle principal.

---
_Generado para mantener coherencia en iteraciones de IA y desarrolladores terceros._
