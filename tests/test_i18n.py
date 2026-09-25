import ast
import re
import unittest
from pathlib import Path

from clicksmith.core import i18n
from clicksmith.core.translations import FA

SRC = Path(__file__).resolve().parents[1] / "src" / "clicksmith"


def ui_strings() -> dict[str, str]:
    """Every string literal that is passed to ``tr(...)`` anywhere in the package."""
    found: dict[str, str] = {}
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "translations.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            is_tr = isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            if is_tr and node.func.id == "tr" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.setdefault(arg.value, path.name)
    return found


class I18nTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_every_ui_string_has_a_persian_translation(self):
        missing = sorted(text for text in ui_strings() if text not in FA)
        self.assertEqual(missing, [], "add these strings to translations.FA")

    def test_no_stale_translations(self):
        used = ui_strings()
        stale = sorted(text for text in FA if text not in used)
        self.assertEqual(stale, [], "these translations are no longer used by the UI")

    def test_placeholders_are_preserved(self):
        pattern = re.compile(r"\{[a-z_]+\}")
        for english, persian in FA.items():
            self.assertEqual(
                sorted(pattern.findall(english)), sorted(pattern.findall(persian)), english
            )

    def test_language_switching(self):
        i18n.set_language("fa")
        self.assertEqual(i18n.tr("Start"), "شروع")
        self.assertTrue(i18n.is_rtl())
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Start"), "Start")
        self.assertFalse(i18n.is_rtl())
        i18n.set_language("xx")  # unknown code falls back to English
        self.assertEqual(i18n.get_language(), "en")

    def test_untranslated_text_falls_back_to_english(self):
        i18n.set_language("fa")
        self.assertEqual(i18n.tr("Not in the table"), "Not in the table")


if __name__ == "__main__":
    unittest.main()
