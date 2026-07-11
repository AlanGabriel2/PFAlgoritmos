"""Diagnóstico de mando: muestra en vivo lo que reporta tu control.

Uso:  python tools/diagnose_gamepad.py
Mueve AMBOS sticks, presiona gatillos, D-pad y botones durante ~20 segundos.
Al final imprime un resumen con el máximo registrado por eje en las dos APIs
(joystick crudo y Game Controller normalizado). Copia TODA la salida.
"""
import time

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except (ImportError, pygame.error):
    sdl_controller = None

DURATION_S = 20
AXIS_NAMES = ["LEFTX", "LEFTY", "RIGHTX", "RIGHTY", "TRIGL", "TRIGR"]


def main():
    pygame.init()
    pygame.joystick.init()
    # Se necesita una ventana para que Windows entregue la entrada del mando de forma fiable.
    pygame.display.set_mode((420, 120))
    pygame.display.set_caption("Diagnóstico de mando - mueve sticks y botones")

    if sdl_controller is not None and not sdl_controller.get_init():
        sdl_controller.init()

    count = pygame.joystick.get_count()
    print(f"\nDispositivos detectados: {count}")
    if count == 0:
        print("No hay mandos. Conéctalo y vuelve a ejecutar.")
        return

    joys, ctrls = [], []
    for i in range(count):
        j = pygame.joystick.Joystick(i)
        j.init()
        joys.append(j)
        is_ctrl = sdl_controller.is_controller(i) if sdl_controller else False
        c = None
        if is_ctrl:
            try:
                c = sdl_controller.Controller(i)
                if not c.get_init():
                    c.init()
            except Exception as e:
                print(f"  [{i}] Controller NO se pudo abrir: {e!r}")
                c = None
        ctrls.append(c)
        print(
            f"  [{i}] {j.get_name()!r} | instance_id={j.get_instance_id()} | "
            f"ejes={j.get_numaxes()} botones={j.get_numbuttons()} hats={j.get_numhats()} | "
            f"is_controller={is_ctrl} | controller_abierto={c is not None}"
            + (f" attached={c.attached()}" if c is not None else "")
        )

    max_raw = [[0.0] * j.get_numaxes() for j in joys]
    max_ctrl = [[0.0] * 6 for _ in joys]
    buttons_seen = [set() for _ in joys]
    events_seen = set()

    print(f"\nMueve sticks/gatillos/botones. Midiendo {DURATION_S} segundos...")
    t_end = time.time() + DURATION_S
    last_print = 0.0
    clock = pygame.time.Clock()
    while time.time() < t_end:
        for ev in pygame.event.get():
            if ev.type in (pygame.JOYAXISMOTION, pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION,
                           pygame.CONTROLLERAXISMOTION, pygame.CONTROLLERBUTTONDOWN):
                events_seen.add(pygame.event.event_name(ev.type))
            if ev.type == pygame.JOYBUTTONDOWN:
                for idx, j in enumerate(joys):
                    if j.get_instance_id() == ev.instance_id:
                        buttons_seen[idx].add(ev.button)

        for idx, j in enumerate(joys):
            for a in range(j.get_numaxes()):
                v = j.get_axis(a)
                if abs(v) > abs(max_raw[idx][a]):
                    max_raw[idx][a] = v
            c = ctrls[idx]
            if c is not None:
                for a in range(6):
                    try:
                        v = c.get_axis(a) / 32767.0
                    except Exception:
                        v = 0.0
                    if abs(v) > abs(max_ctrl[idx][a]):
                        max_ctrl[idx][a] = v

        now = time.time()
        if now - last_print >= 2.0:
            last_print = now
            j = joys[0]
            raw_now = " ".join(f"{j.get_axis(a):+.2f}" for a in range(j.get_numaxes()))
            line = f"  crudo[0]: {raw_now}"
            if ctrls[0] is not None:
                ctrl_now = " ".join(f"{ctrls[0].get_axis(a) / 32767.0:+.2f}" for a in range(6))
                line += f" | ctrl[0]: {ctrl_now}"
            print(line)
        clock.tick(60)

    print("\n===== RESUMEN (máximo absoluto visto por eje) =====")
    for idx, j in enumerate(joys):
        print(f"\n[{idx}] {j.get_name()!r}")
        print("  Ejes crudos:  " + " ".join(f"a{a}={v:+.2f}" for a, v in enumerate(max_raw[idx])))
        if ctrls[idx] is not None:
            print("  Controller:   " + " ".join(f"{AXIS_NAMES[a]}={v:+.2f}" for a, v in enumerate(max_ctrl[idx])))
        else:
            print("  Controller:   (no abierto)")
        print(f"  Botones presionados (crudos): {sorted(buttons_seen[idx]) or 'ninguno'}")
    print(f"\nTipos de evento vistos: {sorted(events_seen) or 'ninguno'}")
    print("Copia y pega TODO este resumen.")
    pygame.quit()


if __name__ == "__main__":
    main()
