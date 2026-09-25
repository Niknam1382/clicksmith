"""Where Clicksmith keeps its data. Supports a portable mode next to the executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Clicksmith"


def app_dir() -> Path:
    """Folder of the executable (frozen build) or of the source checkout."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def is_portable() -> bool:
    """Portable mode: env CLICKSMITH_PORTABLE=1 or an empty ``portable.flag`` beside the exe."""
    return os.environ.get("CLICKSMITH_PORTABLE") == "1" or (app_dir() / "portable.flag").exists()


def _default_base() -> Path:
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    root = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(root) / APP_DIR_NAME.lower()


def data_dir() -> Path:
    override = os.environ.get("CLICKSMITH_HOME")
    if override:
        base = Path(override)
    elif is_portable():
        base = app_dir() / "data"
    else:
        base = _default_base()
    base.mkdir(parents=True, exist_ok=True)
    return base


def profiles_dir() -> Path:
    path = data_dir() / "profiles"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def asset_path(name: str) -> Path:
    """Bundled resource; works from a checkout and inside a PyInstaller bundle."""
    return Path(__file__).resolve().parents[1] / "assets" / name
