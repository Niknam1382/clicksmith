"""Global hotkeys via pynput (imported lazily so the core works without a display server)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from .keys import MODIFIERS, is_valid_key, parse_combo

log = logging.getLogger("clicksmith.hotkeys")

_PYNPUT_NAMES = {
    "pageup": "page_up",
    "pagedown": "page_down",
    "capslock": "caps_lock",
    "numlock": "num_lock",
    "scrolllock": "scroll_lock",
    "printscreen": "print_screen",
}


def to_pynput(combo: str) -> str:
    """Convert "Ctrl+Shift+F6" to pynput's "<ctrl>+<shift>+<f6>" notation."""
    keys = parse_combo(combo)
    if not keys:
        raise ValueError("Empty hotkey")
    if all(k in MODIFIERS for k in keys):
        raise ValueError(f"Hotkey '{combo}' needs a key besides the modifiers")
    parts = []
    for key in keys:
        if not is_valid_key(key):
            raise ValueError(f"Unknown key '{key}' in hotkey '{combo}'")
        if key == "win":
            parts.append("<cmd>")
        elif key in MODIFIERS or len(key) > 1:
            parts.append(f"<{_PYNPUT_NAMES.get(key, key)}>")
        else:
            parts.append(key)
    return "+".join(parts)


class HotkeyManager:
    """Registers a set of global hotkeys; callbacks run on pynput's listener thread."""

    def __init__(self, debounce: float = 0.25) -> None:
        self._listener = None
        self._debounce = debounce
        self._last: dict[str, float] = {}

    def _wrap(self, combo: str, callback: Callable[[], None]) -> Callable[[], None]:
        def fire() -> None:
            now = time.monotonic()
            last = self._last.get(combo)
            if last is not None and now - last < self._debounce:
                return
            self._last[combo] = now
            try:
                callback()
            except Exception:
                log.exception("Hotkey handler for %s failed", combo)

        return fire

    def register(self, bindings: dict[str, Callable[[], None]]) -> list[str]:
        """(Re)register *bindings* ({"F6": callback}); returns a list of error messages."""
        self.stop()
        errors: list[str] = []
        mapping: dict[str, Callable[[], None]] = {}
        for combo, callback in bindings.items():
            try:
                mapping[to_pynput(combo)] = self._wrap(combo, callback)
            except ValueError as exc:
                errors.append(str(exc))
        if not mapping:
            return errors
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys(mapping)
            listener.daemon = True
            listener.start()
            self._listener = listener
        except Exception as exc:
            errors.append(f"Global hotkeys are unavailable: {exc}")
        return errors

    def stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                log.debug("Could not stop the hotkey listener cleanly", exc_info=True)
