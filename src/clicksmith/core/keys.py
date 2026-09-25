"""Key-name normalisation shared by the input backends, hotkeys and the recorder."""

from __future__ import annotations

MODIFIERS = ("ctrl", "shift", "alt", "win")

_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "return": "enter",
    "ret": "enter",
    "escape": "esc",
    "del": "delete",
    "ins": "insert",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "pgdown": "pagedown",
    "windows": "win",
    "meta": "win",
    "super": "win",
    "cmd": "win",
    "command": "win",
    "option": "alt",
    "altgr": "alt",
    "bksp": "backspace",
    "prtsc": "printscreen",
    "prtscn": "printscreen",
    "print": "printscreen",
    "spacebar": "space",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
}

NAMED_KEYS = frozenset(
    {
        "backspace",
        "tab",
        "enter",
        "esc",
        "space",
        "pageup",
        "pagedown",
        "end",
        "home",
        "left",
        "up",
        "right",
        "down",
        "insert",
        "delete",
        "pause",
        "capslock",
        "numlock",
        "scrolllock",
        "printscreen",
        "menu",
        *MODIFIERS,
        *(f"f{i}" for i in range(1, 25)),
    }
)


def normalize_key(name: str) -> str:
    """Return the canonical lower-case name of a key ("Ctrl_L" -> "ctrl", "PgUp" -> "pageup")."""
    if name == " ":
        return "space"
    raw = name.strip()
    if len(raw) == 1:
        return raw.lower() if raw.isalpha() else raw
    key = raw.lower()
    if key.endswith(("_l", "_r")):
        key = key[:-2]
    key = key.replace("_", "").replace(" ", "").replace("-", "")
    return _ALIASES.get(key, key)


def is_valid_key(name: str) -> bool:
    return name in NAMED_KEYS or len(name) == 1


def parse_combo(text: str) -> list[str]:
    """Split "Ctrl + Shift + V" into ["ctrl", "shift", "v"] (modifiers first)."""
    stripped = text.strip()
    keys = [normalize_key(part) for part in stripped.split("+") if part.strip()]
    if stripped == "+" or stripped.endswith("++"):
        keys.append("+")
    mods = [m for m in MODIFIERS if m in keys]
    others = [k for k in keys if k not in MODIFIERS]
    return mods + others


def format_combo(keys: list[str]) -> str:
    """Human friendly form of a parsed combo: ["ctrl", "v"] -> "Ctrl+V"."""
    return "+".join(k.upper() if len(k) == 1 else k.capitalize() for k in keys)
