"""Capa de control sobre Animator: clips con nombre, prioridades y eventos.

El controlador decide QUE animacion se reproduce y QUE eventos emite; cada
entidad decide que significan esos eventos (bind). No conoce balas, danio ni
sonido: solo nombres.

Uso tipico:

    clips = {
        "idle":   AnimationClip(state=0, loop=True, priority=0),
        "move":   AnimationClip(state=1, loop=True, priority=0),
        "attack": AnimationClip(state=2, loop=False, priority=30,
                                events={4: ("shoot",)}),
        "hurt":   AnimationClip(state=3, loop=False, priority=50),
        "death":  AnimationClip(state=4, loop=False, priority=100,
                                hold_last=True),
    }
    controller = AnimationController(animator, clips, base="idle")
    controller.bind("shoot", self.spawn_projectile)

    # cada tick del juego:
    controller.set_base("move" if moving else "idle")
    controller.update(dt_ms)

Reglas de prioridad:
- Un clip nuevo interrumpe al activo solo si su prioridad es MAYOR.
- Prioridad igual no interrumpe (evita stun-lock visual); el propio clip
  puede reiniciarse a si mismo solo si se declara con restart=True.
- Los clips base (idle/move) van con prioridad baja; cambiar entre ellos es
  set_base(), que nunca interrumpe un one-shot en curso.
- hold_last=True congela el ultimo frame al terminar (muerte): el clip sigue
  activo y su prioridad sigue bloqueando a los demas.

Eventos:
- events={indice_de_frame: ("nombre", ...)} se emiten al ENTRAR a ese frame,
  exactamente una vez por pasada, aunque un dt grande salte varios indices o
  la animacion envuelva al final del loop.
- Al terminar un one-shot se emite automaticamente "<nombre>:finished".
- Los eventos del frame 0 se emiten al arrancar el clip (dentro de play()).
"""


class AnimationClip:
    def __init__(self, state, loop=True, priority=0, speed=None,
                 events=None, restart=False, hold_last=False):
        self.state = state          # fila del Animator
        self.loop = loop
        self.priority = priority
        self.speed = speed          # None -> velocidad ya configurada en el Animator
        self.events = {int(k): tuple(v) for k, v in (events or {}).items()}
        self.restart = restart      # re-solicitarse a si mismo lo reinicia
        self.hold_last = hold_last  # al terminar se queda en el ultimo frame


class AnimationController:
    def __init__(self, animator, clips, base):
        self.animator = animator
        self.clips = dict(clips)
        self._bindings = {}
        self._current = None
        self._holding = False
        self._base = None

        for name, clip in self.clips.items():
            frames = animator.frames.get(clip.state)
            if not frames:
                raise ValueError(
                    f"clip '{name}': el estado {clip.state} no tiene frames en el Animator")
            for idx in clip.events:
                if not 0 <= idx < len(frames):
                    raise ValueError(
                        f"clip '{name}': evento en frame {idx}, pero el clip tiene "
                        f"{len(frames)} frames (0..{len(frames) - 1})")

        self.set_base(base)

    # ---- API publica ----

    @property
    def current(self):
        return self._current

    def is_playing(self, name):
        return self._current == name

    @property
    def busy(self):
        """True mientras hay un one-shot activo (o congelado en hold_last)."""
        return self._current is not None and not self.clips[self._current].loop

    def bind(self, event, callback):
        self._bindings.setdefault(event, []).append(callback)

    def set_base(self, name):
        """Define el clip de reposo/movimiento. Nunca interrumpe un one-shot
        ni un clip solicitado con play(); solo re-apunta a donde volver."""
        self._require(name)
        showing_base = self._current is None or self._current == self._base
        self._base = name
        if showing_base and self._current != name:
            self._start(name)

    def stop(self):
        """Corta el clip activo y vuelve inmediatamente al base."""
        if self._current != self._base:
            self._start(self._base)

    def play(self, name, restart=None):
        """Solicita un clip. Devuelve True si se acepto (interrumpio o arranco)."""
        clip = self._require(name)
        if self._current is None:
            self._start(name)
            return True

        active = self.clips[self._current]
        if name == self._current:
            wants_restart = clip.restart if restart is None else restart
            if wants_restart:
                self._start(name)
                return True
            return False
        if clip.priority > active.priority:
            self._start(name)
            return True
        return False

    def update(self, dt_ms=None):
        """Avanza la animacion y emite los eventos de los frames cruzados."""
        if self._current is None or self._holding:
            return
        clip = self.clips[self._current]
        num_frames = len(self.animator.frames[clip.state])

        prev = self.animator.current_frame
        self.animator.update(dt_ms)
        new = self.animator.current_frame

        if new >= prev:
            self._emit_range(clip, int(prev) + 1, int(new) + 1)
            return

        # El Animator envolvio (modulo): fin de pasada.
        self._emit_range(clip, int(prev) + 1, num_frames)
        if clip.loop:
            self._emit_range(clip, 0, int(new) + 1)
            return

        # One-shot terminado.
        finished = self._current
        if clip.hold_last:
            self.animator.current_frame = float(num_frames - 1)
            self._holding = True
            self._emit(f"{finished}:finished")
        else:
            # Primero volver al base y luego emitir: asi un callback de
            # "<clip>:finished" puede encadenar otro clip (attack -> recover)
            # compitiendo contra la prioridad del base, no contra la del
            # one-shot que acaba de terminar.
            self._start(self._base)
            self._emit(f"{finished}:finished")

    # ---- internos ----

    def _require(self, name):
        clip = self.clips.get(name)
        if clip is None:
            raise KeyError(
                f"clip desconocido '{name}'; disponibles: {sorted(self.clips)}")
        return clip

    def _start(self, name):
        clip = self.clips[name]
        self._current = name
        self._holding = False
        if clip.speed is not None:
            self.animator.state_speeds[clip.state] = clip.speed
        self.animator.set_state(clip.state)
        self.animator.current_frame = 0.0
        self._emit_frame(clip, 0)

    def _emit_range(self, clip, start, stop):
        for idx in range(start, stop):
            self._emit_frame(clip, idx)

    def _emit_frame(self, clip, idx):
        for event in clip.events.get(idx, ()):
            self._emit(event)

    def _emit(self, event):
        for callback in self._bindings.get(event, ()):
            callback()
