"""Pure scheduling helpers (no threads, no GUI)."""

from __future__ import annotations

import datetime as dt

from .models import Schedule, parse_time_str


def next_run(schedule: Schedule, now: dt.datetime) -> dt.datetime | None:
    """Next moment strictly after *now* (naive local time) at which *schedule* fires."""
    if not schedule.enabled:
        return None
    h, m, s = parse_time_str(schedule.time)
    days = set(schedule.days) or set(range(7))
    for offset in range(8):
        day = now.date() + dt.timedelta(days=offset)
        candidate = dt.datetime.combine(day, dt.time(h, m, s))
        if candidate.weekday() in days and candidate > now:
            return candidate
    return None


def fmt_hms(seconds: float) -> str:
    """Format a duration as HH:MM:SS (hours may exceed 24)."""
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
