"""Small OS helpers (Windows-specific parts degrade to no-ops elsewhere)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from contextlib import contextmanager

IS_WINDOWS = sys.platform == "win32"

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def _dll(name: str):
    """A private DLL handle, so our argtypes never clash with other libraries' (e.g. pynput)."""
    return ctypes.WinDLL(name, use_last_error=True)  # type: ignore[attr-defined]


def enable_dpi_awareness() -> None:
    """Make coordinates physical pixels. Qt does this itself, so only the CLI needs it."""
    if not IS_WINDOWS:
        return
    try:
        _dll("user32").SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
        return
    except (OSError, AttributeError):
        pass
    try:
        _dll("shcore").SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        try:
            _dll("user32").SetProcessDPIAware()
        except (OSError, AttributeError):
            pass


def set_app_user_model_id(app_id: str) -> None:
    """Give the process its own taskbar identity so the custom icon is shown."""
    if not IS_WINDOWS:
        return
    try:
        _dll("shell32").SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(app_id))
    except (OSError, AttributeError):
        pass


def is_admin() -> bool:
    if not IS_WINDOWS:
        return hasattr(os, "geteuid") and os.geteuid() == 0
    try:
        return bool(_dll("shell32").IsUserAnAdmin())
    except (OSError, AttributeError):
        return False


def relaunch_as_admin() -> bool:
    """Ask Windows (UAC prompt) to start a new elevated copy of this program."""
    if not IS_WINDOWS:
        return False
    forwarded = [a for a in sys.argv[1:] if a != "--wait-lock"] + ["--wait-lock"]
    if getattr(sys, "frozen", False):
        exe, args = sys.executable, forwarded
    else:
        exe, args = sys.executable, ["-m", "clicksmith", *forwarded]
    shell32 = _dll("shell32")
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    shell32.ShellExecuteW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_int,
    ]
    result = shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), None, 1)
    return (result or 0) > 32


def attach_parent_console() -> None:
    """Let a windowed (no console) exe print to the terminal that launched it."""
    if not IS_WINDOWS:
        return
    try:
        if _dll("kernel32").AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
            sys.stderr = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
    except (OSError, AttributeError):
        pass
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115


def open_path(path: str | os.PathLike[str]) -> None:
    """Open a file or folder with the OS default handler."""
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


@contextmanager
def high_resolution_timer(period_ms: int = 1):
    """Request 1 ms system timer resolution (default is ~15.6 ms on Windows)."""
    winmm = None
    if IS_WINDOWS:
        try:
            winmm = _dll("winmm")
            winmm.timeBeginPeriod(period_ms)
        except (OSError, AttributeError):
            winmm = None
    try:
        yield
    finally:
        if winmm is not None:
            winmm.timeEndPeriod(period_ms)


@contextmanager
def keep_awake(enabled: bool = True):
    """Prevent system sleep / display-off for the calling thread while active."""
    kernel32 = None
    if enabled and IS_WINDOWS:
        try:
            kernel32 = _dll("kernel32")
            kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint]
            kernel32.SetThreadExecutionState.restype = ctypes.c_uint
            kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
            )
        except (OSError, AttributeError):
            kernel32 = None
    try:
        yield
    finally:
        if kernel32 is not None:
            kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
