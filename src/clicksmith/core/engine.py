"""Threaded automation engine: runs a :class:`Profile` through an :class:`InputBackend`.

The engine has no GUI dependency. It reports state changes through one callback and exposes
lock-free statistics via :meth:`Engine.snapshot`, which the UI polls a few times per second.
"""

from __future__ import annotations

import copy
import logging
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from .input.base import InputBackend
from .keys import parse_combo
from .models import Button, Profile, RunMode, Step, StepType, StopMode, Target, TargetMode
from .sysutils import high_resolution_timer, keep_awake
from .timing import wait_until

log = logging.getLogger("clicksmith.engine")

MIN_INTERVAL = 0.001  # 1 ms => at most 1000 clicks/second
MOVE_TOLERANCE_PX = 8
CPS_WINDOW = 2.0


class RunState(StrEnum):
    IDLE = "idle"
    WAITING = "waiting"  # start delay or scheduled start
    RUNNING = "running"


class StopReason(StrEnum):
    COMPLETED = "completed"
    USER = "user"
    FAILSAFE = "failsafe"
    MOUSE_MOVED = "mouse_moved"
    ERROR = "error"


StateCallback = Callable[[RunState, StopReason | None], None]


class _Halt(Exception):
    """Internal control flow: unwinds the run as soon as a stop condition is met."""

    def __init__(self, reason: StopReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class Snapshot:
    state: RunState
    count: int  # repetitions: clicks in clicker mode, macro runs in macro mode
    clicks: int  # click actions performed
    cps: float
    elapsed: float
    next_in: float | None  # seconds until the next run / scheduled start
    reason: StopReason | None  # why the last run ended (when idle)


class Engine:
    def __init__(
        self,
        backend: InputBackend,
        on_state: StateCallback | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.backend = backend
        self._on_state = on_state
        self._rng = rng or random.Random()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._state = RunState.IDLE
        self._reason: StopReason | None = None
        self._final_reason: StopReason | None = None
        self._count = 0
        self._clicks = 0
        self._stamps: deque[float] = deque(maxlen=8192)
        self._t_start: float | None = None
        self._t_end: float | None = None
        self._next_wall: float | None = None
        self._failsafe = False
        self._track_moves = False
        self._last_pos: tuple[int, int] | None = None

    # ------------------------------------------------------------------ public API
    @property
    def running(self) -> bool:
        return self._running

    @property
    def state(self) -> RunState:
        return self._state

    def start(
        self,
        profile: Profile,
        *,
        start_delay: float | None = None,
        start_at: float | None = None,
    ) -> bool:
        """Start running *profile* in a background thread.

        *start_delay* overrides the profile's start delay (seconds). *start_at* is an absolute
        ``time.time()`` value for a scheduled start and wins over the delay. Returns False if a
        run is already active.
        """
        with self._lock:
            if self._running:
                return False
            self._running = True
        snapshot = copy.deepcopy(profile).normalize()
        self._stop.clear()
        self._reason = None
        self._reset_stats()
        delay = snapshot.safety.start_delay_s if start_delay is None else start_delay
        self._thread = threading.Thread(
            target=self._run,
            args=(snapshot, float(delay), start_at),
            name="clicksmith-engine",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self, reason: StopReason = StopReason.USER) -> None:
        """Ask the running job to stop. Safe to call from any thread, never blocks."""
        self._request_stop(reason)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current run has finished. Returns True when the engine is idle."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return not self._running

    def snapshot(self) -> Snapshot:
        now = time.perf_counter()
        state = self._state
        if self._t_start is None:
            elapsed = 0.0
        else:
            elapsed = (self._t_end if self._t_end is not None else now) - self._t_start
        cps = 0.0
        if state == RunState.RUNNING and self._t_start is not None:
            stamps = tuple(self._stamps)
            recent = sum(1 for t in stamps if t >= now - CPS_WINDOW)
            cps = recent / max(min(CPS_WINDOW, elapsed), 0.25)
        next_in = None if self._next_wall is None else max(0.0, self._next_wall - time.time())
        return Snapshot(
            state, self._count, self._clicks, cps, max(0.0, elapsed), next_in, self._final_reason
        )

    # ------------------------------------------------------------------ bookkeeping
    def _reset_stats(self) -> None:
        self._count = 0
        self._clicks = 0
        self._stamps.clear()
        self._t_start = None
        self._t_end = None
        self._next_wall = None
        self._final_reason = None

    def _request_stop(self, reason: StopReason) -> None:
        with self._lock:
            if self._reason is None:
                self._reason = reason
        self._stop.set()

    def _current_reason(self) -> StopReason:
        return self._reason or StopReason.USER

    def _set_state(self, state: RunState, reason: StopReason | None = None) -> None:
        self._state = state
        if self._on_state is not None:
            try:
                self._on_state(state, reason)
            except Exception:
                log.exception("State callback failed")

    def _record_click(self) -> None:
        self._clicks += 1
        self._stamps.append(time.perf_counter())

    # ------------------------------------------------------------------ thread body
    def _run(self, p: Profile, delay: float, start_at: float | None) -> None:
        reason = StopReason.COMPLETED
        try:
            self._failsafe = p.safety.failsafe_corner
            self._track_moves = False
            self._last_pos = None
            log.info("Started '%s' (%s mode)", p.name, p.mode.value)
            with high_resolution_timer(), keep_awake(p.safety.prevent_sleep):
                self._initial_wait(delay, start_at)
                self._begin_running(p)
                if p.mode == RunMode.CLICKER:
                    self._loop_clicker(p)
                else:
                    self._loop_macro(p)
        except _Halt as halt:
            reason = halt.reason
        except Exception as exc:
            log.exception("The engine stopped because of an error")
            log.info("Error: %s", exc)
            reason = StopReason.ERROR
        finally:
            self._finish(reason)

    def _finish(self, reason: StopReason) -> None:
        self._t_end = time.perf_counter()
        self._next_wall = None
        self._final_reason = reason
        elapsed = (self._t_end - self._t_start) if self._t_start is not None else 0.0
        log.info(
            "Stopped (%s): %d repetitions, %d clicks, %.1f s",
            reason.value,
            self._count,
            self._clicks,
            elapsed,
        )
        with self._lock:
            self._running = False
        self._set_state(RunState.IDLE, reason)

    def _initial_wait(self, delay: float, start_at: float | None) -> None:
        now_wall = time.time()
        wait = (start_at - now_wall) if start_at is not None else delay
        if wait <= 0:
            return
        self._set_state(RunState.WAITING)
        self._next_wall = now_wall + wait
        log.info("Starting in %.1f s", wait)
        self._wait_deadline(time.perf_counter() + wait)
        self._next_wall = None

    def _begin_running(self, p: Profile) -> None:
        self._t_start = time.perf_counter()
        self._track_moves = p.safety.stop_on_mouse_move and (
            p.mode == RunMode.MACRO or p.target.mode != TargetMode.CURSOR
        )
        self._last_pos = self.backend.position()
        self._set_state(RunState.RUNNING)

    # ------------------------------------------------------------------ stop conditions
    def _should_stop(self) -> bool:
        if self._stop.is_set():
            return True
        if self._failsafe or self._track_moves:
            try:
                x, y = self.backend.position()
            except Exception:
                return False
            if self._failsafe and (x, y) == (0, 0):
                self._request_stop(StopReason.FAILSAFE)
                return True
            if self._track_moves and self._last_pos is not None:
                lx, ly = self._last_pos
                if abs(x - lx) > MOVE_TOLERANCE_PX or abs(y - ly) > MOVE_TOLERANCE_PX:
                    self._request_stop(StopReason.MOUSE_MOVED)
                    return True
        return False

    def _check(self) -> None:
        if self._should_stop():
            raise _Halt(self._current_reason())

    def _wait_deadline(self, deadline: float) -> None:
        if not wait_until(deadline, self._stop, poll=self._should_stop):
            raise _Halt(self._current_reason())

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._wait_deadline(time.perf_counter() + seconds)

    # ------------------------------------------------------------------ primitives
    def _jittered(self, seconds: float, jitter: float) -> float:
        if not jitter:
            return seconds
        return max(0.0, seconds * self._rng.uniform(1 - jitter, 1 + jitter))

    def _target_point(self, target: Target) -> tuple[int, int]:
        if target.mode == TargetMode.AREA:
            return (
                self._rng.randint(min(target.x, target.x2), max(target.x, target.x2)),
                self._rng.randint(min(target.y, target.y2), max(target.y, target.y2)),
            )
        x, y = target.x, target.y
        if target.jitter_px:
            x += self._rng.randint(-target.jitter_px, target.jitter_px)
            y += self._rng.randint(-target.jitter_px, target.jitter_px)
        return x, y

    def _move(self, x: int, y: int, duration_ms: int = 0) -> None:
        self._check()
        if duration_ms <= 0:
            self.backend.move_to(x, y)
        else:
            sx, sy = self.backend.position()
            steps = max(2, duration_ms // 8)
            total = duration_ms / 1000
            t0 = time.perf_counter()
            for i in range(1, steps + 1):
                k = i / steps
                ease = k * k * (3 - 2 * k)  # smoothstep: gentle start and end
                self.backend.move_to(round(sx + (x - sx) * ease), round(sy + (y - sy) * ease))
                self._last_pos = self.backend.position()
                self._wait_deadline(t0 + total * k)
        self._last_pos = self.backend.position()

    def _do_click(self, button: Button, count: int, hold_s: float) -> None:
        if hold_s <= 0:
            self.backend.click(button, count)
        else:
            for _ in range(count):
                self.backend.mouse_down(button)
                try:
                    self._sleep(hold_s)
                finally:
                    self.backend.mouse_up(button)
        self._record_click()

    # ------------------------------------------------------------------ clicker mode
    def _limits(self, p: Profile) -> tuple[int | None, float | None]:
        max_count = p.stop.count if p.stop.mode == StopMode.COUNT else None
        t_stop = None
        if p.stop.mode == StopMode.DURATION and self._t_start is not None:
            t_stop = self._t_start + p.stop.duration_s
        return max_count, t_stop

    def _loop_clicker(self, p: Profile) -> None:
        base = max(MIN_INTERVAL, p.interval.total_seconds)
        jitter = p.interval.jitter_pct / 100
        max_count, t_stop = self._limits(p)
        hold = p.click.hold_ms / 1000
        next_t = time.perf_counter()
        while True:
            self._check()
            if p.target.mode != TargetMode.CURSOR:
                self._move(*self._target_point(p.target))
            self._do_click(p.click.button, p.click.clicks, hold)
            self._count += 1
            if max_count is not None and self._count >= max_count:
                return
            next_t += max(MIN_INTERVAL, self._jittered(base, jitter))
            now = time.perf_counter()
            if next_t < now:
                next_t = now  # running late: do not burst to catch up
            if t_stop is not None and next_t >= t_stop:
                return
            self._wait_deadline(next_t)

    # ------------------------------------------------------------------ macro mode
    def _loop_macro(self, p: Profile) -> None:
        if not p.steps:
            raise ValueError("The macro has no steps")
        jitter = p.interval.jitter_pct / 100
        max_count, t_stop = self._limits(p)
        while True:
            for step in p.steps:
                self._check()
                self._exec(step, jitter)
            self._count += 1
            log.info("Macro run %d finished", self._count)
            if max_count is not None and self._count >= max_count:
                return
            gap = self._jittered(p.interval.total_seconds, jitter)
            if t_stop is not None and time.perf_counter() + gap >= t_stop:
                return
            self._next_wall = time.time() + gap
            self._wait_deadline(time.perf_counter() + gap)
            self._next_wall = None

    def _exec(self, s: Step, jitter: float) -> None:
        kind = s.type
        if kind == StepType.CLICK:
            if not s.use_cursor:
                self._move(s.x, s.y)
            self._do_click(s.button, s.clicks, s.hold_ms / 1000)
        elif kind == StepType.MOVE:
            self._move(s.x, s.y, s.duration_ms)
        elif kind == StepType.DRAG:
            self._move(s.x, s.y)
            self.backend.mouse_down(s.button)
            try:
                self._move(s.x2, s.y2, max(s.duration_ms, 50))
            finally:
                self.backend.mouse_up(s.button)
        elif kind == StepType.SCROLL:
            if not s.use_cursor:
                self._move(s.x, s.y)
            self.backend.scroll(s.dx, s.dy)
        elif kind == StepType.TEXT:
            self.backend.type_text(s.text, s.char_delay_ms / 1000, self._should_stop)
            self._check()
        elif kind == StepType.KEY:
            keys = parse_combo(s.keys)
            if keys:
                self.backend.press_keys(keys)
        # StepType.WAIT does nothing except the delay below
        self._sleep(self._jittered(s.delay_after_ms / 1000, jitter))
