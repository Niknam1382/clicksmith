"""Persistent application settings and profile storage (atomic JSON files)."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .models import Profile, dataclass_from_dict, dataclass_to_dict


@dataclass
class AppSettings:
    language: str = "en"
    theme: str = "dark"
    hotkey_toggle: str = "F6"
    hotkey_capture: str = "F7"
    hotkey_panic: str = "F8"
    close_to_tray: bool = True
    always_on_top: bool = False
    check_updates: bool = False
    last_profile: str = "Default"


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temp file + rename so a crash can never leave a half-written JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.settings_path()

    def load(self) -> AppSettings:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return dataclass_from_dict(AppSettings, data)
        except (OSError, ValueError):
            pass
        return AppSettings()

    def save(self, settings: AppSettings) -> None:
        text = json.dumps(dataclass_to_dict(settings), indent=2, ensure_ascii=False)
        atomic_write_text(self.path, text + "\n")


_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(name: str) -> str:
    cleaned = _ILLEGAL.sub("_", name).strip(" .")
    return cleaned[:80] or "profile"


def load_profile_file(path: Path | str) -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("A profile file must contain a JSON object")
    profile = Profile.from_dict(data)
    if "name" not in data:
        profile.name = Path(path).stem
    return profile


def save_profile_file(profile: Profile, path: Path | str) -> None:
    profile.normalize()
    text = json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
    atomic_write_text(Path(path), text + "\n")


class ProfileStore:
    """One ``<name>.json`` file per profile inside the profiles folder."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or paths.profiles_dir()
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.directory / f"{safe_filename(name)}.json"

    def names(self) -> list[str]:
        return sorted((p.stem for p in self.directory.glob("*.json")), key=str.casefold)

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def load(self, name: str) -> Profile:
        path = self._path(name)
        profile = load_profile_file(path)
        profile.name = path.stem
        return profile

    def save(self, profile: Profile) -> Path:
        path = self._path(profile.name)
        save_profile_file(profile, path)
        return path

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def unique_name(self, base: str) -> str:
        if not self.exists(base):
            return base
        n = 2
        while self.exists(f"{base} ({n})"):
            n += 1
        return f"{base} ({n})"

    def import_file(self, source: Path | str) -> Profile:
        profile = load_profile_file(source)
        profile.name = self.unique_name(safe_filename(profile.name))
        self.save(profile)
        return profile

    def rename(self, old: str, new: str) -> Profile:
        profile = self.load(old)
        profile.name = new
        self.save(profile)
        if safe_filename(old) != safe_filename(new):
            self.delete(old)
        return profile
