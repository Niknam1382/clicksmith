import unittest

from clicksmith.core.hotkeys import HotkeyManager, to_pynput
from clicksmith.core.keys import format_combo, is_valid_key, normalize_key, parse_combo


class KeyTests(unittest.TestCase):
    def test_normalize(self):
        cases = {
            "Ctrl_L": "ctrl",
            "PgUp": "pageup",
            "Return": "enter",
            "A": "a",
            " ": "space",
            "Page_Down": "pagedown",
            "cmd_r": "win",
            "Meta": "win",
            "Del": "delete",
            "F12": "f12",
            "5": "5",
        }
        for raw, expected in cases.items():
            self.assertEqual(normalize_key(raw), expected, raw)

    def test_parse_combo(self):
        self.assertEqual(parse_combo("Ctrl + Shift + V"), ["ctrl", "shift", "v"])
        self.assertEqual(parse_combo("v+ctrl"), ["ctrl", "v"])
        self.assertEqual(parse_combo("Ctrl++"), ["ctrl", "+"])
        self.assertEqual(parse_combo(""), [])
        self.assertEqual(format_combo(["ctrl", "v"]), "Ctrl+V")

    def test_validity(self):
        self.assertTrue(is_valid_key("f5"))
        self.assertTrue(is_valid_key("x"))
        self.assertFalse(is_valid_key("banana"))


class HotkeyTests(unittest.TestCase):
    def test_to_pynput(self):
        self.assertEqual(to_pynput("F6"), "<f6>")
        self.assertEqual(to_pynput("Ctrl+Shift+F6"), "<ctrl>+<shift>+<f6>")
        self.assertEqual(to_pynput("Alt+A"), "<alt>+a")
        self.assertEqual(to_pynput("Meta+PgUp"), "<cmd>+<page_up>")

    def test_invalid_hotkeys(self):
        for bad in ("", "Ctrl", "Ctrl+Banana"):
            with self.assertRaises(ValueError, msg=bad):
                to_pynput(bad)

    def test_register_reports_bad_bindings(self):
        errors = HotkeyManager().register({"Ctrl": lambda: None})
        self.assertEqual(len(errors), 1)
        self.assertIn("needs a key", errors[0])

    def test_handler_is_debounced_and_isolated(self):
        calls = []
        manager = HotkeyManager(debounce=10)
        fire = manager._wrap("F6", lambda: calls.append(1))
        fire()
        fire()
        self.assertEqual(len(calls), 1)
        failing = HotkeyManager()._wrap("F7", lambda: 1 / 0)
        with self.assertLogs("clicksmith.hotkeys", level="ERROR"):
            failing()  # a crashing handler must be logged, never raised


if __name__ == "__main__":
    unittest.main()
