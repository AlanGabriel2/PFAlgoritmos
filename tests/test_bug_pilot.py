"""Piloto de migracion: BugEnemy animado por AnimationController.

Usa los assets reales del repo (hojas v2 del bug), asi que tambien sirve de
smoke test de carga de esas hojas.
"""
import pygame
import pytest

from enemy import BugEnemy, SpaghettiEnemy
from collision_manager import CollisionManager

TICK = 1000.0 / 60.0
W, H = 800, 600


@pytest.fixture
def bug():
    return BugEnemy(400, 300, scale=1.0)


def boxed_in(bug):
    """Colliders pegados a los cuatro lados del rect del bug: no puede moverse."""
    r = bug.rect
    return CollisionManager([
        pygame.Rect(r.left - 10, r.top - 10, r.width + 20, 10),   # arriba
        pygame.Rect(r.left - 10, r.bottom, r.width + 20, 10),     # abajo
        pygame.Rect(r.left - 10, r.top - 10, 10, r.height + 20),  # izquierda
        pygame.Rect(r.right, r.top - 10, 10, r.height + 20),      # derecha
    ])


def test_arranca_en_move(bug):
    assert bug.controller.current == "move"


def test_persigue_con_clip_move(bug):
    bug.update(700, 300, W, H)
    assert bug.controller.current == "move"
    assert bug.x > 400  # se movio hacia el jugador


def test_bloqueado_pasa_a_idle(bug):
    cm = boxed_in(bug)
    for _ in range(5):
        bug.update(700, 300, W, H, collision_manager=cm)
    assert bug.controller.current == "idle"


def test_ataque_es_oneshot_y_vuelve_al_base(bug):
    bug.notify_attack()
    assert bug.controller.current == "attack"
    # La IA sigue pidiendo move cada tick: no debe pisar el ataque.
    bug.update(700, 300, W, H)
    assert bug.controller.current == "attack"
    # 8 frames a 0.28/tick ~= 29 ticks; con margen debe haber terminado.
    for _ in range(40):
        bug.controller.update(dt_ms=TICK)
    assert bug.controller.current in ("move", "idle")
    assert not bug.controller.busy


def test_draw_avanza_por_el_controller(bug):
    surface = pygame.Surface((W, H))
    bug.draw(surface)  # primer draw inicializa el reloj interno
    # El state numerico heredado ya no manda: aunque la IA lo deje en 1,
    # el clip activo es el que decide la fila del animator.
    bug.notify_attack()
    bug.state = 1
    bug.draw(surface)
    assert bug.animator.current_row == 2  # fila del clip attack


def test_notify_attack_dispara_one_shot_en_enemigos_migrados():
    spaghetti = SpaghettiEnemy(100, 100, scale=1.0)
    spaghetti.notify_attack()
    assert spaghetti.controller.current == "attack"
