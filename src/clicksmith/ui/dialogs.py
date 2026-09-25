"""Dialogs: the macro step editor and the application settings."""

from __future__ import annotations

import copy

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.hotkeys import to_pynput
from ..core.i18n import LANGUAGES, tr
from ..core.keys import is_valid_key, parse_combo
from ..core.models import Button, Step, StepType
from ..core.storage import AppSettings
from .picker import PickerSession
from .theme import tokens
from .widgets import enum_or, int_or, make_combo, make_label, make_row, make_spin, set_data

# Which optional rows each step type shows ("type" and "delay" are always visible).
_VISIBLE = {
    "click": {"use_cursor", "pos", "button", "clicks", "hold"},
    "move": {"pos", "duration"},
    "drag": {"pos", "end", "button", "duration"},
    "scroll": {"use_cursor", "pos", "scroll"},
    "text": {"text", "char_delay"},
    "key": {"keys"},
    "wait": set(),
}


class StepDialog(QDialog):
    """Create or edit one macro step."""

    def __init__(self, parent, backend, step: Step | None = None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._step = copy.deepcopy(step) if step is not None else Step()
        self.setWindowTitle(tr("Edit step") if step is not None else tr("Add step"))
        self.setMinimumWidth(500)

        self.type_combo = make_combo(
            [
                (tr("Click"), "click"),
                (tr("Move mouse"), "move"),
                (tr("Drag"), "drag"),
                (tr("Scroll"), "scroll"),
                (tr("Type text"), "text"),
                (tr("Press keys"), "key"),
                (tr("Wait"), "wait"),
            ]
        )
        self.cursor_check = QCheckBox(tr("Use the current cursor position"))
        self.x_spin = make_spin(-32768, 32767, width=90)
        self.y_spin = make_spin(-32768, 32767, width=90)
        self.pick_start_btn = QPushButton(tr("Pick on screen..."))
        self.pos_row = make_row(
            QLabel("X"), self.x_spin, QLabel("Y"), self.y_spin, self.pick_start_btn
        )
        self.x2_spin = make_spin(-32768, 32767, width=90)
        self.y2_spin = make_spin(-32768, 32767, width=90)
        self.pick_end_btn = QPushButton(tr("Pick on screen..."))
        self.end_row = make_row(
            QLabel("X"), self.x2_spin, QLabel("Y"), self.y2_spin, self.pick_end_btn
        )
        self.button_combo = make_combo(
            [(tr("Left"), "left"), (tr("Right"), "right"), (tr("Middle"), "middle")]
        )
        self.clicks_combo = make_combo(
            [(tr("Single click"), 1), (tr("Double click"), 2), (tr("Triple click"), 3)]
        )
        self.hold_spin = make_spin(0, 60_000, " ms")
        self.duration_spin = make_spin(0, 600_000, " ms")
        self.dy_spin = make_spin(-10_000, 10_000, width=90)
        self.dx_spin = make_spin(-10_000, 10_000, width=90)
        self.scroll_row = make_row(
            QLabel(tr("Vertical")), self.dy_spin, QLabel(tr("Horizontal")), self.dx_spin
        )
        self.text_edit = QPlainTextEdit()
        self.text_edit.setMinimumHeight(96)
        self.char_delay_spin = make_spin(0, 5000, " ms")
        self.keys_edit = QLineEdit()
        self.keys_edit.setPlaceholderText("Ctrl+V")
        keys_field = QWidget()
        keys_layout = QVBoxLayout(keys_field)
        keys_layout.setContentsMargins(0, 0, 0, 0)
        keys_layout.addWidget(self.keys_edit)
        keys_layout.addWidget(
            make_label(tr("Examples: Enter, Ctrl+V, Alt+Tab, F5, Ctrl+Shift+T"), wrap=True)
        )
        self.delay_spin = make_spin(0, 86_400_000, " ms")

        self.form = QFormLayout()
        self._rows: dict[str, QWidget] = {}
        for name, label, widget in (
            ("type", tr("Action"), self.type_combo),
            ("use_cursor", "", self.cursor_check),
            ("pos", tr("Position"), self.pos_row),
            ("end", tr("Drop position"), self.end_row),
            ("button", tr("Mouse button"), self.button_combo),
            ("clicks", tr("Click type"), self.clicks_combo),
            ("hold", tr("Hold each click for"), self.hold_spin),
            ("duration", tr("Movement time"), self.duration_spin),
            ("scroll", tr("Scroll (notches)"), self.scroll_row),
            ("text", tr("Text to type"), self.text_edit),
            ("char_delay", tr("Delay between characters"), self.char_delay_spin),
            ("keys", tr("Keys"), keys_field),
            ("delay", tr("Pause after this step"), self.delay_spin),
        ):
            self.form.addRow(label, widget)
            self._rows[name] = widget

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(buttons)

        self._load()
        self._update_rows()
        self.type_combo.currentIndexChanged.connect(self._update_rows)
        self.cursor_check.toggled.connect(self._update_rows)
        self.pick_start_btn.clicked.connect(lambda _=False: self._pick("start"))
        self.pick_end_btn.clicked.connect(lambda _=False: self._pick("end"))

    # ------------------------------------------------------------------ state <-> widgets
    def _load(self) -> None:
        s = self._step
        set_data(self.type_combo, s.type.value)
        self.cursor_check.setChecked(s.use_cursor)
        self.x_spin.setValue(s.x)
        self.y_spin.setValue(s.y)
        self.x2_spin.setValue(s.x2)
        self.y2_spin.setValue(s.y2)
        set_data(self.button_combo, s.button.value)
        set_data(self.clicks_combo, s.clicks)
        self.hold_spin.setValue(s.hold_ms)
        self.duration_spin.setValue(s.duration_ms)
        self.dy_spin.setValue(s.dy)
        self.dx_spin.setValue(s.dx)
        self.text_edit.setPlainText(s.text)
        self.char_delay_spin.setValue(s.char_delay_ms)
        self.keys_edit.setText(s.keys)
        self.delay_spin.setValue(s.delay_after_ms)

    def result_step(self) -> Step:
        s = copy.deepcopy(self._step)
        s.type = enum_or(StepType, self.type_combo.currentData(), StepType.CLICK)
        s.use_cursor = self.cursor_check.isChecked()
        s.x, s.y = self.x_spin.value(), self.y_spin.value()
        s.x2, s.y2 = self.x2_spin.value(), self.y2_spin.value()
        s.button = enum_or(Button, self.button_combo.currentData(), Button.LEFT)
        s.clicks = int_or(self.clicks_combo.currentData(), 1)
        s.hold_ms = self.hold_spin.value()
        s.duration_ms = self.duration_spin.value()
        s.dy, s.dx = self.dy_spin.value(), self.dx_spin.value()
        s.text = self.text_edit.toPlainText()
        s.char_delay_ms = self.char_delay_spin.value()
        s.keys = self.keys_edit.text().strip()
        s.delay_after_ms = self.delay_spin.value()
        s.normalize()
        return s

    def _update_rows(self, *_args) -> None:
        kind = str(self.type_combo.currentData())
        visible = _VISIBLE.get(kind, set())
        for name, widget in self._rows.items():
            if name not in ("type", "delay"):
                self.form.setRowVisible(widget, name in visible)
        follows_cursor = kind in ("click", "scroll") and self.cursor_check.isChecked()
        self.pos_row.setEnabled(not follows_cursor)
        label = self.form.labelForField(self.delay_spin)
        if isinstance(label, QLabel):
            label.setText(tr("Wait for") if kind == "wait" else tr("Pause after this step"))

    def _pick(self, which: str) -> None:
        hint = tr("Click the target position. Esc or right-click cancels.")
        session = PickerSession(self, self._backend, hint, tokens()["accent"])
        session.finished.connect(lambda result, w=which: self._on_picked(w, result))
        session.start()

    def _on_picked(self, which: str, result) -> None:
        if result is None:
            return
        x, y = result
        if which == "start":
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
        else:
            self.x2_spin.setValue(x)
            self.y2_spin.setValue(y)

    def _on_accept(self) -> None:
        step = self.result_step()
        if step.type == StepType.KEY:
            keys = parse_combo(step.keys)
            if not keys or not all(is_valid_key(k) for k in keys):
                QMessageBox.warning(self, tr("Add step"), tr("That key combination is not valid."))
                return
        if step.type == StepType.TEXT and not step.text:
            QMessageBox.warning(self, tr("Add step"), tr("Enter the text to type."))
            return
        self.accept()


def _hotkey_edit(text: str) -> QKeySequenceEdit:
    edit = QKeySequenceEdit(QKeySequence(text))
    try:
        edit.setMaximumSequenceLength(1)
    except AttributeError:  # Qt older than 6.5
        pass
    return edit


def _combo_of(edit: QKeySequenceEdit) -> str:
    return edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings: AppSettings) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Settings"))
        self.setMinimumWidth(480)

        self.lang_combo = make_combo([(name, code) for code, name in LANGUAGES.items()])
        set_data(self.lang_combo, settings.language)
        self.theme_combo = make_combo([(tr("Dark"), "dark"), (tr("Light"), "light")])
        set_data(self.theme_combo, settings.theme)
        self.tray_check = QCheckBox(tr("Keep running in the tray when the window is closed"))
        self.tray_check.setChecked(settings.close_to_tray)
        self.top_check = QCheckBox(tr("Keep the window above other windows"))
        self.top_check.setChecked(settings.always_on_top)
        self.update_check = QCheckBox(tr("Check for updates when Clicksmith starts"))
        self.update_check.setChecked(settings.check_updates)
        self.toggle_edit = _hotkey_edit(settings.hotkey_toggle)
        self.capture_edit = _hotkey_edit(settings.hotkey_capture)
        self.panic_edit = _hotkey_edit(settings.hotkey_panic)

        form = QFormLayout()
        form.addRow(tr("Language"), self.lang_combo)
        form.addRow(make_label(tr("A language change applies after restarting."), wrap=True))
        form.addRow(tr("Theme"), self.theme_combo)
        form.addRow(self.tray_check)
        form.addRow(self.top_check)
        form.addRow(self.update_check)
        form.addRow(
            make_label(tr("Global hotkeys work even while Clicksmith is in the background."), wrap=True)
        )
        form.addRow(tr("Start / stop"), self.toggle_edit)
        form.addRow(tr("Capture cursor position"), self.capture_edit)
        form.addRow(tr("Emergency stop"), self.panic_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        combos = [_combo_of(e) for e in (self.toggle_edit, self.capture_edit, self.panic_edit)]
        for combo in combos:
            try:
                to_pynput(combo)
            except ValueError as exc:
                QMessageBox.warning(
                    self, tr("Settings"), tr("Invalid hotkey: {error}").format(error=exc)
                )
                return
        if len({tuple(parse_combo(c)) for c in combos}) != len(combos):
            QMessageBox.warning(self, tr("Settings"), tr("Each action needs its own hotkey."))
            return
        super().accept()

    def apply_to(self, settings: AppSettings) -> None:
        settings.language = str(self.lang_combo.currentData() or "en")
        settings.theme = str(self.theme_combo.currentData() or "dark")
        settings.close_to_tray = self.tray_check.isChecked()
        settings.always_on_top = self.top_check.isChecked()
        settings.check_updates = self.update_check.isChecked()
        settings.hotkey_toggle = _combo_of(self.toggle_edit)
        settings.hotkey_capture = _combo_of(self.capture_edit)
        settings.hotkey_panic = _combo_of(self.panic_edit)
