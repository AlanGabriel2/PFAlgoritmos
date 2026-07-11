"""Gamepad input with stable joystick polling and event fallbacks."""

import math

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except (ImportError, pygame.error):
    sdl_controller = None


MOVE_DEADZONE = 0.22
AIM_DEADZONE = 0.28
NAV_THRESHOLD = 0.55
NAV_INITIAL_DELAY_MS = 320
NAV_REPEAT_MS = 115
TRIGGER_THRESHOLD = 0.38

NAV_CONTEXTS = {"MAIN_MENU", "SLOT_SELECT", "PAUSE", "BESTIARY", "OPTIONS", "MAP"}
BACK_CONTEXTS = {"MAIN_MENU", "SLOT_SELECT", "PAUSE", "BESTIARY", "OPTIONS"}

# Perfiles de ejes CRUDOS (solo fallback: se usan únicamente si el mando no es
# reconocido por la API de Game Controller de SDL, que ya normaliza el layout).
# Los drivers modernos de SDL en Windows (RawInput para Xbox, HIDAPI para PS)
# exponen: sticks en 0-3 y gatillos en 4/5 con reposo en -1.
GENERIC_PROFILE = {
    "axes": {"left_x": 0, "left_y": 1, "right_x": 2, "right_y": 3, "left_trigger": 4, "right_trigger": 5},
    "buttons": {"confirm": 0, "back": 1, "alt": 2, "rest": 3, "select": 6, "pause": 7, "lb": 4, "rb": 5},
    "trigger_rest": -1.0,
}

XBOX_PROFILE = GENERIC_PROFILE

# DualShock/DualSense por HIDAPI (driver moderno de SDL en Windows): sticks en
# 0-3 y gatillos en 4/5; botones 0=Cross 1=Circle 2=Square 3=Triangle.
PLAYSTATION_PROFILE = {
    "axes": {"left_x": 0, "left_y": 1, "right_x": 2, "right_y": 3, "left_trigger": 4, "right_trigger": 5},
    "buttons": {
        "confirm": 0,
        "back": 1,
        "alt": 2,
        "rest": 3,
        "select": 4,
        "pause": 6,
        "lb": 9,
        "rb": 10,
        "dpad_up": 11,
        "dpad_down": 12,
        "dpad_left": 13,
        "dpad_right": 14,
    },
    "trigger_rest": -1.0,
}

CONTROLLER_AXES = {
    "left_x": pygame.CONTROLLER_AXIS_LEFTX,
    "left_y": pygame.CONTROLLER_AXIS_LEFTY,
    "right_x": pygame.CONTROLLER_AXIS_RIGHTX,
    "right_y": pygame.CONTROLLER_AXIS_RIGHTY,
    "left_trigger": pygame.CONTROLLER_AXIS_TRIGGERLEFT,
    "right_trigger": pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
}

CONTROLLER_BUTTONS = {
    "confirm": pygame.CONTROLLER_BUTTON_A,
    "back": pygame.CONTROLLER_BUTTON_B,
    "alt": pygame.CONTROLLER_BUTTON_X,
    "rest": pygame.CONTROLLER_BUTTON_Y,
    "select": pygame.CONTROLLER_BUTTON_BACK,
    "pause": pygame.CONTROLLER_BUTTON_START,
    "lb": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "rb": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    "dpad_up": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "dpad_down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "dpad_left": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "dpad_right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}


def apply_radial_deadzone(x, y, deadzone):
    """Return a direction-preserving vector with a rescaled radial deadzone."""
    magnitude = math.hypot(x, y)
    if magnitude <= deadzone:
        return 0.0, 0.0
    clamped = min(1.0, magnitude)
    scaled = (clamped - deadzone) / (1.0 - deadzone)
    return (x / magnitude) * scaled, (y / magnitude) * scaled


def _profile_for_name(name):
    normalized = name.casefold()
    if any(token in normalized for token in ("playstation", "dualshock", "dualsense", "sony", "ps4", "ps5")):
        return PLAYSTATION_PROFILE, "playstation"
    if "xbox" in normalized or "xinput" in normalized:
        return XBOX_PROFILE, "xbox"
    return GENERIC_PROFILE, "generic"


