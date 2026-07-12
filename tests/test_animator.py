"""Tests del Animator: avance por dt inyectado, loop, estados y lienzo comun.

Todas las hojas se generan sinteticamente en tmp_path, asi que los tests no
dependen de los assets del juego y son deterministas (sin reloj real).
"""
import pygame
import pytest

from animator import Animator

TICK = 1000.0 / 60.0  # un tick de 60 Hz en ms
CELL = 32


def make_sheet(path, rows, cols, cell=CELL, half_frames=()):
    """Hoja sintetica: cada celda es un cuadrado opaco de color unico.

    Las celdas listadas en `half_frames` (fila, col) solo pintan la mitad
    superior, para probar recorte de bbox y anclaje inferior.
    """
    surf = pygame.Surface((cell * cols, cell * rows), pygame.SRCALPHA)
    for r in range(rows):
        for c in range(cols):
            h = cell // 2 if (r, c) in half_frames else cell
            surf.fill((20 + 40 * r, 20 + 40 * c, 200, 255),
                      pygame.Rect(c * cell, r * cell, cell, h))
    pygame.image.save(surf, str(path))
    return str(path)


@pytest.fixture
def animator(tmp_path):
    sheet = make_sheet(tmp_path / "sheet.png", rows=2, cols=4)
    return Animator(sheet, CELL, CELL, rows=2, cols=4,
                    animation_speed=0.1, state_speeds={1: 0.5})


def test_dt_inyectado_avanza_frames(animator):
    animator.update(dt_ms=TICK)
    assert animator.current_frame == pytest.approx(0.1)
    animator.update(dt_ms=TICK * 3)
    assert animator.current_frame == pytest.approx(0.4)


def test_dt_cero_congela_la_animacion(animator):
    """Base del hit-stop: dt=0 no debe avanzar ni resetear nada."""
    animator.update(dt_ms=TICK * 5)
    frozen = animator.current_frame
    for _ in range(10):
        animator.update(dt_ms=0)
    assert animator.current_frame == frozen


def test_dt_negativo_no_retrocede(animator):
    animator.update(dt_ms=TICK * 5)
    before = animator.current_frame
    animator.update(dt_ms=-500)
    assert animator.current_frame == before


def test_dt_se_limita_a_100ms(animator):
    animator.update(dt_ms=100)
    capped = animator.current_frame
    animator.current_frame = 0.0
    animator.update(dt_ms=100000)
    assert animator.current_frame == pytest.approx(capped)


def test_loop_envuelve_al_final(animator):
    # speed 0.1 * 45 ticks = 4.5 frames sobre 4 -> envuelve a 0.5
    for _ in range(45):
        animator.update(dt_ms=TICK)
    assert animator.current_frame == pytest.approx(0.5, abs=1e-6)
    assert 0 <= int(animator.current_frame) < 4


def test_set_state_solo_resetea_al_cambiar(animator):
    animator.update(dt_ms=TICK * 20)
    advanced = animator.current_frame
    assert advanced > 0
    # Pedir el mismo estado cada tick (como hace el game loop) no reinicia.
    animator.set_state(0)
    assert animator.current_frame == advanced
    # Cambiar de estado si reinicia.
    animator.set_state(1)
    assert animator.current_frame == 0.0


def test_state_speeds_por_estado(animator):
    animator.set_state(1)  # speed 0.5 en vez de 0.1
    animator.update(dt_ms=TICK)
    assert animator.current_frame == pytest.approx(0.5)


def test_get_current_image_devuelve_el_frame_entero(animator):
    animator.current_frame = 2.7
    assert animator.get_current_image() is animator.frames[0][2]


def test_estado_inexistente_no_revienta(animator):
    animator.set_state(99)
    animator.update(dt_ms=TICK)
    assert animator.get_current_image() is None


def test_hoja_inexistente_usa_fallback_magenta(tmp_path):
    anim = Animator(str(tmp_path / "no_existe.png"), CELL, CELL, rows=2, cols=4)
    image = anim.get_current_image()
    assert image is not None
    assert image.get_at((CELL // 2, CELL // 2)) == pygame.Color(255, 0, 255, 255)


def test_replace_state_comparte_lienzo_y_ancla_abajo(tmp_path, animator):
    # Clip de 4 frames; el ultimo solo ocupa la mitad superior de su celda.
    clip = make_sheet(tmp_path / "clip.png", rows=1, cols=4,
                      half_frames={(0, 3)})
    animator.replace_state_from_sheet(1, clip, rows=1, cols=4, frame_height=CELL)

    sizes = {frame.get_size()
             for frames in animator.frames.values() for frame in frames}
    assert len(sizes) == 1, "todos los estados deben compartir lienzo"

    short = animator.frames[1][3]
    bbox = short.get_bounding_rect()
    assert bbox.bottom == short.get_height(), "el contenido debe anclarse al fondo"
    assert bbox.height == CELL // 2


def test_replace_crece_y_luego_reduce_mantiene_lienzo_uniforme(tmp_path, animator):
    """El lienzo solo crece; un clip posterior mas pequeno se ancla al fondo
    del lienzo grande sin descuadrar los demas frames (guarda la optimizacion
    que evita re-padear cuando el tamaño no cambia)."""
    big = make_sheet(tmp_path / "big.png", rows=1, cols=4, cell=CELL * 2)
    animator.replace_state_from_sheet(1, big, rows=1, cols=4, frame_height=CELL * 2)
    grown = {f.get_size() for frames in animator.frames.values() for f in frames}
    assert len(grown) == 1, "tras crecer, todo comparte el lienzo grande"
    grown_size = grown.pop()

    small = make_sheet(tmp_path / "small.png", rows=1, cols=4, cell=CELL)
    animator.replace_state_from_sheet(0, small, rows=1, cols=4, frame_height=CELL)
    sizes = {f.get_size() for frames in animator.frames.values() for f in frames}
    assert sizes == {grown_size}, "el lienzo no debe encogerse ni fragmentarse"

    small_frame = animator.frames[0][0]
    bbox = small_frame.get_bounding_rect()
    assert bbox.bottom == small_frame.get_height(), "el clip pequeno se ancla al fondo"


def test_update_sin_argumento_sigue_funcionando(animator):
    # Camino de reloj real: solo comprobamos que no falla ni retrocede.
    animator.update()
    first = animator.current_frame
    animator.update()
    assert animator.current_frame >= first
