"""GUI bootstrap: logging, single-instance guard, QApplication, theme, engine and main window."""

from __future__ import annotations

import logging
import os
import sys
import tempfile

from . import APP_NAME, __version__


def _selftest_checks() -> list[tuple[str, bool, str]]:
    """Checks that prove a (frozen) build is complete. Qt itself is exercised by the caller."""
    from .core import i18n
    from .core.engine import Engine, StopReason
    from .core.input import FakeBackend, create_backend
    from .core.models import Interval, Profile, Safety, StopMode, StopRule
    from .core.paths import asset_path

    results: list[tuple[str, bool, str]] = []

    fake = FakeBackend()
    engine = Engine(fake)
    profile = Profile()
    profile.interval = Interval(millis=1)
    profile.stop = StopRule(StopMode.COUNT, count=5)
    profile.safety = Safety(failsafe_corner=False, prevent_sleep=False, start_delay_s=0)
    engine.start(profile)
    engine.wait(10)
    ok = fake.click_count == 5 and engine.snapshot().reason == StopReason.COMPLETED
    results.append(("engine performs 5 clicks", ok, f"clicks={fake.click_count}"))

    try:
        backend = create_backend()
        results.append(("native input backend loads", True, backend.name))
    except Exception as exc:
        results.append(("native input backend loads", False, repr(exc)))

    try:
        import pynput.keyboard  # noqa: F401
        import pynput.mouse  # noqa: F401

        results.append(("pynput (hotkeys, recorder) imports", True, ""))
    except Exception as exc:
        results.append(("pynput (hotkeys, recorder) imports", False, repr(exc)))

    for name in ("icon.png", "icon.ico"):
        path = asset_path(name)
        results.append((f"asset {name} is bundled", path.exists(), str(path)))

    i18n.set_language("fa")
    results.append(("Persian translation is active", i18n.tr("Start") != "Start", ""))
    i18n.set_language("en")
    return results


def run_gui(minimized: bool = False, selftest: bool = False, wait_lock: bool = False) -> int:
    if selftest:
        os.environ["CLICKSMITH_HOME"] = tempfile.mkdtemp(prefix="clicksmith-selftest-")

    from PySide6.QtCore import QLockFile, Qt, QTimer
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .core import i18n, paths, sysutils
    from .core.engine import Engine
    from .core.hotkeys import HotkeyManager
    from .core.i18n import tr
    from .core.input import FakeBackend, create_backend
    from .core.log import setup_logging
    from .core.storage import ProfileStore, SettingsStore
    from .ui.bridge import AppContext, Bridge, QtLogHandler
    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    setup_logging(console=not getattr(sys, "frozen", False))
    log = logging.getLogger("clicksmith")

    def _excepthook(exc_type, exc, tb) -> None:
        log.critical("Unhandled exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = _excepthook

    settings_store = SettingsStore()
    settings = settings_store.load()
    i18n.set_language(settings.language)

    sysutils.set_app_user_model_id("Clicksmith.App")
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)  # the tray icon keeps the app alive
    app.setWindowIcon(QIcon(str(paths.asset_path("icon.png"))))
    if sysutils.IS_WINDOWS:
        app.setFont(QFont("Segoe UI", 10))
    if i18n.is_rtl():
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    apply_theme(app, settings.theme)

    lock = None
    if not selftest:
        lock = QLockFile(os.path.join(tempfile.gettempdir(), "clicksmith.lock"))
        if not lock.tryLock(8000 if wait_lock else 200):
            QMessageBox.information(
                None,
                APP_NAME,
                tr("Clicksmith is already running. Look for its icon in the system tray."),
            )
            return 0

    bridge = Bridge()
    try:
        backend = FakeBackend() if selftest else create_backend()
    except Exception as exc:
        log.exception("Could not initialise input control")
        QMessageBox.critical(
            None,
            APP_NAME,
            tr("Could not initialise input control: {error}").format(error=exc),
        )
        return 1

    engine = Engine(backend, on_state=bridge.emit_state)
    log_handler = QtLogHandler(bridge)
    log.addHandler(log_handler)
    hotkeys = None if selftest else HotkeyManager()
    ctx = AppContext(backend, engine, settings, settings_store, ProfileStore(), hotkeys, bridge)
    window = MainWindow(ctx)

    exit_code = 0
    if selftest:
        checks = _selftest_checks()
        checks.append(("main window is constructed", window.windowTitle() == APP_NAME, ""))
        QTimer.singleShot(150, app.quit)
        app.exec()
        window.shutdown()
        lines = [f"{'PASS' if ok else 'FAIL'}  {name}  {detail}".rstrip() for name, ok, detail in checks]
        report = "\n".join(lines)
        print(report)
        out = os.environ.get("CLICKSMITH_SELFTEST_OUT")
        if out:
            with open(out, "w", encoding="utf-8") as handle:
                handle.write(report + "\n")
        exit_code = 0 if all(ok for _, ok, _ in checks) else 1
    else:
        if not (minimized and window.has_tray):
            window.show()
        if settings.check_updates:
            QTimer.singleShot(3000, lambda: window.check_updates(True))
        exit_code = app.exec()

    log.removeHandler(log_handler)
    if lock is not None:
        lock.unlock()
    return exit_code
