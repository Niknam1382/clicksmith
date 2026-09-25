"""Macro recorder: turns raw mouse / keyboard events into macro steps.

The conversion (:func:`events_to_steps`) is pure so it can be unit-tested without input devices;
:class:`Recorder` merely feeds it events captured through pynput listeners.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .keys import MODIFIERS, normalize_key
from .models import Button, Step, StepType

DRAG_MIN_PX = 12
MULTI_CLICK_GAP = 0.4
MULTI_CLICK_PX = 4
HOLD_THRESHOLD = 0.35
SCROLL_MERGE_GAP = 0.35
MAX_DELAY_MS = 60_000


@dataclass(frozen=True)
class RecEvent:
    t: float  # seconds since the recording started
    kind: str  # mouse_down | mouse_up | scroll | key_down | key_up
    x: int = 0
    y: int = 0
    button: str = ""
    dx: int = 0
    dy: int = 0
    key: str = ""  # a typed character, or a normalised key name ("enter", "ctrl", ...)


def events_to_steps(events: Iterable[RecEvent], ignore_keys: Iterable[str] = ()) -> list[Step]:
    """Convert raw events into a compact list of macro steps with the recorded pauses."""
    ignore = {normalize_key(k) for k in ignore_keys}
    steps: list[Step] = []
    spans: list[list[float]] = []  # [start, end] time of every step
    pressed: dict[str, RecEvent] = {}
    mods: set[str] = set()
    text: list[tuple[str, float]] = []

    def add(step: Step, start: float, end: float) -> None:
        steps.append(step)
        spans.append([start, end])

    def flush_text() -> None:
        if not text:
            return
        start, end = text[0][1], text[-1][1]
        delay = 20
        if len(text) > 1:
            delay = int(min(250, max(5, (end - start) / (len(text) - 1) * 1000)))
        add(
            Step(type=StepType.TEXT, text="".join(c for c, _ in text), char_delay_ms=delay),
            start,
            end,
        )
        text.clear()

    for ev in events:
        if ev.kind == "mouse_down":
            flush_text()
            pressed[ev.button] = ev
        elif ev.kind == "mouse_up":
            down = pressed.pop(ev.button, None)
            if down is None:
                continue
            held = ev.t - down.t
            button = Button(down.button)
            if math.hypot(ev.x - down.x, ev.y - down.y) > DRAG_MIN_PX:
                duration = int(min(10_000, max(50, held * 1000)))
                add(
                    Step(
                        type=StepType.DRAG,
                        x=down.x,
                        y=down.y,
                        x2=ev.x,
                        y2=ev.y,
                        button=button,
                        duration_ms=duration,
                    ),
                    down.t,
                    ev.t,
                )
                continue
            hold_ms = int(held * 1000) if held >= HOLD_THRESHOLD else 0
            prev = steps[-1] if steps else None
            if (
                prev is not None
                and prev.type == StepType.CLICK
                and prev.button == button
                and prev.clicks < 3
                and prev.hold_ms == 0
                and hold_ms == 0
                and abs(prev.x - down.x) <= MULTI_CLICK_PX
                and abs(prev.y - down.y) <= MULTI_CLICK_PX
                and down.t - spans[-1][1] <= MULTI_CLICK_GAP
            ):
                prev.clicks += 1  # double / triple click
                spans[-1][1] = ev.t
            else:
                add(
                    Step(type=StepType.CLICK, x=down.x, y=down.y, button=button, hold_ms=hold_ms),
                    down.t,
                    ev.t,
                )
        elif ev.kind == "scroll":
            flush_text()
            prev = steps[-1] if steps else None
            if (
                prev is not None
                and prev.type == StepType.SCROLL
                and ev.t - spans[-1][1] <= SCROLL_MERGE_GAP
            ):
                prev.dx += ev.dx
                prev.dy += ev.dy
                spans[-1][1] = ev.t
            else:
                add(Step(type=StepType.SCROLL, x=ev.x, y=ev.y, dx=ev.dx, dy=ev.dy), ev.t, ev.t)
        elif ev.kind == "key_down":
            key = ev.key
            if not key or key in ignore:
                continue
            if key in MODIFIERS:
                mods.add(key)
                continue
            chord = mods & {"ctrl", "alt", "win"}
            if not chord and len(key) == 1:
                text.append((key, ev.t))
            elif not chord and key == "space":
                text.append((" ", ev.t))
            else:
                flush_text()
                combo = [m for m in MODIFIERS if m in mods] + [key]
                add(Step(type=StepType.KEY, keys="+".join(combo)), ev.t, ev.t)
        elif ev.kind == "key_up":
            mods.discard(ev.key)
    flush_text()

    for i, step in enumerate(steps):
        if i + 1 < len(steps):
            gap = spans[i + 1][0] - spans[i][1]
            step.delay_after_ms = int(min(MAX_DELAY_MS, max(0, round(gap * 1000))))
        else:
            step.delay_after_ms = 0
    return steps


def key_name(key) -> str | None:
    """Name of a pynput key object: a typed character or a normalised special-key name."""
    name = getattr(key, "name", None)
    if name:
        return normalize_key(name)
    char = getattr(key, "char", None)
    if char and char.isprintable():
        return char
    vk = getattr(key, "vk", None)  # e.g. Ctrl+C reports a control character: use the key code
    if isinstance(vk, int):
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
    return None


class Recorder:
    """Captures global mouse and keyboard input until :meth:`stop` is called."""

    def __init__(
        self,
        ignore_keys: Iterable[str] = (),
        stop_keys: Iterable[str] = (),
        on_stop_key: Callable[[], None] | None = None,
    ) -> None:
        self._ignore = [normalize_key(k) for k in ignore_keys]
        self._stop_keys = {normalize_key(k) for k in stop_keys}
        self._on_stop_key = on_stop_key
        self._events: list[RecEvent] = []
        self._lock = threading.Lock()
        self._t0 = 0.0
        self._listeners: list = []

    @property
    def recording(self) -> bool:
        return bool(self._listeners)

    def start(self) -> None:
        from pynput import keyboard, mouse  # lazy: needs a display server

        with self._lock:
            self._events.clear()
        self._t0 = time.perf_counter()
        listeners = [
            mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll),
            keyboard.Listener(on_press=self._on_press, on_release=self._on_release),
        ]
        for listener in listeners:
            listener.daemon = True
            listener.start()
        self._listeners = listeners

    def stop(self) -> list[Step]:
        listeners, self._listeners = self._listeners, []
        for listener in listeners:
            listener.stop()
        with self._lock:
            events = list(self._events)
        return events_to_steps(events, ignore_keys=self._ignore)

    # --- listener callbacks (run on pynput threads) -------------------------------------
    def _add(self, event: RecEvent) -> None:
        with self._lock:
            self._events.append(event)

    def _now(self) -> float:
        return time.perf_counter() - self._t0

    def _on_click(self, x, y, button, pressed) -> None:
        name = getattr(button, "name", "")
        if name in ("left", "right", "middle"):
            kind = "mouse_down" if pressed else "mouse_up"
            self._add(RecEvent(self._now(), kind, int(x), int(y), button=name))

    def _on_scroll(self, x, y, dx, dy) -> None:
        self._add(RecEvent(self._now(), "scroll", int(x), int(y), dx=int(dx), dy=int(dy)))

    def _on_press(self, key) -> None:
        name = key_name(key)
        if name is None:
            return
        if normalize_key(name) in self._stop_keys:
            if self._on_stop_key is not None:
                self._on_stop_key()
            return
        self._add(RecEvent(self._now(), "key_down", key=name))

    def _on_release(self, key) -> None:
        name = key_name(key)
        if name:
            self._add(RecEvent(self._now(), "key_up", key=name))
