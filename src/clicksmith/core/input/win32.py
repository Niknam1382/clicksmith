"""Native Windows backend built on SendInput.

No third-party dependency and the lowest latency available from user mode. Uses a *private*
``WinDLL`` handle so the argument types declared here never collide with other libraries (such as
pynput) that configure the shared ``ctypes.windll.user32`` object.
"""

from __future__ import annotations

import ctypes

from ..keys import normalize_key
from ..models import Button
from .base import InputBackend

DWORD = ctypes.c_uint32
WORD = ctypes.c_uint16
LONG = ctypes.c_int32
ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
WHEEL_DELTA = 120

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

_DOWN = {
    Button.LEFT: MOUSEEVENTF_LEFTDOWN,
    Button.RIGHT: MOUSEEVENTF_RIGHTDOWN,
    Button.MIDDLE: MOUSEEVENTF_MIDDLEDOWN,
}
_UP = {
    Button.LEFT: MOUSEEVENTF_LEFTUP,
    Button.RIGHT: MOUSEEVENTF_RIGHTUP,
    Button.MIDDLE: MOUSEEVENTF_MIDDLEUP,
}

_VK = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "delete": 0x2E,
    "win": 0x5B,
    "menu": 0x5D,
    "numlock": 0x90,
    "scrolllock": 0x91,
    **{f"f{i}": 0x70 + i - 1 for i in range(1, 25)},
}
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5D, 0x90}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", LONG),
        ("dy", LONG),
        ("mouseData", DWORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", WORD),
        ("wScan", WORD),
        ("dwFlags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", DWORD), ("u", _INPUT_UNION)]


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


def utf16_units(ch: str) -> list[int]:
    """UTF-16 code units of *ch* (characters outside the BMP become a surrogate pair)."""
    code = ord(ch)
    if code > 0xFFFF:
        code -= 0x10000
        return [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
    return [code]


def _mouse_input(flags: int, data: int = 0) -> INPUT:
    return INPUT(INPUT_MOUSE, _INPUT_UNION(mi=MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)))


def _key_input(vk: int, scan: int, flags: int) -> INPUT:
    return INPUT(INPUT_KEYBOARD, _INPUT_UNION(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))


class Win32Backend(InputBackend):
    name = "win32"

    def __init__(self) -> None:
        if not hasattr(ctypes, "WinDLL"):
            raise OSError("The Win32 backend is only available on Windows")
        user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
        user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
        user32.SendInput.restype = ctypes.c_uint
        user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
        user32.SetCursorPos.restype = ctypes.c_int
        user32.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
        user32.GetCursorPos.restype = ctypes.c_int
        user32.VkKeyScanW.argtypes = (ctypes.c_wchar,)
        user32.VkKeyScanW.restype = ctypes.c_short
        user32.MapVirtualKeyW.argtypes = (ctypes.c_uint, ctypes.c_uint)
        user32.MapVirtualKeyW.restype = ctypes.c_uint
        self._u = user32
        self._vk_cache: dict[str, int] = {}

    # --- plumbing ----------------------------------------------------------------------
    def _send(self, *inputs: INPUT) -> None:
        array = (INPUT * len(inputs))(*inputs)
        sent = self._u.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise OSError(f"SendInput failed (Windows error {ctypes.get_last_error()})")

    def _vk(self, name: str) -> int:
        key = normalize_key(name)
        cached = self._vk_cache.get(key)
        if cached is not None:
            return cached
        vk = _VK.get(key)
        if vk is None and len(key) == 1:
            scanned = self._u.VkKeyScanW(key)
            if scanned != -1:
                vk = scanned & 0xFF
        if vk is None:
            raise ValueError(f"Unknown key: {name!r}")
        self._vk_cache[key] = vk
        return vk

    def _key_event(self, name: str, up: bool) -> INPUT:
        vk = self._vk(name)
        scan = self._u.MapVirtualKeyW(vk, 0)
        flags = (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED else 0) | (KEYEVENTF_KEYUP if up else 0)
        return _key_input(vk, scan, flags)

    # --- mouse -------------------------------------------------------------------------
    def position(self) -> tuple[int, int]:
        point = POINT()
        self._u.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    def move_to(self, x: int, y: int) -> None:
        self._u.SetCursorPos(int(x), int(y))

    def mouse_down(self, button: Button) -> None:
        self._send(_mouse_input(_DOWN[Button(button)]))

    def mouse_up(self, button: Button) -> None:
        self._send(_mouse_input(_UP[Button(button)]))

    def click(self, button: Button, count: int = 1) -> None:
        button = Button(button)
        pair = (_mouse_input(_DOWN[button]), _mouse_input(_UP[button]))
        self._send(*(pair * count))  # one syscall for the whole click

    def scroll(self, dx: int, dy: int) -> None:
        events = []
        if dy:
            events.append(_mouse_input(MOUSEEVENTF_WHEEL, dy * WHEEL_DELTA))
        if dx:
            events.append(_mouse_input(MOUSEEVENTF_HWHEEL, dx * WHEEL_DELTA))
        if events:
            self._send(*events)

    # --- keyboard ----------------------------------------------------------------------
    def key_down(self, key: str) -> None:
        self._send(self._key_event(key, up=False))

    def key_up(self, key: str) -> None:
        self._send(self._key_event(key, up=True))

    def type_char(self, ch: str) -> None:
        events = []
        for unit in utf16_units(ch):
            events.append(_key_input(0, unit, KEYEVENTF_UNICODE))
            events.append(_key_input(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        self._send(*events)

    def type_newline(self) -> None:
        self._send(
            self._key_event("shift", up=False),
            self._key_event("enter", up=False),
            self._key_event("enter", up=True),
            self._key_event("shift", up=True),
        )
