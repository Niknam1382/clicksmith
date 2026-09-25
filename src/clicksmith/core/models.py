"""Data model for Clicksmith profiles.

Everything is a plain dataclass so a profile can be stored as JSON, shared between users and
validated without importing any GUI toolkit.  Loading is deliberately forgiving: unknown keys are
ignored and invalid values fall back to defaults, so hand-edited or older files never crash.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

SCHEMA_VERSION = 1
T = TypeVar("T")


class Button(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class RunMode(StrEnum):
    CLICKER = "clicker"
    MACRO = "macro"


class TargetMode(StrEnum):
    CURSOR = "cursor"
    FIXED = "fixed"
    AREA = "area"


class StopMode(StrEnum):
    INFINITE = "infinite"
    COUNT = "count"
    DURATION = "duration"


class StepType(StrEnum):
    CLICK = "click"
    MOVE = "move"
    DRAG = "drag"
    SCROLL = "scroll"
    TEXT = "text"
    KEY = "key"
    WAIT = "wait"


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def parse_time_str(text: str) -> tuple[int, int, int]:
    """Parse "HH:MM" or "HH:MM:SS"; anything invalid becomes midnight."""
    try:
        parts = [int(p) for p in str(text).strip().split(":")]
    except ValueError:
        return 0, 0, 0
    while len(parts) < 3:
        parts.append(0)
    h, m, s = parts[:3]
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        return 0, 0, 0
    return h, m, s


@dataclass
class Interval:
    """Time between repetitions: clicks in clicker mode, macro runs in macro mode."""

    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    millis: int = 100
    jitter_pct: int = 0

    @property
    def total_seconds(self) -> float:
        return self.hours * 3600 + self.minutes * 60 + self.seconds + self.millis / 1000

    def normalize(self) -> None:
        total_ms = (
            max(0, self.hours) * 3_600_000
            + max(0, self.minutes) * 60_000
            + max(0, self.seconds) * 1000
            + max(0, self.millis)
        )
        total_ms = min(total_ms, 9999 * 3_600_000)
        self.hours, rest = divmod(total_ms, 3_600_000)
        self.minutes, rest = divmod(rest, 60_000)
        self.seconds, self.millis = divmod(rest, 1000)
        self.jitter_pct = clamp(self.jitter_pct, 0, 100)


@dataclass
class ClickSpec:
    button: Button = Button.LEFT
    clicks: int = 1
    hold_ms: int = 0

    def normalize(self) -> None:
        self.clicks = clamp(self.clicks, 1, 3)
        self.hold_ms = clamp(self.hold_ms, 0, 60_000)


@dataclass
class Target:
    mode: TargetMode = TargetMode.CURSOR
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    jitter_px: int = 0

    def normalize(self) -> None:
        for name in ("x", "y", "x2", "y2"):
            setattr(self, name, clamp(getattr(self, name), -100_000, 100_000))
        self.jitter_px = clamp(self.jitter_px, 0, 500)


@dataclass
class StopRule:
    mode: StopMode = StopMode.INFINITE
    count: int = 100
    duration_s: int = 60

    def normalize(self) -> None:
        self.count = clamp(self.count, 1, 2_000_000_000)
        self.duration_s = clamp(self.duration_s, 1, 10_000_000)


@dataclass
class Safety:
    failsafe_corner: bool = True
    stop_on_mouse_move: bool = False
    prevent_sleep: bool = True
    start_delay_s: int = 3

    def normalize(self) -> None:
        self.start_delay_s = clamp(self.start_delay_s, 0, 3600)


@dataclass
class Step:
    """One action of a macro."""

    type: StepType = StepType.CLICK
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    use_cursor: bool = False
    button: Button = Button.LEFT
    clicks: int = 1
    hold_ms: int = 0
    duration_ms: int = 0
    dx: int = 0
    dy: int = 0
    text: str = ""
    char_delay_ms: int = 20
    keys: str = ""
    delay_after_ms: int = 300

    def normalize(self) -> None:
        for name in ("x", "y", "x2", "y2"):
            setattr(self, name, clamp(getattr(self, name), -100_000, 100_000))
        self.clicks = clamp(self.clicks, 1, 3)
        self.hold_ms = clamp(self.hold_ms, 0, 60_000)
        self.duration_ms = clamp(self.duration_ms, 0, 600_000)
        self.dx = clamp(self.dx, -10_000, 10_000)
        self.dy = clamp(self.dy, -10_000, 10_000)
        self.char_delay_ms = clamp(self.char_delay_ms, 0, 5000)
        self.delay_after_ms = clamp(self.delay_after_ms, 0, 86_400_000)
        self.text = self.text[:20_000]


@dataclass
class Schedule:
    enabled: bool = False
    time: str = "09:00:00"
    days: list[int] = field(default_factory=lambda: list(range(7)))  # Monday = 0
    once: bool = True

    def normalize(self) -> None:
        h, m, s = parse_time_str(self.time)
        self.time = f"{h:02d}:{m:02d}:{s:02d}"
        days = sorted({d for d in self.days if isinstance(d, int) and 0 <= d <= 6})
        self.days = days or list(range(7))


@dataclass
class Profile:
    schema: int = SCHEMA_VERSION
    name: str = "Default"
    mode: RunMode = RunMode.CLICKER
    interval: Interval = field(default_factory=Interval)
    click: ClickSpec = field(default_factory=ClickSpec)
    target: Target = field(default_factory=Target)
    stop: StopRule = field(default_factory=StopRule)
    safety: Safety = field(default_factory=Safety)
    steps: list[Step] = field(default_factory=list)
    schedule: Schedule = field(default_factory=Schedule)

    def normalize(self) -> Profile:
        self.name = self.name.strip()[:80] or "Default"
        for part in (self.interval, self.click, self.target, self.stop, self.safety, self.schedule):
            part.normalize()
        for step in self.steps:
            step.normalize()
        return self

    def copy(self) -> Profile:
        return copy.deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        return dataclass_from_dict(cls, data).normalize()


# --------------------------------------------------------------------------- (de)serialisation


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass tree to plain JSON-compatible builtins."""
    return _plain(dataclasses.asdict(obj))


def _coerce(tp: Any, value: Any) -> Any:
    origin = get_origin(tp)
    if origin is list:
        (item_tp,) = get_args(tp)
        if not isinstance(value, list):
            raise TypeError("expected a list")
        items = []
        for item in value:
            try:
                items.append(_coerce(item_tp, item))
            except (TypeError, ValueError):
                continue
        return items
    if is_dataclass(tp):
        if not isinstance(value, dict):
            raise TypeError("expected an object")
        return dataclass_from_dict(tp, value)
    if isinstance(tp, type) and issubclass(tp, Enum):
        return tp(value)
    if tp is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int | float):
            return bool(value)
        raise TypeError("expected a boolean")
    if tp is int:
        if isinstance(value, bool):
            raise TypeError("expected an integer")
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, str):
            return int(float(value.strip()))
        raise TypeError("expected an integer")
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError("expected a number")
        return float(value)
    if tp is str:
        if isinstance(value, str):
            return value
        raise TypeError("expected a string")
    return value


def dataclass_from_dict(cls: type[T], data: dict[str, Any]) -> T:
    """Build *cls* from a dict, skipping unknown keys and falling back to defaults on bad values."""
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            continue
        try:
            kwargs[f.name] = _coerce(hints[f.name], data[f.name])
        except (TypeError, ValueError):
            continue
    return cls(**kwargs)
