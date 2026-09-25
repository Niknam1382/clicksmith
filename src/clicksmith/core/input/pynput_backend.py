"""Cross-platform fallback backend (macOS / Linux X11) built on pynput. Experimental."""

from __future__ import annotations

from ..keys import normalize_key
from ..models import Button
from .base import InputBackend

_ATTR = {
    "pageup": "page_up",
    "pagedown": "page_down",
    "win": "cmd",
    "capslock": "caps_lock",
    "numlock": "num_lock",
    "scrolllock": "scroll_lock",
    "printscreen": "print_screen",
}


class PynputBackend(InputBackend):
    name = "pynput"

    def __init__(self) -> None:
        from pynput import keyboard, mouse  # imported lazily: needs a display server

        self._kb = keyboard
        self._mouse = mouse.Controller()
        self._keys = keyboard.Controller()
        self._buttons = {
            Button.LEFT: mouse.Button.left,
            Button.RIGHT: mouse.Button.right,
            Button.MIDDLE: mouse.Button.middle,
        }

    def _key(self, name: str):
        key = normalize_key(name)
        member = getattr(self._kb.Key, _ATTR.get(key, key), None)
        if member is not None:
            return member
        if len(key) == 1:
            return self._kb.KeyCode.from_char(key)
        raise ValueError(f"Unknown key: {name!r}")

    def position(self) -> tuple[int, int]:
        x, y = self._mouse.position
        return int(x), int(y)

    def move_to(self, x: int, y: int) -> None:
        self._mouse.position = (int(x), int(y))

    def mouse_down(self, button: Button) -> None:
        self._mouse.press(self._buttons[Button(button)])

    def mouse_up(self, button: Button) -> None:
        self._mouse.release(self._buttons[Button(button)])

    def scroll(self, dx: int, dy: int) -> None:
        self._mouse.scroll(dx, dy)

    def key_down(self, key: str) -> None:
        self._keys.press(self._key(key))

    def key_up(self, key: str) -> None:
        self._keys.release(self._key(key))

    def type_char(self, ch: str) -> None:
        self._keys.type(ch)

    def type_newline(self) -> None:
        with self._keys.pressed(self._kb.Key.shift):
            self._keys.tap(self._kb.Key.enter)