class _GamepadDevice:
    def __init__(self, joystick, controller=None):
        self.joystick = joystick
        self.controller = controller
        self.instance_id = joystick.get_instance_id()
        self.name = joystick.get_name() or "Gamepad"
        self.profile, detected_kind = _profile_for_name(self.name)
        self.kind = detected_kind if controller is None else self._controller_kind()
        # Estado normalizado alimentado por eventos CONTROLLER* (ver
        # GamepadManager.handle_event). El polling directo (get_axis/get_button)
        # devuelve 0 en algunos equipos aunque los eventos lleguen bien, así que
        # el estado se reconstruye desde los eventos, que sí son confiables.
        self.ctrl_axis_state = {}
        self.ctrl_button_state = {}

    @classmethod
    def open(cls, device_index):
        joystick = pygame.joystick.Joystick(device_index)
        if not joystick.get_init():
            joystick.init()
        # Preferir la API de Game Controller: SDL normaliza ejes y botones para
        # Xbox, PlayStation y la mayoría de mandos, sin depender de perfiles.
        # Se abre con el constructor (no from_joystick) y se garantiza el init:
        # un Controller sin inicializar emite eventos pero get_axis devuelve 0.
        controller = None
        if sdl_controller is not None:
            try:
                if sdl_controller.is_controller(device_index):
                    controller = sdl_controller.Controller(device_index)
                    if not controller.get_init():
                        controller.init()
                    if not controller.attached():
                        controller.quit()
                        controller = None
            except (pygame.error, AttributeError, RuntimeError):
                controller = None
        device = cls(joystick, controller)
        mode = "normalizado (SDL)" if controller is not None else "perfil crudo"
        print(
            f"[gamepad] Conectado: {device.name} | modo {mode} | "
            f"ejes={joystick.get_numaxes()} botones={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
        )
        return device

    def _controller_kind(self):
        normalized = self.name.casefold()
        if any(token in normalized for token in ("playstation", "dualshock", "dualsense", "sony", "ps4", "ps5")):
            return "playstation"
        if "xbox" in normalized or "xinput" in normalized:
            return "xbox"
        return "controller"

    def close(self):
        try:
            if self.controller is not None:
                self.controller.quit()
        except pygame.error:
            pass
        try:
            if self.joystick.get_init():
                self.joystick.quit()
        except pygame.error:
            pass

    def axis(self, name):
        try:
            if self.controller is not None:
                return self.ctrl_axis_state.get(CONTROLLER_AXES[name], 0.0)
            index = self.profile["axes"].get(name)
            if index is None or index >= self.joystick.get_numaxes():
                return 0.0
            return max(-1.0, min(1.0, float(self.joystick.get_axis(index))))
        except (KeyError, pygame.error):
            return 0.0

    def trigger(self, side):
        name = f"{side}_trigger"
        if self.controller is None:
            index = self.profile["axes"].get(name)
            if index is None or index >= self.joystick.get_numaxes():
                return 0.0
        value = self.axis(name)
        if self.controller is not None:
            return max(0.0, value)
        if self.profile.get("trigger_rest", -1.0) < 0:
            return max(0.0, min(1.0, (value + 1.0) * 0.5))
        return max(0.0, min(1.0, value))

    def button(self, name):
        try:
            if self.controller is not None:
                return self.ctrl_button_state.get(CONTROLLER_BUTTONS[name], False)
            index = self.profile["buttons"].get(name)
            if index is None or index >= self.joystick.get_numbuttons():
                return False
            return bool(self.joystick.get_button(index))
        except (KeyError, pygame.error):
            return False

    def dpad(self):
        if self.controller is not None:
            x = int(self.button("dpad_right")) - int(self.button("dpad_left"))
            y = int(self.button("dpad_down")) - int(self.button("dpad_up"))
            return x, y

        try:
            if self.joystick.get_numhats() > 0:
                hat_x, hat_y = self.joystick.get_hat(0)
                return hat_x, -hat_y
        except pygame.error:
            pass
        x = int(self.button("dpad_right")) - int(self.button("dpad_left"))
        y = int(self.button("dpad_down")) - int(self.button("dpad_up"))
        return x, y

    def rumble(self, low_frequency, high_frequency, duration_ms):
        if self.controller is not None:
            try:
                if self.controller.rumble(low_frequency, high_frequency, duration_ms):
                    return True
            except (AttributeError, pygame.error):
                pass
        try:
            return bool(self.joystick.rumble(low_frequency, high_frequency, duration_ms))
        except (AttributeError, pygame.error):
            return False


