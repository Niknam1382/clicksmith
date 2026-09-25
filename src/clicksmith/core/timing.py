"""Cancellable, high-precision waiting."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

SPIN_WINDOW = 0.002  # busy-wait for the last 2 ms to beat OS timer granularity
MAX_CHUNK = 3600.0


def wait_until(
    deadline: float,
    stop: threading.Event,
    *,
    poll: Callable[[], bool] | None = None,
    poll_interval: float = 0.2,
) -> bool:
    """Block until ``time.perf_counter()`` reaches *deadline*.

    Returns True when the deadline was reached and False when the wait was aborted, either because
    *stop* was set or because *poll* returned True (used for the failsafe / mouse-move checks).
    """
    while True:
        if stop.is_set():
            return False
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return True
        if remaining > SPIN_WINDOW:
            if poll is not None and poll():
                return False
            chunk = min(remaining - SPIN_WINDOW, poll_interval if poll else MAX_CHUNK)
            stop.wait(chunk)
