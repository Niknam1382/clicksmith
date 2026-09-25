import ctypes
import unittest

from clicksmith.core.input import win32


class Win32LayoutTests(unittest.TestCase):
    """The native structures must match the Windows ABI exactly, or SendInput silently fails."""

    def test_input_struct_size(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(win32.INPUT), expected)

    def test_negative_wheel_delta_is_packed_as_dword(self):
        event = win32._mouse_input(win32.MOUSEEVENTF_WHEEL, -120)
        self.assertEqual(event.u.mi.mouseData, 0xFFFFFF88)
        self.assertEqual(event.type, win32.INPUT_MOUSE)

    def test_unicode_key_event_fields(self):
        event = win32._key_input(0, 0x0633, win32.KEYEVENTF_UNICODE)
        self.assertEqual((event.type, event.u.ki.wScan, event.u.ki.dwFlags), (1, 0x0633, 4))

    def test_utf16_units(self):
        self.assertEqual(win32.utf16_units("a"), [0x61])
        self.assertEqual(win32.utf16_units("س"), [0x0633])
        self.assertEqual(win32.utf16_units("\U0001f44b"), [0xD83D, 0xDC4B])  # waving hand emoji


if __name__ == "__main__":
    unittest.main()
