"""Test de aceptacion: el disparo del jugador nace en el frame de impacto.

Usa los assets reales del jugador. El cooldown sigue siendo de gameplay
(se fija al pulsar), pero la bala se crea en el evento "shoot".
"""
import math

import pygame
import pytest

from player import Player, ATTACK_IMPACT_FRAME, WALK_ANIMATION_SPEED
from collision_manager import CollisionManager

TICK = 1000.0 / 60.0
W, H = 800, 600


@pytest.fixture
def player():
    return Player(400, 300, scale=1.0)


def step_until_bullet(player, max_ticks=60):
    """Avanza el controller tick a tick; devuelve en que tick aparecio la bala."""
    for t in range(max_ticks):
        player.controller.update(dt_ms=TICK)
        if player.bullets:
            return t
    return None


def test_disparar_no_crea_la_bala_de_inmediato(player):
    player.shoot_angle(0.0)
    assert player.bullets == []              # aun no
    assert player.shoot_cooldown == 15       # el cooldown si es inmediato
    assert player.controller.current == "attack"


def test_la_bala_nace_en_el_frame_de_impacto(player):
    player.shoot_angle(0.0)
    appeared = step_until_bullet(player)
    assert appeared is not None, "la bala nunca se creo"
    # A speed 0.52, el frame ATTACK_IMPACT_FRAME se cruza en ~impact/0.52 ticks.
    expected = math.ceil(ATTACK_IMPACT_FRAME / 0.52)
    assert abs(appeared - expected) <= 2


def test_la_bala_sale_con_el_angulo_pedido(player):
    player.shoot_angle(math.pi)  # hacia la izquierda
    step_until_bullet(player)
    bullet = player.bullets[0]
    assert bullet.dx < 0 and abs(bullet.dy) < 1e-6


def test_solo_una_bala_por_disparo(player):
    player.shoot_angle(0.0)
    for _ in range(20):
        player.controller.update(dt_ms=TICK)
    assert len(player.bullets) == 1


def test_cooldown_bloquea_rafaga(player):
    player.shoot_angle(0.0)
    player.shoot_angle(0.0)  # ignorado: cooldown activo
    assert player.shoot_cooldown == 15
    step_until_bullet(player)
    assert len(player.bullets) == 1


def test_moverse_no_interrumpe_el_ataque(player):
    player.shoot_angle(0.0)
    # El jugador sigue caminando mientras dispara: el clip base cambia pero
    # el one-shot de ataque no debe ser interrumpido.
    player.move_vector(1, 0, W, H)
    assert player.controller.current == "attack"
    appeared = step_until_bullet(player)
    assert appeared is not None


def test_al_terminar_el_ataque_vuelve_al_base(player):
    player.move_vector(1, 0, W, H)  # base = move
    player.shoot_angle(0.0)
    for _ in range(30):
        player.controller.update(dt_ms=TICK)
    assert player.controller.current == "move"
    assert not player.controller.busy


def test_sin_moverse_el_base_es_idle(player):
    player.move_vector(0, 0, W, H)
    assert player.controller.current == "idle"


def test_caminar_tiene_un_ritmo_legible(player):
    player.move_vector(1, 0, W, H)
    player.controller.update(dt_ms=TICK)
    assert player.animator.current_frame == pytest.approx(WALK_ANIMATION_SPEED)


def test_bala_choca_con_solido_delgado_sin_atravesarlo(player):
    player.shoot_angle(0.0)
    step_until_bullet(player)
    bullet = player.bullets[0]
    bullet.x = 100
    bullet.y = 200
    bullet.dx = 40
    bullet.dy = 0
    collision_manager = CollisionManager([pygame.Rect(120, 150, 2, 100)])

    impacts = player.update_bullets(W, H, collision_manager)

    assert player.bullets == []
    assert len(impacts) == 1
    assert impacts[0]["collider"] == pygame.Rect(120, 150, 2, 100)
    assert impacts[0]["x"] < 120


def test_draw_no_falla_y_usa_el_controller(player):
    surface = pygame.Surface((W, H))
    player.shoot_angle(0.0)
    for _ in range(10):
        player.draw(surface)  # reloj real; solo comprobamos que no truena
    assert player.animator.current_row in (0, 1, 2)
