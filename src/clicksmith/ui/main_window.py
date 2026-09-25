"""The main window."""

from __future__ import annotations

import copy
import datetime as dt
import logging
import threading
import webbrowser

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, REPO, __version__
from ..core import sysutils
from ..core.engine import RunState
from ..core.i18n import tr
from ..core.keys import parse_combo
from ..core.models import (
    Button,
    Profile,
    RunMode,
    Step,
    StepType,
    StopMode,
    StopRule,
    TargetMode,
    parse_time_str,
)
from ..core.paths import asset_path, logs_dir
from ..core.recorder import Recorder
from ..core.scheduler import fmt_hms, next_run
from ..core.storage import safe_filename, save_profile_file
from ..core.updater import fetch_latest, is_newer
from ..core.validation import problems
from .bridge import AppContext
from .dialogs import SettingsDialog, StepDialog
from .picker import PickerSession
from .theme import apply_theme, tokens
from .widgets import (
    Sparkline,
    blocked,
    describe_step,
    enum_or,
    format_delay,
    int_or,
    make_card,
    make_combo,
    make_label,
    make_row,
    make_spin,
    set_data,
    set_prop,
    set_role,
)

log = logging.getLogger("clicksmith.ui")

LEAD_SECONDS = 2.0  # a scheduled run is handed to the engine this long before it is due


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.engine = ctx.engine
        self.backend = ctx.backend
        self.settings = ctx.settings
        self.store = ctx.profiles
        self.profile = Profile()
        self._inputs: list[QWidget] = []
        self._loading = False
        self._quitting = False
        self._fired_due: dt.datetime | None = None
        self._capture_flip = False
        self._recorder: Recorder | None = None
        self._tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._tray_toggle_action: QAction | None = None
        self._tray_hint_shown = False
        self._update_silent = False
        self._on_top = False

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self._save_profile)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(200)
        self._tick_timer.timeout.connect(self._tick)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(asset_path("icon.png"))))
        self.resize(1120, 780)
        self.setMinimumSize(980, 700)

        self._build_ui()
        self._build_menu()
        self._build_tray()
        self._connect_signals()

        self._reload_profiles(self.settings.last_profile)
        self.apply_window_flags()
        self.apply_hotkeys()
        self._update_start_button(False)
        self._tick_timer.start()

    @property
    def has_tray(self) -> bool:
        return self._tray is not None

    # ================================================================== construction
    def _reg(self, widget):
        """Register an input widget: every change re-reads the whole form into the profile."""
        for name in ("valueChanged", "currentIndexChanged", "toggled", "timeChanged"):
            signal = getattr(widget, name, None)
            if signal is not None:
                signal.connect(self._on_edited)
        self._inputs.append(widget)
        return widget

    def _add_action(self, menu: QMenu, text: str, slot) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 12, 20, 10)
        root.setSpacing(12)
        root.addLayout(self._build_header())

        self.editor_area = QWidget()
        body = QHBoxLayout(self.editor_area)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_clicker_tab(), tr("Clicker"))
        self.tabs.addTab(self._build_macro_tab(), tr("Macro"))
        self.tabs.addTab(self._build_schedule_tab(), tr("Schedule"))
        body.addWidget(self.tabs, 5)
        body.addLayout(self._build_side_column(), 3)
        root.addWidget(self.editor_area, 1)
        root.addWidget(self._build_footer())
        root.addWidget(self._build_log())

        self.hint_label = make_label("")
        self.statusBar().addPermanentWidget(self.hint_label)
        if sysutils.is_admin():
            self.statusBar().addPermanentWidget(make_label(tr("Administrator")))

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(asset_path("icon.png"))).scaled(
                40,
                40,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(make_label(APP_NAME, "title"))
        titles.addWidget(make_label(tr("Forge your clicks")))
        row.addWidget(logo)
        row.addLayout(titles)
        row.addStretch(1)
        row.addWidget(make_label(tr("Profile")))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(220)
        self.profile_menu_btn = QToolButton()
        self.profile_menu_btn.setText("⋯")
        self.profile_menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.profile_menu_btn.setMenu(self._build_profile_menu())
        self.state_pill = make_label(tr("Idle"), "pill")
        set_prop(self.state_pill, "state", "idle")
        row.addWidget(self.profile_combo)
        row.addWidget(self.profile_menu_btn)
        row.addSpacing(8)
        row.addWidget(self.state_pill)
        return row

    def _build_profile_menu(self) -> QMenu:
        menu = QMenu(self)
        entries = (
            (tr("New profile..."), self._new_profile),
            (tr("Duplicate"), self._duplicate_profile),
            (tr("Rename..."), self._rename_profile),
            (tr("Delete"), self._delete_profile),
            None,
            (tr("Import..."), self._import_profile),
            (tr("Export..."), self._export_profile),
            None,
            (tr("Open profiles folder"), self._open_profiles_folder),
        )
        for entry in entries:
            if entry is None:
                menu.addSeparator()
            else:
                self._add_action(menu, entry[0], entry[1])
        return menu

    # ------------------------------------------------------------------ clicker tab
    def _build_clicker_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        click_box, cg = make_card(tr("Click"))
        self.button_combo = self._reg(
            make_combo([(tr("Left"), "left"), (tr("Right"), "right"), (tr("Middle"), "middle")])
        )
        self.clicks_combo = self._reg(
            make_combo(
                [(tr("Single click"), 1), (tr("Double click"), 2), (tr("Triple click"), 3)]
            )
        )
        self.hold_spin = self._reg(make_spin(0, 60_000, " ms"))
        self.hold_spin.setToolTip(tr("How long the button stays pressed for every click."))
        cg.addWidget(QLabel(tr("Mouse button")), 0, 0)
        cg.addWidget(self.button_combo, 0, 1)
        cg.addWidget(QLabel(tr("Click type")), 1, 0)
        cg.addWidget(self.clicks_combo, 1, 1)
        cg.addWidget(QLabel(tr("Hold each click for")), 2, 0)
        cg.addWidget(self.hold_spin, 2, 1)
        cg.setColumnStretch(1, 1)
        layout.addWidget(click_box)

        target_box, tg = make_card(tr("Target"))
        self.target_combo = self._reg(
            make_combo(
                [
                    (tr("Follow the cursor"), "cursor"),
                    (tr("Fixed point"), "fixed"),
                    (tr("Random area"), "area"),
                ]
            )
        )
        self.corner_a_label = QLabel(tr("Point"))
        self.x_spin = self._reg(make_spin(-32768, 32767, width=90))
        self.y_spin = self._reg(make_spin(-32768, 32767, width=90))
        self.pick_a_btn = QPushButton(tr("Pick on screen..."))
        self.row_a = make_row(
            self.corner_a_label, QLabel("X"), self.x_spin, QLabel("Y"), self.y_spin, self.pick_a_btn
        )
        self.corner_b_label = QLabel(tr("Bottom-right corner"))
        self.x2_spin = self._reg(make_spin(-32768, 32767, width=90))
        self.y2_spin = self._reg(make_spin(-32768, 32767, width=90))
        self.pick_b_btn = QPushButton(tr("Pick on screen..."))
        self.row_b = make_row(
            self.corner_b_label,
            QLabel("X"),
            self.x2_spin,
            QLabel("Y"),
            self.y2_spin,
            self.pick_b_btn,
        )
        self.jitter_px_spin = self._reg(make_spin(0, 500, " px", 90))
        self.jitter_px_spin.setToolTip(tr("Each click lands a random distance from the point."))
        self.row_j = make_row(QLabel(tr("Random offset")), self.jitter_px_spin)
        self.cursor_hint = make_label(
            tr("Clicks wherever the mouse cursor is. Move it to the target before you start."),
            wrap=True,
        )
        tg.addWidget(self.target_combo, 0, 0)
        tg.addWidget(self.row_a, 1, 0)
        tg.addWidget(self.row_b, 2, 0)
        tg.addWidget(self.row_j, 3, 0)
        tg.addWidget(self.cursor_hint, 4, 0)
        layout.addWidget(target_box)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ macro tab
    def _build_macro_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.add_btn = QPushButton(tr("+ Add step"))
        self.edit_btn = QPushButton(tr("Edit"))
        self.dup_btn = QPushButton(tr("Duplicate"))
        self.del_btn = QPushButton(tr("Delete"))
        self.up_btn = QPushButton("▲")
        self.down_btn = QPushButton("▼")
        self.record_btn = QPushButton(tr("● Record"))
        self.record_btn.setToolTip(tr("Record your mouse and keyboard and turn them into steps."))
        for button in (self.add_btn, self.edit_btn, self.dup_btn, self.del_btn):
            bar.addWidget(button)
        bar.addSpacing(8)
        bar.addWidget(self.up_btn)
        bar.addWidget(self.down_btn)
        bar.addStretch(1)
        bar.addWidget(self.record_btn)
        layout.addLayout(bar)

        self.steps_table = QTableWidget(0, 4)
        self.steps_table.setHorizontalHeaderLabels(
            ["#", tr("Action"), tr("Details"), tr("Pause after")]
        )
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.steps_table.verticalHeader().setVisible(False)
        self.steps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.steps_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.steps_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.steps_table, 1)

        self.macro_hint = make_label("", wrap=True)
        layout.addWidget(self.macro_hint)
        return page

    # ------------------------------------------------------------------ schedule tab
    def _build_schedule_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        box, grid = make_card(tr("Schedule"))
        self.sched_enable = self._reg(QCheckBox(tr("Run this profile automatically")))
        self.sched_time = self._reg(QTimeEdit())
        self.sched_time.setDisplayFormat("HH:mm:ss")
        days_row = QHBoxLayout()
        self.day_checks: list[QCheckBox] = []
        for label in (
            tr("Mon"),
            tr("Tue"),
            tr("Wed"),
            tr("Thu"),
            tr("Fri"),
            tr("Sat"),
            tr("Sun"),
        ):
            check = self._reg(QCheckBox(label))
            self.day_checks.append(check)
            days_row.addWidget(check)
        days_row.addStretch(1)
        self.sched_once = self._reg(QCheckBox(tr("Run once, then switch the schedule off")))
        self.sched_status = make_label("", wrap=True)
        grid.addWidget(self.sched_enable, 0, 0, 1, 2)
        grid.addWidget(QLabel(tr("Start at")), 1, 0)
        grid.addWidget(self.sched_time, 1, 1)
        grid.addWidget(QLabel(tr("On these days")), 2, 0)
        grid.addLayout(days_row, 2, 1)
        grid.addWidget(self.sched_once, 3, 0, 1, 2)
        grid.addWidget(self.sched_status, 4, 0, 1, 2)
        grid.setColumnStretch(1, 1)
        layout.addWidget(box)
        layout.addWidget(
            make_label(
                tr(
                    "Clicksmith must be running (it can sit in the system tray) and the PC must be "
                    "awake and unlocked for a scheduled run to work."
                ),
                wrap=True,
            )
        )
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ shared cards
    def _build_side_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(12)

        self.timing_box, tg = make_card(tr("Click interval"))
        self.h_spin = self._reg(make_spin(0, 9999))
        self.m_spin = self._reg(make_spin(0, 59))
        self.s_spin = self._reg(make_spin(0, 59))
        self.ms_spin = self._reg(make_spin(0, 999))
        for col, (caption, spin) in enumerate(
            (
                (tr("Hours"), self.h_spin),
                (tr("Minutes"), self.m_spin),
                (tr("Seconds"), self.s_spin),
                (tr("Millisec."), self.ms_spin),
            )
        ):
            tg.addWidget(make_label(caption, "caption"), 0, col)
            tg.addWidget(spin, 1, col)
        self.jitter_spin = self._reg(make_spin(0, 100, " %"))
        self.jitter_spin.setToolTip(
            tr("Randomly shortens or lengthens every wait by up to this percentage.")
        )
        tg.addWidget(QLabel(tr("Random variation ±")), 2, 0, 1, 2)
        tg.addWidget(self.jitter_spin, 2, 2, 1, 2)
        self.rate_label = make_label("", wrap=True)
        tg.addWidget(self.rate_label, 3, 0, 1, 4)
        column.addWidget(self.timing_box)

        repeat_box, rg = make_card(tr("Repeat"))
        self.stop_combo = self._reg(
            make_combo(
                [
                    (tr("Until I stop it"), "infinite"),
                    (tr("A number of times"), "count"),
                    (tr("For a duration"), "duration"),
                ]
            )
        )
        self.count_spin = self._reg(make_spin(1, 2_000_000_000))
        self.duration_spin = self._reg(make_spin(1, 10_000_000, " s"))
        rg.addWidget(self.stop_combo, 0, 0)
        rg.addWidget(self.count_spin, 1, 0)
        rg.addWidget(self.duration_spin, 1, 0)
        column.addWidget(repeat_box)

        safety_box, sg = make_card(tr("Safety"))
        self.failsafe_check = self._reg(QCheckBox(tr("Failsafe corner (top-left)")))
        self.failsafe_check.setToolTip(
            tr("Slam the mouse into the top-left corner of the screen to stop everything at once.")
        )
        self.moved_check = self._reg(QCheckBox(tr("Stop if I move the mouse")))
        self.moved_check.setToolTip(
            tr("Works with a fixed point, a random area and macros - not with follow-the-cursor.")
        )
        self.awake_check = self._reg(QCheckBox(tr("Keep the PC awake while running")))
        self.delay_spin = self._reg(make_spin(0, 3600, " s"))
        self.delay_spin.setToolTip(tr("Countdown before a run started with the Start button."))
        sg.addWidget(self.failsafe_check, 0, 0, 1, 2)
        sg.addWidget(self.moved_check, 1, 0, 1, 2)
        sg.addWidget(self.awake_check, 2, 0, 1, 2)
        sg.addWidget(QLabel(tr("Start delay")), 3, 0)
        sg.addWidget(self.delay_spin, 3, 1)
        sg.setColumnStretch(1, 1)
        column.addWidget(safety_box)
        column.addStretch(1)
        return column

    # ------------------------------------------------------------------ footer + log
    def _stat_block(self, caption: str) -> tuple[QWidget, QLabel]:
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        value = make_label("0", "stat")
        col.addWidget(make_label(caption, "caption"))
        col.addWidget(value)
        return holder, value

    def _build_footer(self) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(22)
        block, self.count_value = self._stat_block(tr("Repetitions"))
        row.addWidget(block)
        block, self.cps_value = self._stat_block(tr("Per second"))
        row.addWidget(block)
        block, self.elapsed_value = self._stat_block(tr("Elapsed"))
        row.addWidget(block)
        block, self.next_value = self._stat_block(tr("Next run in"))
        row.addWidget(block)
        self.sparkline = Sparkline(tokens()["accent"])
        row.addWidget(self.sparkline, 1)
        self.test_btn = QPushButton(tr("Test once"))
        self.test_btn.setMinimumHeight(46)
        self.start_btn = QPushButton()
        self.start_btn.setMinimumHeight(46)
        self.start_btn.setMinimumWidth(210)
        set_role(self.start_btn, "primary")
        row.addWidget(self.test_btn)
        row.addWidget(self.start_btn)
        return holder

    def _build_log(self) -> QPlainTextEdit:
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFixedHeight(96)
        self.log_view.setPlaceholderText(tr("Activity log"))
        return self.log_view

    # ------------------------------------------------------------------ menu + tray
    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu(tr("File"))
        self._add_action(file_menu, tr("Import profile..."), self._import_profile)
        self._add_action(file_menu, tr("Export profile..."), self._export_profile)
        file_menu.addSeparator()
        self._add_action(file_menu, tr("Settings..."), self._open_settings)
        file_menu.addSeparator()
        self._add_action(file_menu, tr("Quit"), self.quit_app)

        tools_menu = bar.addMenu(tr("Tools"))
        admin = self._add_action(
            tools_menu, tr("Restart as administrator"), self._restart_as_admin
        )
        admin.setEnabled(sysutils.IS_WINDOWS and not sysutils.is_admin())
        admin.setToolTip(
            tr("Needed to click inside windows that run as administrator (Windows UIPI).")
        )
        self._add_action(tools_menu, tr("Open data folder"), self._open_data_folder)
        self._add_action(tools_menu, tr("Open log file"), self._open_log_file)

        help_menu = bar.addMenu(tr("Help"))
        self._add_action(help_menu, tr("Check for updates"), lambda: self.check_updates(False))
        self._add_action(help_menu, tr("Project page on GitHub"), self._open_project_page)
        self._add_action(help_menu, tr("About Clicksmith"), self._show_about)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip(APP_NAME)
        menu = QMenu(self)
        self._add_action(menu, tr("Show window"), self.show_window)
        self._tray_toggle_action = self._add_action(
            menu, tr("Start"), lambda: self.toggle_run("button")
        )
        menu.addSeparator()
        self._add_action(menu, tr("Quit"), self.quit_app)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray
        self._tray_menu = menu

    def _connect_signals(self) -> None:
        bridge = self.ctx.bridge
        bridge.state_changed.connect(self._on_engine_state)
        bridge.hotkey.connect(self._on_hotkey)
        bridge.log_line.connect(self.log_view.appendPlainText)
        bridge.record_stop.connect(self._finish_recording)
        bridge.update_result.connect(self._on_update_result)

        self.tabs.currentChanged.connect(self._on_edited)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        self.pick_a_btn.clicked.connect(lambda _=False: self._pick("a"))
        self.pick_b_btn.clicked.connect(lambda _=False: self._pick("b"))
        self.add_btn.clicked.connect(self._add_step)
        self.edit_btn.clicked.connect(lambda _=False: self._edit_step(self.steps_table.currentRow()))
        self.dup_btn.clicked.connect(self._duplicate_step)
        self.del_btn.clicked.connect(self._delete_step)
        self.up_btn.clicked.connect(lambda _=False: self._move_step(-1))
        self.down_btn.clicked.connect(lambda _=False: self._move_step(1))
        self.record_btn.clicked.connect(self._start_recording)
        self.steps_table.itemSelectionChanged.connect(self._update_step_buttons)
        self.steps_table.cellDoubleClicked.connect(lambda row, _col: self._edit_step(row))
        self.start_btn.clicked.connect(lambda _=False: self.toggle_run("button"))
        self.test_btn.clicked.connect(lambda _=False: self.start_run("button", once=True))

    # ================================================================== profiles
    def _reload_profiles(self, select: str | None = None) -> None:
        names = self.store.names()
        if not names:
            self.store.save(Profile(name="Default"))
            names = self.store.names()
        chosen = select if select in names else names[0]
        with blocked(self.profile_combo):
            self.profile_combo.clear()
            for name in names:
                self.profile_combo.addItem(name, name)
            self.profile_combo.setCurrentIndex(names.index(chosen))
        self._load_profile(chosen)

    def _load_profile(self, name: str) -> None:
        try:
            profile = self.store.load(name)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self, APP_NAME, tr("Could not load the profile: {error}").format(error=exc)
            )
            profile = Profile(name=name)
        self.profile = profile
        self.settings.last_profile = profile.name
        self._fired_due = None
        self._sync_to_ui()

    def _save_profile(self) -> None:
        self._sync_from_ui()
        try:
            self.store.save(self.profile)
        except OSError as exc:
            log.warning("Could not save the profile: %s", exc)

    def _on_profile_selected(self, _index: int) -> None:
        name = self.profile_combo.currentData()
        if self._loading or not name or name == self.profile.name:
            return
        self._save_profile()
        self._load_profile(str(name))

    def _ask_name(self, title: str, default: str) -> str | None:
        text, accepted = QInputDialog.getText(
            self, title, tr("Profile name:"), QLineEdit.EchoMode.Normal, default
        )
        text = text.strip()
        return text if accepted and text else None

    def _new_profile(self) -> None:
        name = self._ask_name(tr("New profile"), tr("New profile"))
        if name is None:
            return
        self._save_profile()
        name = self.store.unique_name(safe_filename(name))
        self.store.save(Profile(name=name))
        self._reload_profiles(name)

    def _duplicate_profile(self) -> None:
        self._save_profile()
        name = self.store.unique_name(safe_filename(f"{self.profile.name} copy"))
        clone = self.profile.copy()
        clone.name = name
        self.store.save(clone)
        self._reload_profiles(name)

    def _rename_profile(self) -> None:
        name = self._ask_name(tr("Rename profile"), self.profile.name)
        if name is None:
            return
        new = safe_filename(name)
        if new == self.profile.name:
            return
        if self.store.exists(new):
            QMessageBox.warning(self, APP_NAME, tr("A profile with that name already exists."))
            return
        self._save_profile()
        self.store.rename(self.profile.name, new)
        self._reload_profiles(new)

    def _delete_profile(self) -> None:
        question = tr("Delete the profile '{name}'?").format(name=self.profile.name)
        if QMessageBox.question(self, APP_NAME, question) != QMessageBox.StandardButton.Yes:
            return
        self.store.delete(self.profile.name)
        self._reload_profiles()

    def _import_profile(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self, tr("Import profile"), "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            imported = self.store.import_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self, APP_NAME, tr("Could not import the profile: {error}").format(error=exc)
            )
            return
        self._save_profile()
        self._reload_profiles(imported.name)

    def _export_profile(self) -> None:
        self._sync_from_ui()
        suggested = f"{safe_filename(self.profile.name)}.json"
        path, _selected = QFileDialog.getSaveFileName(
            self, tr("Export profile"), suggested, "JSON (*.json)"
        )
        if not path:
            return
        try:
            save_profile_file(self.profile, path)
        except OSError as exc:
            QMessageBox.warning(
                self, APP_NAME, tr("Could not export the profile: {error}").format(error=exc)
            )
            return
        self.statusBar().showMessage(tr("Profile exported."), 4000)

    def _open_profiles_folder(self) -> None:
        sysutils.open_path(self.store.directory)

    # ================================================================== form <-> profile
    def _sync_to_ui(self) -> None:
        p = self.profile
        self._loading = True
        try:
            with blocked(*self._inputs):
                set_data(self.button_combo, p.click.button.value)
                set_data(self.clicks_combo, p.click.clicks)
                self.hold_spin.setValue(p.click.hold_ms)
                set_data(self.target_combo, p.target.mode.value)
                self.x_spin.setValue(p.target.x)
                self.y_spin.setValue(p.target.y)
                self.x2_spin.setValue(p.target.x2)
                self.y2_spin.setValue(p.target.y2)
                self.jitter_px_spin.setValue(p.target.jitter_px)
                self.h_spin.setValue(p.interval.hours)
                self.m_spin.setValue(p.interval.minutes)
                self.s_spin.setValue(p.interval.seconds)
                self.ms_spin.setValue(p.interval.millis)
                self.jitter_spin.setValue(p.interval.jitter_pct)
                set_data(self.stop_combo, p.stop.mode.value)
                self.count_spin.setValue(p.stop.count)
                self.duration_spin.setValue(p.stop.duration_s)
                self.failsafe_check.setChecked(p.safety.failsafe_corner)
                self.moved_check.setChecked(p.safety.stop_on_mouse_move)
                self.awake_check.setChecked(p.safety.prevent_sleep)
                self.delay_spin.setValue(p.safety.start_delay_s)
                self.sched_enable.setChecked(p.schedule.enabled)
                hour, minute, second = parse_time_str(p.schedule.time)
                self.sched_time.setTime(QTime(hour, minute, second))
                for index, check in enumerate(self.day_checks):
                    check.setChecked(index in p.schedule.days)
                self.sched_once.setChecked(p.schedule.once)
            with blocked(self.tabs):
                self.tabs.setCurrentIndex(1 if p.mode == RunMode.MACRO else 0)
        finally:
            self._loading = False
        self._refresh_steps()
        self._refresh_dynamic()

    def _sync_from_ui(self) -> None:
        if self._loading:
            return
        p = self.profile
        p.click.button = enum_or(Button, self.button_combo.currentData(), Button.LEFT)
        p.click.clicks = int_or(self.clicks_combo.currentData(), 1)
        p.click.hold_ms = self.hold_spin.value()
        p.target.mode = enum_or(TargetMode, self.target_combo.currentData(), TargetMode.CURSOR)
        p.target.x = self.x_spin.value()
        p.target.y = self.y_spin.value()
        p.target.x2 = self.x2_spin.value()
        p.target.y2 = self.y2_spin.value()
        p.target.jitter_px = self.jitter_px_spin.value()
        p.interval.hours = self.h_spin.value()
        p.interval.minutes = self.m_spin.value()
        p.interval.seconds = self.s_spin.value()
        p.interval.millis = self.ms_spin.value()
        p.interval.jitter_pct = self.jitter_spin.value()
        p.stop.mode = enum_or(StopMode, self.stop_combo.currentData(), StopMode.INFINITE)
        p.stop.count = self.count_spin.value()
        p.stop.duration_s = self.duration_spin.value()
        p.safety.failsafe_corner = self.failsafe_check.isChecked()
        p.safety.stop_on_mouse_move = self.moved_check.isChecked()
        p.safety.prevent_sleep = self.awake_check.isChecked()
        p.safety.start_delay_s = self.delay_spin.value()
        p.schedule.enabled = self.sched_enable.isChecked()
        when = self.sched_time.time()
        p.schedule.time = f"{when.hour():02d}:{when.minute():02d}:{when.second():02d}"
        p.schedule.days = [i for i, check in enumerate(self.day_checks) if check.isChecked()]
        p.schedule.once = self.sched_once.isChecked()
        tab = self.tabs.currentIndex()
        if tab == 0:
            p.mode = RunMode.CLICKER
        elif tab == 1:
            p.mode = RunMode.MACRO

    def _on_edited(self, *_args) -> None:
        if self._loading:
            return
        self._sync_from_ui()
        self._refresh_dynamic()
        self._save_timer.start()

    def _refresh_dynamic(self) -> None:
        """Show / hide and re-label controls that depend on the current selections."""
        mode = self.target_combo.currentData()
        self.row_a.setVisible(mode in ("fixed", "area"))
        self.row_b.setVisible(mode == "area")
        self.row_j.setVisible(mode == "fixed")
        self.cursor_hint.setVisible(mode == "cursor")
        self.corner_a_label.setText(tr("Top-left corner") if mode == "area" else tr("Point"))
        stop = self.stop_combo.currentData()
        self.count_spin.setVisible(stop == "count")
        self.duration_spin.setVisible(stop == "duration")
        macro = self.profile.mode == RunMode.MACRO
        self.timing_box.setTitle(tr("Delay between runs") if macro else tr("Click interval"))
        self.count_spin.setSuffix(tr(" runs") if macro else tr(" clicks"))
        seconds = self.profile.interval.total_seconds
        if macro:
            text = tr("Waits {time} between runs").format(time=fmt_hms(seconds))
        elif seconds <= 0.001:
            text = tr("Maximum speed: about 1000 clicks per second")
        elif seconds <= 1:
            text = tr("About {rate} clicks per second").format(rate=f"{1 / seconds:.1f}")
        else:
            text = tr("About one click every {secs} s").format(secs=f"{seconds:g}")
        self.rate_label.setText(text)

    # ================================================================== macro editing
    def _refresh_steps(self, select: int | None = None) -> None:
        steps = self.profile.steps
        table = self.steps_table
        table.setRowCount(len(steps))
        for row, step in enumerate(steps):
            action, details = describe_step(step)
            cells = (str(row + 1), action, details, format_delay(step.delay_after_ms))
            for col, text in enumerate(cells):
                table.setItem(row, col, QTableWidgetItem(text))
        if select is not None and 0 <= select < len(steps):
            table.selectRow(select)
        self._update_step_buttons()

    def _update_step_buttons(self) -> None:
        row = self.steps_table.currentRow()
        count = len(self.profile.steps)
        selected = 0 <= row < count
        self.edit_btn.setEnabled(selected)
        self.dup_btn.setEnabled(selected)
        self.del_btn.setEnabled(selected)
        self.up_btn.setEnabled(selected and row > 0)
        self.down_btn.setEnabled(selected and row < count - 1)

    def _after_steps_changed(self, select: int | None = None) -> None:
        self._refresh_steps(select)
        self._save_timer.start()

    def _add_step(self) -> None:
        dialog = StepDialog(self, self.backend)
        if not dialog.exec():
            return
        row = self.steps_table.currentRow()
        steps = self.profile.steps
        index = row + 1 if 0 <= row < len(steps) else len(steps)
        steps.insert(index, dialog.result_step())
        self._after_steps_changed(index)

    def _edit_step(self, row: int) -> None:
        if not 0 <= row < len(self.profile.steps):
            return
        dialog = StepDialog(self, self.backend, self.profile.steps[row])
        if dialog.exec():
            self.profile.steps[row] = dialog.result_step()
            self._after_steps_changed(row)

    def _duplicate_step(self) -> None:
        row = self.steps_table.currentRow()
        if 0 <= row < len(self.profile.steps):
            self.profile.steps.insert(row + 1, copy.deepcopy(self.profile.steps[row]))
            self._after_steps_changed(row + 1)

    def _delete_step(self) -> None:
        row = self.steps_table.currentRow()
        if 0 <= row < len(self.profile.steps):
            del self.profile.steps[row]
            self._after_steps_changed(min(row, len(self.profile.steps) - 1))

    def _move_step(self, delta: int) -> None:
        row = self.steps_table.currentRow()
        target = row + delta
        steps = self.profile.steps
        if 0 <= row < len(steps) and 0 <= target < len(steps):
            steps[row], steps[target] = steps[target], steps[row]
            self._after_steps_changed(target)

    # ================================================================== running
    def _warn(self, text: str) -> None:
        if self.isVisible():
            QMessageBox.warning(self, APP_NAME, text)
            return
        self.statusBar().showMessage(text, 8000)
        if self._tray is not None:
            self._tray.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Warning, 5000)

    def start_run(self, source: str = "button", once: bool = False) -> None:
        """Start the current profile. *source* is "button", "hotkey" or "schedule"."""
        if self.engine.running or self._recorder is not None:
            return
        self._sync_from_ui()
        profile = self.profile.copy()
        if once:
            profile.stop = StopRule(StopMode.COUNT, count=1)
        issues = problems(profile)
        if issues:
            self._warn("\n\n".join(issues))
            return
        self._save_profile()
        self.sparkline.clear()
        self.engine.start(profile, start_delay=None if source == "button" else 0)

    def toggle_run(self, source: str = "hotkey") -> None:
        if self.engine.running:
            self.engine.stop()
        else:
            self.start_run(source)

    def _on_engine_state(self, state: str, reason: str) -> None:
        running = state != RunState.IDLE.value
        self.editor_area.setEnabled(not running)
        self.profile_combo.setEnabled(not running)
        self.profile_menu_btn.setEnabled(not running)
        self.test_btn.setEnabled(not running)
        self._update_start_button(running)
        labels = {"idle": tr("Idle"), "waiting": tr("Waiting"), "running": tr("Running")}
        self.state_pill.setText(labels.get(state, state))
        set_prop(self.state_pill, "state", state)
        if self._tray is not None:
            self._tray.setToolTip(f"{APP_NAME} - {labels.get(state, state)}")
        if not running and reason:
            text = self._reason_text(reason)
            self.statusBar().showMessage(text, 10000)
            if not self.isVisible() and self._tray is not None:
                self._tray.showMessage(APP_NAME, text, QSystemTrayIcon.MessageIcon.Information, 4000)

    @staticmethod
    def _reason_text(reason: str) -> str:
        return {
            "completed": tr("Finished."),
            "user": tr("Stopped."),
            "failsafe": tr("Emergency stop: the cursor reached the top-left corner."),
            "mouse_moved": tr("Stopped because the mouse was moved."),
            "error": tr("Stopped because of an error. See the activity log."),
        }.get(reason, reason)

    def _update_start_button(self, running: bool) -> None:
        key = self.settings.hotkey_toggle
        if running:
            self.start_btn.setText(f"■  {tr('Stop')}  ({key})")
        else:
            self.start_btn.setText(f"▶  {tr('Start')}  ({key})")
        set_role(self.start_btn, "danger" if running else "primary")
        if self._tray_toggle_action is not None:
            self._tray_toggle_action.setText(tr("Stop") if running else tr("Start"))

    def _tick(self) -> None:
        snap = self.engine.snapshot()
        self.count_value.setText(str(snap.count))
        self.cps_value.setText(f"{snap.cps:.1f}")
        self.elapsed_value.setText(fmt_hms(snap.elapsed))
        self.next_value.setText(fmt_hms(snap.next_in) if snap.next_in is not None else "—")
        if snap.state == RunState.RUNNING:
            self.sparkline.push(snap.cps)
        self._schedule_tick()

    # ------------------------------------------------------------------ scheduler
    def _schedule_tick(self) -> None:
        schedule = self.profile.schedule
        if not schedule.enabled:
            self.sched_status.setText(tr("The schedule is off."))
            return
        now = dt.datetime.now()
        due = next_run(schedule, now)
        if due is None:
            self.sched_status.setText(tr("Nothing is scheduled."))
            return
        seconds = (due - now).total_seconds()
        self.sched_status.setText(
            tr("Next run: {when} (in {left})").format(
                when=due.strftime("%Y-%m-%d %H:%M:%S"), left=fmt_hms(seconds)
            )
        )
        if seconds <= LEAD_SECONDS and due != self._fired_due and not self.engine.running:
            self._fired_due = due
            self._start_scheduled(due)

    def _start_scheduled(self, due: dt.datetime) -> None:
        if self._recorder is not None:
            return
        profile = self.profile.copy()
        issues = problems(profile)
        if issues:
            self._warn(tr("The scheduled run was skipped:") + "\n\n" + "\n\n".join(issues))
            return
        self._save_profile()
        log.info("Scheduled run for %s", due.strftime("%Y-%m-%d %H:%M:%S"))
        self.sparkline.clear()
        self.engine.start(profile, start_at=due.timestamp())
        if profile.schedule.once:
            self.profile.schedule.enabled = False
            self._sync_to_ui()
            self._save_profile()

    # ================================================================== hotkeys, picking, recording
    def apply_hotkeys(self) -> None:
        manager = self.ctx.hotkeys
        self._update_hint()
        if manager is None:
            return
        bridge = self.ctx.bridge
        s = self.settings
        errors = manager.register(
            {
                s.hotkey_toggle: lambda: bridge.hotkey.emit("toggle"),
                s.hotkey_capture: lambda: bridge.hotkey.emit("capture"),
                s.hotkey_panic: lambda: bridge.hotkey.emit("panic"),
            }
        )
        for message in errors:
            log.warning(message)

    def _update_hint(self) -> None:
        s = self.settings
        self.hint_label.setText(
            tr("{toggle}: start / stop   ·   {capture}: capture position   ·   {panic}: emergency stop").format(
                toggle=s.hotkey_toggle, capture=s.hotkey_capture, panic=s.hotkey_panic
            )
        )
        self.macro_hint.setText(
            tr("Tip: press {capture} to add a click at the cursor position, or use Record.").format(
                capture=s.hotkey_capture
            )
        )
        self._update_start_button(self.engine.running)

    def _on_hotkey(self, name: str) -> None:
        if name in ("toggle", "panic") and self._recorder is not None:
            self._finish_recording()
        elif name == "toggle":
            self.toggle_run("hotkey")
        elif name == "panic":
            if self.engine.running:
                self.engine.stop()
        elif name == "capture":
            self._capture_cursor()

    def _capture_cursor(self) -> None:
        if self.engine.running or self._recorder is not None:
            return
        x, y = self.backend.position()
        tab = self.tabs.currentIndex()
        if tab == 1:
            self.profile.steps.append(Step(type=StepType.CLICK, x=x, y=y))
            self._after_steps_changed(len(self.profile.steps) - 1)
            message = tr("Added a click at ({x}, {y})")
        elif tab == 0:
            mode = self.target_combo.currentData()
            if mode == "area":
                if self._capture_flip:
                    self.x2_spin.setValue(x)
                    self.y2_spin.setValue(y)
                else:
                    self.x_spin.setValue(x)
                    self.y_spin.setValue(y)
                self._capture_flip = not self._capture_flip
            else:
                if mode != "fixed":
                    set_data(self.target_combo, "fixed")
                self.x_spin.setValue(x)
                self.y_spin.setValue(y)
            message = tr("Captured ({x}, {y})")
        else:
            return
        self.statusBar().showMessage(message.format(x=x, y=y), 4000)

    def _pick(self, corner: str) -> None:
        hint = tr("Click the target position. Esc or right-click cancels.")
        session = PickerSession(self, self.backend, hint, tokens()["accent"])
        session.finished.connect(lambda result, c=corner: self._on_picked(c, result))
        session.start()

    def _on_picked(self, corner: str, result) -> None:
        if result is None:
            return
        x, y = result
        if corner == "a":
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
        else:
            self.x2_spin.setValue(x)
            self.y2_spin.setValue(y)

    # --- macro recording ------------------------------------------------------------------
    def _start_recording(self) -> None:
        if self._recorder is not None or self.engine.running:
            return
        key = self.settings.hotkey_panic
        QMessageBox.information(
            self,
            tr("Record macro"),
            tr(
                "Recording starts 2 seconds after you close this message.\n"
                "Do what you want to automate, then press {key} to stop."
            ).format(key=key),
        )
        hotkeys = (self.settings.hotkey_toggle, self.settings.hotkey_capture, key)
        ignored = [parse_combo(h)[-1] for h in hotkeys if parse_combo(h)]
        self._recorder = Recorder(
            ignore_keys=ignored,
            stop_keys=[parse_combo(key)[-1]] if parse_combo(key) else [],
            on_stop_key=self.ctx.bridge.record_stop.emit,
        )
        self.showMinimized()
        QTimer.singleShot(2000, self._begin_recording)

    def _begin_recording(self) -> None:
        recorder = self._recorder
        if recorder is None:
            return
        try:
            recorder.start()
        except Exception as exc:
            log.warning("Could not start recording: %s", exc)
            self._recorder = None
            self.show_window()
            QMessageBox.warning(
                self, APP_NAME, tr("Could not start recording: {error}").format(error=exc)
            )
            return
        log.info("Recording started")

    def _finish_recording(self) -> None:
        recorder, self._recorder = self._recorder, None
        if recorder is None:
            return
        steps = recorder.stop() if recorder.recording else []
        self.show_window()
        if not steps:
            self.statusBar().showMessage(tr("Nothing was recorded."), 5000)
            return
        self.profile.steps.extend(steps)
        self.tabs.setCurrentIndex(1)
        self._after_steps_changed(len(self.profile.steps) - 1)
        log.info("Recorded %d steps", len(steps))
        self.statusBar().showMessage(tr("Recorded {n} steps.").format(n=len(steps)), 6000)

    # ================================================================== settings, tools, help
    def _open_settings(self) -> None:
        dialog = SettingsDialog(self, self.settings)
        if not dialog.exec():
            return
        previous_language = self.settings.language
        dialog.apply_to(self.settings)
        self.ctx.settings_store.save(self.settings)
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self.settings.theme)
        self.sparkline.set_colour(tokens()["accent"])
        self.apply_hotkeys()
        self.apply_window_flags()
        if self.settings.language != previous_language:
            QMessageBox.information(
                self, APP_NAME, tr("The language changes the next time you start Clicksmith.")
            )

    def apply_window_flags(self) -> None:
        wanted = self.settings.always_on_top
        if wanted == self._on_top:
            return
        self._on_top = wanted
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, wanted)
        if visible:
            self.show()  # changing window flags hides the window

    def _restart_as_admin(self) -> None:
        if sysutils.relaunch_as_admin():
            self.quit_app()
        else:
            QMessageBox.information(self, APP_NAME, tr("The administrator request was cancelled."))

    def _open_data_folder(self) -> None:
        sysutils.open_path(logs_dir().parent)

    def _open_log_file(self) -> None:
        path = logs_dir() / "clicksmith.log"
        sysutils.open_path(path if path.exists() else path.parent)

    def _open_project_page(self) -> None:
        webbrowser.open(f"https://github.com/{REPO}")

    def _show_about(self) -> None:
        text = (
            f"<h3>{APP_NAME} {__version__}</h3>"
            f"<p>{tr('Auto clicker, macro recorder, Unicode typing and scheduler in one tool.')}</p>"
            f"<p><a href='https://github.com/{REPO}'>github.com/{REPO}</a><br>"
            f"{tr('Released under the MIT License.')}</p>"
        )
        QMessageBox.about(self, tr("About Clicksmith"), text)

    # --- updates --------------------------------------------------------------------------
    def check_updates(self, silent: bool) -> None:
        self._update_silent = silent
        threading.Thread(target=self._update_worker, name="clicksmith-update", daemon=True).start()

    def _update_worker(self) -> None:
        try:
            result = fetch_latest()
        except Exception as exc:
            result = exc
        self.ctx.bridge.update_result.emit(result)

    def _on_update_result(self, result) -> None:
        if isinstance(result, Exception):
            log.info("Update check failed: %s", result)
            if not self._update_silent:
                QMessageBox.information(
                    self, APP_NAME, tr("Could not check for updates. Are you online?")
                )
            return
        if is_newer(result.tag, __version__):
            question = tr("Version {version} is available. Open the download page?").format(
                version=result.tag
            )
            if QMessageBox.question(self, APP_NAME, question) == QMessageBox.StandardButton.Yes:
                webbrowser.open(result.url)
        elif not self._update_silent:
            QMessageBox.information(
                self,
                APP_NAME,
                tr("You are running the latest version ({version}).").format(version=__version__),
            )

    # ================================================================== window lifecycle
    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def quit_app(self) -> None:
        self._quitting = True
        self.close()

    def shutdown(self) -> None:
        """Persist everything and release global resources."""
        self._save_timer.stop()
        self._tick_timer.stop()
        try:
            self._save_profile()
            self.ctx.settings_store.save(self.settings)
        except OSError:
            log.exception("Could not save on exit")
        recorder, self._recorder = self._recorder, None
        if recorder is not None and recorder.recording:
            recorder.stop()
        self.engine.stop()
        self.engine.wait(2)
        if self.ctx.hotkeys is not None:
            self.ctx.hotkeys.stop()
        if self._tray is not None:
            self._tray.hide()

    def closeEvent(self, event) -> None:
        if not self._quitting and self._tray is not None and self.settings.close_to_tray:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self._tray.showMessage(
                    APP_NAME,
                    tr("Clicksmith keeps running in the tray. Use the tray icon to quit."),
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
            return
        self.shutdown()
        event.accept()
        QApplication.quit()