class GamepadManager:
    """Own connected gamepads and expose game-focused input values."""

    def __init__(self, scan_devices=False):
        # No se escanea en el constructor: SDL garantiza un JOYDEVICEADDED por
        # cada mando ya conectado al arrancar, y escanear aquí duplicaría la
        # apertura del dispositivo (el cierre del duplicado puede dejar inservible
        # el handle compartido). El escaneo periódico queda como respaldo.
        pygame.joystick.init()
        if sdl_controller is not None:
            try:
                if not sdl_controller.get_init():
                    sdl_controller.init()
            except pygame.error:
                pass

        self.devices = {}
        self.active_instance_id = None
        self._previous_buttons = {}
        self._nav_direction = None
        self._nav_next_ms = 0
        self._last_aim = (1.0, 0.0)
        self._queued_actions = set()
        self._queued_nav_keys = []
        self._status_message = None
        self._last_scan_ms = 0

        if scan_devices:
            self.refresh_devices()

    @property
    def active_device(self):
        return self.devices.get(self.active_instance_id)

    @property
    def connected(self):
        return self.active_device is not None

    @property
    def name(self):
        device = self.active_device
        return device.name if device else None

    @property
    def kind(self):
        device = self.active_device
        return device.kind if device else None

    def _add_device(self, device_index):
        try:
            device = _GamepadDevice.open(device_index)
        except (pygame.error, IndexError):
            return
        if device.instance_id in self.devices:
            # Ya está abierto: NO cerrar el duplicado (comparte el handle SDL con
            # el original; cerrarlo dejaría los sticks muertos). Se descarta y ya.
            return
        self.devices[device.instance_id] = device
        if self.active_instance_id is None:
            self._set_active(device.instance_id)

    def _remove_device(self, instance_id):
        device = self.devices.pop(instance_id, None)
        if device:
            device.close()
        if self.active_instance_id == instance_id:
            next_id = next(iter(self.devices), None)
            self._set_active(next_id)

    def _set_active(self, instance_id):
        if instance_id == self.active_instance_id:
            return
        self.active_instance_id = instance_id
        self._nav_direction = None
        self._nav_next_ms = 0
        self._last_aim = (1.0, 0.0)
        self._previous_buttons = self._read_buttons()
        device = self.active_device
        self._status_message = f"Mando conectado: {device.name}" if device else "Mando desconectado"

    def refresh_devices(self):
        if pygame.joystick.get_count() <= len(self.devices):
            return
        for device_index in range(pygame.joystick.get_count()):
            self._add_device(device_index)

    def consume_status_message(self):
        message = self._status_message
        self._status_message = None
        return message

    def _queue_action(self, action):
        if action:
            self._queued_actions.add(action)

    def _queue_nav_key(self, key):
        if key is not None:
            self._queued_nav_keys.append(key)

    def _queue_joystick_button(self, button_index):
        device = self.active_device
        if device is None:
            return
        for action, mapped_index in device.profile["buttons"].items():
            if mapped_index == button_index:
                if action.startswith("dpad_"):
                    self._queue_nav_key(self._key_for_dpad_action(action))
                else:
                    self._queue_action(action)
                return

    def _queue_controller_button(self, button_index):
        for action, mapped_index in CONTROLLER_BUTTONS.items():
            if mapped_index == button_index:
                if action.startswith("dpad_"):
                    self._queue_nav_key(self._key_for_dpad_action(action))
                else:
                    self._queue_action(action)
                return

    def _queue_hat_motion(self, value):
        hat_x, hat_y = value
        if abs(hat_x) >= abs(hat_y) and hat_x:
            self._queue_nav_key(pygame.K_RIGHT if hat_x > 0 else pygame.K_LEFT)
        elif hat_y:
            self._queue_nav_key(pygame.K_UP if hat_y > 0 else pygame.K_DOWN)

    def _key_for_dpad_action(self, action):
        return {
            "dpad_up": pygame.K_UP,
            "dpad_down": pygame.K_DOWN,
            "dpad_left": pygame.K_LEFT,
            "dpad_right": pygame.K_RIGHT,
        }.get(action)

    def handle_event(self, event):
        if event.type in (pygame.JOYDEVICEADDED, pygame.CONTROLLERDEVICEADDED):
            device_index = getattr(event, "device_index", None)
            if device_index is not None:
                self._add_device(device_index)
            return
        if event.type in (pygame.JOYDEVICEREMOVED, pygame.CONTROLLERDEVICEREMOVED):
            instance_id = getattr(event, "instance_id", getattr(event, "which", None))
            if instance_id is not None:
                self._remove_device(instance_id)
            return

        # Solo un botón presionado cambia el mando activo: el ruido de ejes de un
        # segundo dispositivo (p. ej. el mando virtual de Steam) no debe robar el
        # control ni resetear el estado de navegación.
        instance_id = getattr(event, "instance_id", None)
        device = self.devices.get(instance_id)
        if device is None:
            return
        has_controller = device.controller is not None

        if event.type == pygame.JOYBUTTONDOWN:
            # Con Controller abierto, SDL emite además CONTROLLERBUTTONDOWN con la
            # numeración normalizada; el evento crudo se ignora para no duplicar.
            if not has_controller:
                self._set_active(instance_id)
                self._queue_joystick_button(event.button)
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            device.ctrl_button_state[event.button] = True
            self._set_active(instance_id)
            self._queue_controller_button(event.button)
        elif event.type == pygame.CONTROLLERBUTTONUP:
            device.ctrl_button_state[event.button] = False
        elif event.type == pygame.CONTROLLERAXISMOTION:
            # event.value SIEMPRE es el crudo de SDL (-32768..32767); cerca del
            # centro llegan valores como 1 o -1 que deben quedar en ~0, no en 1.0.
            device.ctrl_axis_state[event.axis] = max(-1.0, min(1.0, event.value / 32767.0))
        elif event.type == pygame.JOYHATMOTION:
            if not has_controller:
                self._queue_hat_motion(event.value)

    def _read_buttons(self):
        device = self.active_device
        names = ("confirm", "back", "alt", "rest", "select", "pause", "lb", "rb")
        if device is None:
            return {name: False for name in names}
        return {name: device.button(name) for name in names}

    def _key_event(self, key):
        return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", gamepad=True)

    def poll_events(self, context, now_ms=None):
        """Return keyboard-compatible edge/repeat events for menus and the map."""
        if now_ms is None:
            now_ms = pygame.time.get_ticks()
        if now_ms - self._last_scan_ms >= 1000:
            self._last_scan_ms = now_ms
            self.refresh_devices()
        if self.active_device is None:
            return []

        current = self._read_buttons()
        pressed = {name for name, value in current.items() if value and not self._previous_buttons.get(name, False)}
        pressed.update(self._queued_actions)
        self._queued_actions.clear()
        self._previous_buttons = current
        keys = []

        if "confirm" in pressed:
            keys.append(pygame.K_SPACE if context == "GAME_OVER" else pygame.K_RETURN)
        if "pause" in pressed:
            keys.append(pygame.K_RETURN if context == "TITLE_SCREEN" else pygame.K_ESCAPE)
        if "back" in pressed and context in BACK_CONTEXTS:
            keys.append(pygame.K_ESCAPE)
        if "rest" in pressed and context == "MAP":
            keys.append(pygame.K_r)
        if context in NAV_CONTEXTS:
            if "lb" in pressed:
                keys.append(pygame.K_LEFT)
            if "rb" in pressed:
                keys.append(pygame.K_RIGHT)
            keys.extend(self._queued_nav_keys)
        self._queued_nav_keys.clear()

        nav_key = self._poll_navigation_key(context, now_ms)
        if nav_key is not None:
            keys.append(nav_key)

        events = []
        for key in keys:
            if key not in [event.key for event in events]:
                events.append(self._key_event(key))
        return events

    def _poll_navigation_key(self, context, now_ms):
        if context not in NAV_CONTEXTS:
            self._nav_direction = None
            return None

        dpad_x, dpad_y = self.active_device.dpad()
        if dpad_x or dpad_y:
            nav_x, nav_y = float(dpad_x), float(dpad_y)
        else:
            nav_x, nav_y = self.get_move_vector()

        if max(abs(nav_x), abs(nav_y)) < NAV_THRESHOLD:
            self._nav_direction = None
            self._nav_next_ms = 0
            return None

        if abs(nav_x) >= abs(nav_y):
            direction = pygame.K_RIGHT if nav_x > 0 else pygame.K_LEFT
        else:
            direction = pygame.K_DOWN if nav_y > 0 else pygame.K_UP

        if direction != self._nav_direction:
            self._nav_direction = direction
            self._nav_next_ms = now_ms + NAV_INITIAL_DELAY_MS
            return direction
        if now_ms >= self._nav_next_ms:
            self._nav_next_ms = now_ms + NAV_REPEAT_MS
            return direction
        return None

    def get_move_vector(self):
        device = self.active_device
        if device is None:
            return 0.0, 0.0
        return apply_radial_deadzone(device.axis("left_x"), device.axis("left_y"), MOVE_DEADZONE)

    def get_aim_vector(self):
        device = self.active_device
        if device is None:
            return 0.0, 0.0
        aim = apply_radial_deadzone(device.axis("right_x"), device.axis("right_y"), AIM_DEADZONE)
        if math.hypot(*aim) > 0.0:
            magnitude = math.hypot(*aim)
            self._last_aim = aim[0] / magnitude, aim[1] / magnitude
        return aim

    def get_last_aim_vector(self):
        return self._last_aim

    def get_right_trigger(self):
        device = self.active_device
        return device.trigger("right") if device else 0.0

    def wants_trigger_fire(self):
        return self.get_right_trigger() >= TRIGGER_THRESHOLD

    def rumble(self, low_frequency=0.35, high_frequency=0.65, duration_ms=140):
        device = self.active_device
        if device is None:
            return False
        return device.rumble(low_frequency, high_frequency, duration_ms)

    def quit(self):
        for device in list(self.devices.values()):
            device.close()
        self.devices.clear()
        self.active_instance_id = None
