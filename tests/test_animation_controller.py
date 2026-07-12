"""Tests del AnimationController: prioridades, one-shots, eventos y retorno al base.

Deterministas: hojas sinteticas + dt inyectado (sin reloj real).
"""
import pytest

from animation_controller import AnimationClip, AnimationController
from animator import Animator
from test_animator import CELL, TICK, make_sheet


def build_controller(tmp_path, extra_clips=None, base="idle"):
    """Animator sintetico de 5 estados x 4 frames + clips tipicos.

    Los clips de accion usan speed=1.0: un frame exacto por tick de 60 Hz.
    """
    sheet = make_sheet(tmp_path / "sheet.png", rows=5, cols=4)
    animator = Animator(sheet, CELL, CELL, rows=5, cols=4, animation_speed=1.0)
    clips = {
        "idle": AnimationClip(state=0, loop=True, priority=0),
        "move": AnimationClip(state=1, loop=True, priority=0),
        "attack": AnimationClip(state=2, loop=False, priority=30, speed=1.0,
                                events={1: ("charge",), 2: ("shoot", "camera_shake")}),
        "hurt": AnimationClip(state=3, loop=False, priority=50, speed=1.0),
        "death": AnimationClip(state=4, loop=False, priority=100, speed=1.0,
                               hold_last=True),
    }
    clips.update(extra_clips or {})
    return AnimationController(animator, clips, base=base)


def bind_counter(controller, event):
    counts = {"n": 0}
    controller.bind(event, lambda: counts.__setitem__("n", counts["n"] + 1))
    return counts


# ---- validacion ----

def test_clip_con_estado_sin_frames_falla_al_construir(tmp_path):
    sheet = make_sheet(tmp_path / "s.png", rows=2, cols=4)
    animator = Animator(sheet, CELL, CELL, rows=2, cols=4)
    with pytest.raises(ValueError, match="estado 7"):
        AnimationController(animator, {"idle": AnimationClip(state=7)}, base="idle")


def test_evento_fuera_de_rango_falla_al_construir(tmp_path):
    sheet = make_sheet(tmp_path / "s.png", rows=2, cols=4)
    animator = Animator(sheet, CELL, CELL, rows=2, cols=4)
    clips = {"idle": AnimationClip(state=0, events={9: ("x",)})}
    with pytest.raises(ValueError, match="frame 9"):
        AnimationController(animator, clips, base="idle")


def test_clip_inexistente_da_mensaje_claro(tmp_path):
    controller = build_controller(tmp_path)
    with pytest.raises(KeyError, match="'volar'.*disponibles"):
        controller.play("volar")


# ---- base y proteccion contra reinicios ----

def test_pedir_el_base_cada_tick_no_reinicia(tmp_path):
    controller = build_controller(tmp_path, base="move")
    for _ in range(3):
        controller.set_base("move")
        controller.update(dt_ms=TICK)
    assert controller.animator.current_frame == pytest.approx(3.0)


def test_cambiar_base_cambia_el_clip_visible(tmp_path):
    controller = build_controller(tmp_path)
    assert controller.current == "idle"
    controller.set_base("move")
    assert controller.current == "move"
    assert controller.animator.current_row == 1


# ---- prioridades ----

def test_oneshot_no_es_pisado_por_el_base(tmp_path):
    controller = build_controller(tmp_path)
    assert controller.play("attack")
    # El game loop sigue pidiendo move/idle cada tick: no debe interrumpir.
    controller.set_base("move")
    assert not controller.play("move")
    controller.update(dt_ms=TICK)
    assert controller.current == "attack"


