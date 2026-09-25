"""Regenerate profiles/examples/*.json from the data model (keeps them schema-correct)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clicksmith.core.models import (  # noqa: E402
    Button,
    ClickSpec,
    Interval,
    Profile,
    RunMode,
    Safety,
    Schedule,
    Step,
    StepType,
    StopMode,
    StopRule,
    Target,
    TargetMode,
)


def examples() -> dict[str, Profile]:
    fast = Profile(
        name="Fast clicker (20 per second)",
        interval=Interval(millis=50, jitter_pct=10),
        safety=Safety(start_delay_s=3),
    )

    human = Profile(
        name="Human-like area clicker",
        interval=Interval(seconds=1, millis=200, jitter_pct=35),
        click=ClickSpec(hold_ms=40),
        target=Target(TargetMode.AREA, x=400, y=300, x2=560, y2=380),
        stop=StopRule(StopMode.COUNT, count=200),
        safety=Safety(stop_on_mouse_move=True),
    )

    daily = Profile(
        name="Daily 09:00 click",
        target=Target(TargetMode.FIXED, x=640, y=400),
        stop=StopRule(StopMode.COUNT, count=1),
        schedule=Schedule(enabled=True, time="09:00:00", days=[0, 1, 2, 3, 4], once=False),
    )

    periodic = Profile(
        name="Periodic paste and send",
        mode=RunMode.MACRO,
        interval=Interval(hours=5, minutes=1, millis=0),
        steps=[
            Step(type=StepType.CLICK, x=640, y=120, delay_after_ms=800),
            Step(type=StepType.CLICK, x=640, y=700, delay_after_ms=400),
            Step(
                type=StepType.TEXT,
                text="Hello 👋\nسلام! این یک پیام خودکار است.",
                char_delay_ms=30,
                delay_after_ms=500,
            ),
            Step(type=StepType.CLICK, x=1180, y=700, delay_after_ms=300),
        ],
        safety=Safety(stop_on_mouse_move=False, prevent_sleep=True),
    )

    refresh = Profile(
        name="Refresh a page every 30 seconds",
        mode=RunMode.MACRO,
        interval=Interval(seconds=30, millis=0, jitter_pct=10),
        steps=[Step(type=StepType.KEY, keys="F5", delay_after_ms=500)],
    )

    scroll = Profile(
        name="Slow auto-scroll",
        mode=RunMode.MACRO,
        interval=Interval(seconds=2, millis=0),
        steps=[
            Step(type=StepType.SCROLL, use_cursor=True, dy=-3, delay_after_ms=0),
        ],
        stop=StopRule(StopMode.DURATION, duration_s=300),
    )

    drag = Profile(
        name="Drag and drop",
        mode=RunMode.MACRO,
        interval=Interval(seconds=5, millis=0),
        steps=[
            Step(
                type=StepType.DRAG,
                button=Button.LEFT,
                x=300,
                y=400,
                x2=700,
                y2=400,
                duration_ms=600,
                delay_after_ms=300,
            )
        ],
        stop=StopRule(StopMode.COUNT, count=10),
    )
    return {
        "fast-clicker": fast,
        "human-like-area-clicker": human,
        "daily-9am-click": daily,
        "periodic-paste-and-send": periodic,
        "refresh-page-every-30s": refresh,
        "slow-auto-scroll": scroll,
        "drag-and-drop": drag,
    }


def main() -> None:
    out = ROOT / "profiles" / "examples"
    out.mkdir(parents=True, exist_ok=True)
    for filename, profile in examples().items():
        text = json.dumps(profile.normalize().to_dict(), indent=2, ensure_ascii=False)
        (out / f"{filename}.json").write_text(text + "\n", encoding="utf-8")
        print("wrote", out / f"{filename}.json")


if __name__ == "__main__":
    main()
