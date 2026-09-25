"""Abstract input backend: everything the engine needs to drive mouse and keyboard."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence

from ..models import Button


class InputBackend(ABC):
    name = "abstract"

    # --- mouse -------------------------------------------------------------------------
    @abstractmethod
    def position(self) -> tuple[int, int]:
        """Current cursor position in physical screen pixels."""

    @abstractmethod
    def move_to(self, x: int, y: int) -> None: ...

    @abstractmethod
    def mouse_down(self, button: Button) -> None: ...

    @abstractmethod
    def mouse_up(self, button: Button) -> None: ...

    @abstractmethod
    def scroll(self, dx: int, dy: int) -> None:
        """Scroll by wheel notches; positive *dy* scrolls up, positive *dx* scrolls right."""

    def click(self, button: Button, count: int = 1) -> None:
        """Press and release *count* times back to back (backends may batch this)."""
        for _ in range(count):
            self.mouse_down(button)
            self.mouse_up(button)

    # --- keyboard ----------------------------------------------------------------------
    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def type_char(self, ch: str) -> None:
        """Type one Unicode character regardless of the active keyboard layout."""

    @abstractmethod
    def type_newline(self) -> None:
        """Insert a line break (Shift+Enter, which is a newline in chat boxes and editors)."""

    def press_keys(self, keys: Sequence[str], hold: float = 0.02) -> None:
        """Press a chord such as ["ctrl", "v"]: hold everything, then release in reverse."""
        pressed: list[str] = []
        try:
            for key in keys:
                self.key_down(key)
                pressed.append(key)
            if hold > 0:
                time.sleep(hold)
        finally:
            for key in reversed(pressed):
                self.key_up(key)

    def type_text(
        self,
        text: str,
        char_delay: float = 0.02,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        for ch in text:
            if should_stop is not None and should_stop():
                return
            if ch == "\r":
                continue
            if ch == "\n":
                self.type_newline()
            else:
                self.type_char(ch)
            if char_delay > 0:
                time.sleep(char_delay)