def test_hurt_interrumpe_attack(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    assert controller.play("hurt")
    assert controller.current == "hurt"


def test_death_interrumpe_todo(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    controller.play("hurt")
    assert controller.play("death")
    assert controller.current == "death"


def test_prioridad_igual_no_interrumpe(tmp_path):
    other = {"attack_b": AnimationClip(state=3, loop=False, priority=30, speed=1.0)}
    controller = build_controller(tmp_path, extra_clips=other)
    controller.play("attack")
    assert not controller.play("attack_b")
    assert controller.current == "attack"


def test_repetir_attack_no_reinicia_sin_flag(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    controller.update(dt_ms=TICK * 2)
    assert not controller.play("attack")
    assert controller.animator.current_frame == pytest.approx(2.0)


def test_restart_explicito_reinicia(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    controller.update(dt_ms=TICK * 2)
    assert controller.play("attack", restart=True)
    assert controller.animator.current_frame == 0.0


# ---- eventos ----

def test_evento_se_dispara_exactamente_una_vez(tmp_path):
    controller = build_controller(tmp_path)
    charge = bind_counter(controller, "charge")
    shoot = bind_counter(controller, "shoot")
    shake = bind_counter(controller, "camera_shake")
    controller.play("attack")
    for _ in range(4):  # pasada completa del one-shot, tick a tick
        controller.update(dt_ms=TICK)
    assert (charge["n"], shoot["n"], shake["n"]) == (1, 1, 1)


def test_eventos_no_se_pierden_si_el_dt_salta_frames(tmp_path):
    controller = build_controller(tmp_path)
    charge = bind_counter(controller, "charge")
    shoot = bind_counter(controller, "shoot")
    controller.play("attack")
    controller.update(dt_ms=TICK * 3)  # 0 -> 3 de un golpe: cruza 1 y 2
    assert (charge["n"], shoot["n"]) == (1, 1)


def test_eventos_de_loop_se_repiten_en_cada_vuelta(tmp_path):
    steps = {"move": AnimationClip(state=1, loop=True, priority=0, speed=1.0,
                                   events={0: ("step",), 2: ("step",)})}
    controller = build_controller(tmp_path, extra_clips=steps)
    controller.set_base("move")
    step = bind_counter(controller, "step")
    controller.set_base("move")  # ya activo: no reinicia ni re-emite
    base = step["n"]
    for _ in range(8):  # dos vueltas completas de 4 frames
        controller.update(dt_ms=TICK)
    assert step["n"] - base == 4  # frames 2, 0, 2, 0


def test_evento_de_frame_cero_al_arrancar(tmp_path):
    clips = {"spawn": AnimationClip(state=3, loop=False, priority=90, speed=1.0,
                                    events={0: ("appear",)})}
    controller = build_controller(tmp_path, extra_clips=clips)
    appear = bind_counter(controller, "appear")
    controller.play("spawn")
    assert appear["n"] == 1


def test_finished_se_emite_una_vez(tmp_path):
    controller = build_controller(tmp_path)
    done = bind_counter(controller, "attack:finished")
    controller.play("attack")
    for _ in range(10):
        controller.update(dt_ms=TICK)
    assert done["n"] == 1


def test_dt_cero_no_avanza_ni_emite(tmp_path):
    controller = build_controller(tmp_path)
    shoot = bind_counter(controller, "shoot")
    controller.play("attack")
    controller.update(dt_ms=TICK)  # frame 1
    frozen = controller.animator.current_frame
    for _ in range(10):  # hit-stop
        controller.update(dt_ms=0)
    assert controller.animator.current_frame == frozen
    assert shoot["n"] == 0


# ---- fin de one-shot ----

def test_al_terminar_vuelve_al_base_vigente(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    controller.set_base("move")  # cambio de base durante el ataque
    for _ in range(4):
        controller.update(dt_ms=TICK)
    assert controller.current == "move"
    assert not controller.busy


def test_hold_last_congela_el_ultimo_frame(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("death")
    for _ in range(6):
        controller.update(dt_ms=TICK)
    assert controller.current == "death"
    assert controller.animator.current_frame == 3.0
    controller.update(dt_ms=TICK * 4)
    assert controller.animator.current_frame == 3.0
    # Su prioridad sigue bloqueando: nada lo saca del ultimo frame.
    assert not controller.play("attack")
    assert not controller.play("hurt")
    controller.set_base("move")
    assert controller.current == "death"


def test_encadenar_desde_finished(tmp_path):
    # Patron ANTICIPATE -> ATTACK -> RECOVER: el callback de finished encadena.
    recover = {"recover": AnimationClip(state=3, loop=False, priority=10, speed=1.0)}
    controller = build_controller(tmp_path, extra_clips=recover)
    controller.bind("attack:finished", lambda: controller.play("recover"))
    controller.play("attack")
    for _ in range(4):
        controller.update(dt_ms=TICK)
    assert controller.current == "recover"
    for _ in range(4):
        controller.update(dt_ms=TICK)
    assert controller.current == "idle"


def test_stop_corta_y_vuelve_al_base(tmp_path):
    controller = build_controller(tmp_path)
    controller.play("attack")
    controller.stop()
    assert controller.current == "idle"


def test_busy_refleja_el_oneshot(tmp_path):
    controller = build_controller(tmp_path)
    assert not controller.busy
    controller.play("attack")
    assert controller.busy
    for _ in range(4):
        controller.update(dt_ms=TICK)
    assert not controller.busy


def test_speed_del_clip_sobrescribe_al_animator(tmp_path):
    # El animator por defecto va a 1.0; el clip lento debe imponerse.
    slow = {"cast": AnimationClip(state=3, loop=False, priority=40, speed=0.25)}
    controller = build_controller(tmp_path, extra_clips=slow)
    controller.play("cast")
    controller.update(dt_ms=TICK)
    assert controller.animator.current_frame == pytest.approx(0.25)
