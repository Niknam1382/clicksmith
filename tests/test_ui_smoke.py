"""GUI smoke tests. They run only where PySide6 is installed (skipped otherwise)."""

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAVE_QT = True
except Exception:  # ImportError, or missing system libraries
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 is not available")
class MainWindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        from clicksmith.core import i18n

        i18n.set_language("en")

    def make_window(self):
        from clicksmith.core.engine import Engine
        from clicksmith.core.input import FakeBackend
        from clicksmith.core.storage import AppSettings, ProfileStore, SettingsStore
        from clicksmith.ui.bridge import AppContext, Bridge
        from clicksmith.ui.main_window import MainWindow

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        bridge = Bridge()
        backend = FakeBackend()
        engine = Engine(backend, on_state=bridge.emit_state)
        ctx = AppContext(
            backend,
            engine,
            AppSettings(),
            SettingsStore(Path(tmp.name) / "settings.json"),
            ProfileStore(Path(tmp.name) / "profiles"),
            None,
            bridge,
        )
        window = MainWindow(ctx)
        self.addCleanup(window.shutdown)
        return window, backend, engine

    def test_form_drives_a_real_run(self):
        window, backend, engine = self.make_window()
        window.ms_spin.setValue(1)
        window.stop_combo.setCurrentIndex(window.stop_combo.findData("count"))
        window.count_spin.setValue(3)
        window.failsafe_check.setChecked(False)
        window.awake_check.setChecked(False)
        window.delay_spin.setValue(0)
        self.assertEqual(window.profile.stop.count, 3)  # the form is mirrored into the profile
        window.start_run("hotkey")
        self.assertTrue(engine.wait(5))
        self.app.processEvents()
        self.assertEqual(backend.click_count, 3)
        self.assertIn("Default", window.store.names())

    def test_macro_table_reflects_the_profile(self):
        from clicksmith.core.models import Step, StepType

        window, _backend, _engine = self.make_window()
        window.profile.steps.append(Step(type=StepType.TEXT, text="hello"))
        window.profile.steps.append(Step(type=StepType.KEY, keys="Enter"))
        window._refresh_steps(0)
        self.assertEqual(window.steps_table.rowCount(), 2)
        window._move_step(1)
        self.assertEqual(window.profile.steps[1].type, StepType.TEXT)

    def test_invalid_macro_is_refused(self):
        window, backend, engine = self.make_window()
        window.tabs.setCurrentIndex(1)  # macro mode with no steps
        window._warn = lambda text: setattr(self, "warning", text)
        window.start_run("button")
        self.assertFalse(engine.running)
        self.assertIn("no steps", self.warning)
        self.assertEqual(backend.click_count, 0)

    def test_persian_ui_builds_right_to_left(self):
        from clicksmith.core import i18n

        i18n.set_language("fa")
        window, _backend, _engine = self.make_window()
        self.assertIn("شروع", window.start_btn.text())


if __name__ == "__main__":
    unittest.main()
