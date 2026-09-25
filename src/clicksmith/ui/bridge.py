"""Glue between worker threads and the GUI thread, plus the shared application context."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..core.engine import Engine, RunState, StopReason
from ..core.hotkeys import HotkeyManager
from ..core.input.base import InputBackend
from ..core.storage import AppSettings, ProfileStore, SettingsStore


class Bridge(QObject):
    """Signals emitted from any thread are delivered on the GUI thread."""

    state_changed = Signal(str, str)  # engine state, stop reason ("" while active)
    hotkey = Signal(str)  # "toggle" | "capture" | "panic"
    log_line = Signal(str)
    record_stop = Signal()
    update_result = Signal(object)  # ReleaseInfo, or the Exception that occurred

    def emit_state(self, state: RunState, reason: StopReason | None) -> None:
        self.state_changed.emit(state.value, reason.value if reason else "")


class QtLogHandler(logging.Handler):
    """Forwards log records to the activity log panel."""

    def __init__(self, bridge: Bridge) -> None:
        super().__init__(logging.INFO)
        self._bridge = bridge
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bridge.log_line.emit(self.format(record))
        except Exception:
            self.handleError(record)


@dataclass
class AppContext:
    backend: InputBackend
    engine: Engine
    settings: AppSettings
    settings_store: SettingsStore
    profiles: ProfileStore
    hotkeys: HotkeyManager | None
    bridge: Bridge
