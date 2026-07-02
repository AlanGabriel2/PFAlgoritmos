# Mega-Calabozo DAG

**Un RPG top-down 2D estilo pixel art donde recorres tu malla curricular convertida en un calabozo.**
Desarrollado en **Python + Pygame**, combina un motor de grafos (DAG) con arenas de combate *bullet-hell*: cada materia de la carrera es una sala que debes "limpiar" para aprobarla, respetando los prerrequisitos.

> Proyecto académico de Algoritmos: la malla de **Ingeniería en Sistemas de Información** se modela como un **Grafo Dirigido Acíclico (DAG)** y el juego lo vuelve jugable.

---

## La idea central: la malla curricular como un DAG

Toda la carrera (59 materias) se representa como un **grafo dirigido acíclico**:

- **Cada nodo es una materia.** Su ID codifica el semestre (p. ej. `TIP01BFT03` → semestre 01, `TIP10TEMTT1` → proyecto de titulación).
- **Cada arista es un prerrequisito.** Si `A → B`, entonces `A` es requisito de `B`.
- El grafo es **acíclico** por naturaleza (no puedes cursar algo que depende de sí mismo), lo que permite aplicar algoritmos clásicos de grafos.

El objetivo del jugador es llegar desde las materias iniciales (sin prerrequisitos) hasta el **nodo final de titulación**, que solo se desbloquea al aprobar todo lo demás.

### Algoritmos que resuelven el DAG (`dag_engine.py`)

El motor `DagEngine` aplica varios algoritmos sobre el grafo:

| Algoritmo | Para qué se usa |
|-----------|-----------------|
| **Ordenamiento topológico** (Kahn / grados de entrada) | Procesar las materias en un orden válido según sus dependencias. |
| **Programación dinámica sobre el orden topológico** | Calcular el *camino más largo* del grafo = **tiempo récord ideal** (`par_score`), es decir, el mínimo de semestres teóricos para graduarse. |
| **Búsqueda del camino crítico (DFS)** | Identificar las rutas críticas de la carrera y colorearlas (hasta 8 colores distintos) para que el jugador vea los caminos más largos/importantes. |
| **Desbloqueo por prerrequisitos** | Una materia pasa de `LOCKED` a `UNLOCKED` solo cuando **todos** sus predecesores están `CLEANED` (aprobados). El nodo de titulación se abre al completar el resto. |

Cada nodo tiene tres estados: **`LOCKED`** (bloqueada), **`UNLOCKED`** (disponible) y **`CLEANED`** (aprobada), que se reflejan visualmente en el mapa.

---

## 🕹️ Cómo funciona el juego

### Navegación por el mapa (DAG)
El mapa dibuja el grafo completo: nodos como salas y aristas como conexiones de prerrequisito (las del camino crítico van coloreadas). Puedes:
- Moverte con **teclado o mouse** y seleccionar materias disponibles.
- **Arrastrar la cámara** para explorar el grafo (con límites para no salirte al vacío).
- Ver un **tooltip** con el nombre de la materia y sus prerrequisitos.

### Progresión: energía y semestres
- Entrar a una materia cuesta **1 de energía**.
- Cuando te quedas sin energía, **descansas** para avanzar de semestre y recargarla (representa el paso de un periodo lectivo al siguiente).
- Solo puedes cursar una materia si sus prerrequisitos ya fueron aprobados.

### Combate (arenas *bullet-hell* / shooter top-down)
"Aprobar" una materia = **superar su arena de combate**:
- Te mueves en 8 direcciones y disparas (mouse o flechas) contra enemigos temáticos: **Bugs**, **Código Spaghetti**, **Memory Leaks** y **Deadlines**.
- En los nodos del **camino crítico** aparecen **Mini-Bosses** (parciales), y el nodo final trae al **Mega-Boss** (titulación), con IA de persecución y ataques de área.
- Las colisiones y la física usan capas lógicas (`pygame.Rect`), no los píxeles de las imágenes.

### Extras
- **Bestiario**: colección de enemigos descubiertos.
- **Tutorial** guiado para nuevos jugadores.
- **Guardado automático** en JSON tras superar cada sala, con 3 ranuras (*slots*).

---

## Controles

**En el mapa**
- Mover / seleccionar: `WASD` o flechas · o el **mouse**
- Entrar a la materia: `ENTER` (o doble clic)
- Arrastrar cámara: **clic derecho + arrastrar**
- Descansar (avanzar de semestre): `ESPACIO` / `R`
- Pausa: `ESC`

