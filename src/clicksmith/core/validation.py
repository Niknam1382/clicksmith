"""Blocking problems that should stop a profile from being started."""

from __future__ import annotations

from .i18n import tr
from .keys import MODIFIERS, is_valid_key, parse_combo
from .models import Profile, RunMode, StepType, TargetMode

_POSITIONAL = (StepType.CLICK, StepType.MOVE, StepType.DRAG, StepType.SCROLL)


def problems(profile: Profile) -> list[str]:
    """Return human-readable reasons why *profile* cannot run (empty list = OK)."""
    found: list[str] = []
    failsafe = profile.safety.failsafe_corner

    if profile.mode == RunMode.CLICKER:
        target = profile.target
        if failsafe and target.mode == TargetMode.FIXED and (target.x, target.y) == (0, 0):
            found.append(
                tr("The fixed target is (0, 0), the emergency-stop corner. Pick a target first.")
            )
        if target.mode == TargetMode.AREA and (target.x, target.y, target.x2, target.y2) == (
            0,
            0,
            0,
            0,
        ):
            found.append(tr("The random area is empty. Pick its two corners first."))
        return found

    if not profile.steps:
        found.append(tr("The macro has no steps. Add some or record them."))
    for n, step in enumerate(profile.steps, start=1):
        if step.type == StepType.KEY:
            keys = parse_combo(step.keys)
            valid = keys and all(is_valid_key(k) for k in keys)
            if not valid or all(k in MODIFIERS for k in keys):
                found.append(
                    tr("Step {n}: unknown key combination '{keys}'.").format(n=n, keys=step.keys)
                )
        elif step.type == StepType.TEXT and not step.text:
            found.append(tr("Step {n}: the text to type is empty.").format(n=n))
        elif (
            step.type in _POSITIONAL
            and failsafe
            and not step.use_cursor
            and (step.x, step.y) == (0, 0)
        ):
            found.append(
                tr("Step {n}: the position is (0, 0), the emergency-stop corner.").format(n=n)
            )
    return found
