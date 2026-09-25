"""A do-nothing backend that records what would have happened (tests and --dry-run)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..models import Button
from .base import InputBackend


class FakeBackend(InputBackend):
    name = "fake"

    def __init__(
        self,
        verbose: bool = False,
        printer: Callable[[str], None] = print,
        on_event: Callable[[tuple], None] | None = None,
    ) -> None:
        self.pos: tuple[int, int] = (500, 500)
        self.events: list[tuple] = []
        self.verbose = verbose
        self._print = printer
        self.on_event = on_event

    def _rec(self, *event) -> None:
        self.events.append(event)
        if self.verbose:
            self._print("[dry-run] " + " ".join(str(part) for part in event))
        if self.on_event is not None:
            self.on_event(event)

    @property
    def click_count(self) -> int:
        return sum(e[2] for e in self.events if e[0] == "click")

    def position(self) -> tuple[int, int]:
        return self.pos

    def move_to(self, x: int, y: int) -> None:
        self.pos = (int(x), int(y))
        self._rec("move", int(x), int(y))

    def mouse_down(self, button: Button) -> None:
        self._rec("down", str(button))

    def mouse_up(self, button: Button) -> None:
        self._rec("up", str(button))

    def click(self, button: Button, count: int = 1) -> None:
        self._rec("click", str(button), count)

    def scroll(self, dx: int, dy: int) -> None:
        self._rec("scroll", dx, dy)

    def key_down(self, key: str) -> None:
        self._rec("key_down", key)

    def key_up(self, key: str) -> None:
        self._rec("key_up", key)

    def press_keys(self, keys: Sequence[str], hold: float = 0.02) -> None:
        self._rec("keys", "+".join(keys))

    def type_char(self, ch: str) -> None:
        self._rec("char", ch)

    def type_newline(self) -> None:
        self._rec("newline")

    def type_text(self, text, char_delay=0.02, should_stop=None) -> None:
        self._rec("text", text)