**En combate**
- Mover: `WASD`
- Disparar: **mouse** o **flechas**
- Pausa: `ESC`

**Global**
- Pantalla completa: `F11`

---

## ⚙️ Requisitos e instalación

Necesitas **Python 3.10+** y **Pygame** (recomendado `pygame-ce`).

```bash
# 1. Clonar el repositorio
git clone https://github.com/AlanGabriel2/PFAlgoritmos.git
cd PFAlgoritmos

# 2. (Opcional) crear un entorno virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Instalar dependencias
pip install pygame-ce

# 4. Ejecutar
python main.py
```

---

## ⚙️ Opciones configurables

Desde el menú de **Opciones** puedes ajustar:
- **Resolución** y **modo de pantalla** (ventana / pantalla completa).
- **Relación de aspecto** (16:9 completo o llenar).
- **Límite de FPS**: `30 / 60 / 120 / 144 / 165 / 240 / Sin límite`.
- **Volumen** general y de música.

El juego renderiza internamente a una resolución base de **1280×720** y la escala a cualquier resolución con **letterbox** (barras negras) manteniendo la proporción 16:9, sin deformar ni cortar contenido. La **lógica corre a 60 Hz fijos** (*fixed timestep*) independientemente del FPS de render, así que el juego nunca se acelera ni se ralentiza al cambiar el límite de FPS.

---

## 📁 Estructura del proyecto

```
PFAlgoritmos/
├── main.py               # Punto de entrada: máquina de estados, bucle principal
│                         # (fixed timestep), render, escalado/resolución y HUD del mapa
├── dag_engine.py         # DagEngine: DAG, orden topológico, camino crítico (DP), desbloqueos
├── data.py               # SUBJECTS: las 59 materias y sus prerrequisitos
├── map_generator.py      # MapGenerator/Room: layout del grafo por semestres, dibujo de nodos/aristas
├── player.py             # Player y proyectiles del jugador
├── enemy.py              # Jerarquía de enemigos (Bug, Spaghetti, MemoryLeak, Deadline, MiniBoss, Boss)
├── enemy_ai.py           # Comportamiento/persecución de enemigos
├── pathfinding.py        # Búsqueda de ruta (A*) para la navegación en combate
├── level.py              # Carga de arenas de combate desde levels/*.json
├── collision_manager.py  # Colisiones por Rect y resolución por ejes (anti-clipping)
├── collision_editor.py   # Herramienta interna para dibujar colisiones
├── tutorial.py           # Flujo del tutorial
├── menu.py               # Pantallas y menús (título, principal, opciones, pausa, bestiario, slots)
├── animator.py           # Animación de spritesheets (independiente del framerate)
├── save_manager.py       # Guardado/carga en JSON (global y por slot)
├── transitions.py        # Transiciones visuales entre estados (fade, slide, etc.)
├── assets/               # Fuentes pixel art, fondos, sprites de enemigos/jugador y UI
├── levels/               # Definiciones de arenas (.json)
└── saves/                # Partidas guardadas (autogeneradas)
```

---

##  Arquitectura técnica (resumen)

- **Máquina de estados** en `main.py`: `DISCLAIMER → TITLE → MAIN_MENU → SLOT_SELECT → MAP → COMBAT → PAUSE / TUTORIAL / BESTIARY / OPTIONS → WIN / GAME_OVER`.
- **Bucle a paso fijo (fixed timestep):** la simulación avanza en pasos fijos de 1/60 s y el render se desacopla al límite de FPS elegido.
- **Escalado por superficie virtual:** todo se dibuja sobre un lienzo de 1280×720 que se escala a la ventana real con letterbox 16:9; las coordenadas del mouse se transforman a ese espacio.
- **Colisiones desacopladas del arte:** obstáculos definidos como `Rect` en JSON, con resolución de colisión por ejes.
- **Persistencia:** opciones globales y progreso por ranura en archivos JSON.

---

##  Notas

- Los mapas y colisiones de las arenas se definen en `levels/*.json` (no se hardcodean en el bucle principal).
- Fuente pixel art principal: **VT323**; títulos con **BoldPixels**.

---

*Proyecto Final de Algoritmos — Ingeniería en Sistemas de Información.*
