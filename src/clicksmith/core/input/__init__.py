"""Input backends. The engine only ever talks to :class:`InputBackend`."""

from __future__ import annotations

import sys

from .base import InputBackend
from .fake import FakeBackend


def create_backend(kind: str = "auto") -> InputBackend:
    """Pick the best backend for this OS: native SendInput on Windows, pynput elsewhere."""
    if kind == "fake":
        return FakeBackend()
    if sys.platform == "win32" and kind in ("auto", "win32"):
        from .win32 import Win32Backend

        return Win32Backend()
    from .pynput_backend import PynputBackend

    return PynputBackend()


__all__ = ["FakeBackend", "InputBackend", "create_backend"]
