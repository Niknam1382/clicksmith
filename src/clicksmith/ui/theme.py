"""Dark and light themes: a Fusion palette plus a small style sheet for the custom look."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

DARK = {
    "bg": "#0F1115",
    "surface": "#171A21",
    "surface2": "#1F232C",
    "border": "#2B303B",
    "text": "#E7E9EE",
    "muted": "#8D95A8",
    "accent": "#FF8A3D",
    "accent_hover": "#FFA05F",
    "accent_soft": "#3A2A1E",
    "on_accent": "#1A1206",
    "danger": "#EF4444",
    "danger_hover": "#F76B6B",
    "success": "#22C55E",
    "success_soft": "#12301F",
    "warning": "#F5A524",
    "warning_soft": "#3A2C0F",
}

LIGHT = {
    "bg": "#F4F5F8",
    "surface": "#FFFFFF",
    "surface2": "#EEF0F5",
    "border": "#D9DDE6",
    "text": "#1B1F29",
    "muted": "#667085",
    "accent": "#F2711C",
    "accent_hover": "#FF8A3D",
    "accent_soft": "#FDE7D6",
    "on_accent": "#FFFFFF",
    "danger": "#DC2626",
    "danger_hover": "#EF4444",
    "success": "#16A34A",
    "success_soft": "#DCFCE7",
    "warning": "#D97706",
    "warning_soft": "#FEF3C7",
}

THEMES = {"dark": DARK, "light": LIGHT}
_current: dict[str, str] = dict(DARK)

_QSS = """
QToolTip { background-color: @surface2; color: @text; border: 1px solid @border; padding: 4px 6px; }
QMainWindow, QDialog { background-color: @bg; }
QGroupBox { background-color: @surface; border: 1px solid @border; border-radius: 10px;
            margin-top: 14px; padding: 16px 12px 10px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 14px;
                   padding: 0 6px; color: @muted; }
QPushButton { background-color: @surface2; border: 1px solid @border; border-radius: 8px;
              padding: 7px 14px; }
QPushButton:hover { border-color: @accent; }
QPushButton:pressed { background-color: @border; }
QPushButton:disabled { color: @muted; }
QPushButton[role="primary"] { background-color: @accent; color: @on_accent;
                              border: 1px solid @accent; font-weight: 700; }
QPushButton[role="primary"]:hover { background-color: @accent_hover; border-color: @accent_hover; }
QPushButton[role="primary"]:disabled { background-color: @border; color: @muted;
                                       border-color: @border; }
QPushButton[role="danger"] { background-color: @danger; color: #ffffff;
                             border: 1px solid @danger; font-weight: 700; }
QPushButton[role="danger"]:hover { background-color: @danger_hover; border-color: @danger_hover; }
QToolButton { background-color: @surface2; border: 1px solid @border; border-radius: 8px;
              padding: 6px 10px; }
QToolButton:hover { border-color: @accent; }
QToolButton::menu-indicator { image: none; }
QTabWidget::pane { border: none; top: 4px; }
QTabBar::tab { background: transparent; color: @muted; padding: 9px 20px; margin-right: 4px;
               border: none; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: @text; border-bottom: 2px solid @accent; }
QTabBar::tab:hover:!selected { color: @text; }
QTableWidget { background-color: @surface; border: 1px solid @border; border-radius: 8px;
               gridline-color: @border; selection-background-color: @accent_soft;
               selection-color: @text; }
QHeaderView::section { background-color: @surface2; color: @muted; border: none;
                       border-bottom: 1px solid @border; padding: 6px 8px; font-weight: 600; }
QPlainTextEdit { background-color: @bg; border: 1px solid @border; border-radius: 8px;
                 font-family: Consolas, "Cascadia Mono", "DejaVu Sans Mono", monospace;
                 font-size: 9pt; }
QMenuBar { background-color: @bg; }
QMenuBar::item { padding: 5px 10px; background: transparent; }
QMenuBar::item:selected { background-color: @surface2; border-radius: 4px; }
QMenu { background-color: @surface; border: 1px solid @border; padding: 4px; }
QMenu::item { padding: 6px 24px; border-radius: 4px; }
QMenu::item:selected { background-color: @accent_soft; }
QStatusBar { background-color: @bg; color: @muted; }
QLabel[role="muted"] { color: @muted; }
QLabel[role="title"] { font-size: 19pt; font-weight: 800; }
QLabel[role="stat"] { font-size: 17pt; font-weight: 700; }
QLabel[role="caption"] { color: @muted; font-size: 8pt; }
QLabel[role="pill"] { border-radius: 11px; padding: 4px 14px; font-weight: 700;
                      background-color: @surface2; color: @muted; }
QLabel[role="pill"][state="running"] { background-color: @success_soft; color: @success; }
QLabel[role="pill"][state="waiting"] { background-color: @warning_soft; color: @warning; }
"""


def tokens() -> dict[str, str]:
    """Colour tokens of the theme that is currently applied."""
    return dict(_current)


def build_palette(t: dict[str, str]) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"],
        QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["surface"],
        QPalette.ColorRole.AlternateBase: t["surface2"],
        QPalette.ColorRole.ToolTipBase: t["surface2"],
        QPalette.ColorRole.ToolTipText: t["text"],
        QPalette.ColorRole.Text: t["text"],
        QPalette.ColorRole.Button: t["surface2"],
        QPalette.ColorRole.ButtonText: t["text"],
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Link: t["accent"],
        QPalette.ColorRole.Highlight: t["accent"],
        QPalette.ColorRole.HighlightedText: t["on_accent"],
        QPalette.ColorRole.PlaceholderText: t["muted"],
    }
    for role, colour in roles.items():
        palette.setColor(role, QColor(colour))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["muted"]))
    return palette


def stylesheet(t: dict[str, str]) -> str:
    css = _QSS
    for key in sorted(t, key=len, reverse=True):  # longest first: @accent_hover before @accent
        css = css.replace(f"@{key}", t[key])
    return css


def apply_theme(app: QApplication, name: str) -> None:
    tokens_for = THEMES.get(name, DARK)
    _current.clear()
    _current.update(tokens_for)
    app.setStyle("Fusion")
    app.setPalette(build_palette(tokens_for))
    app.setStyleSheet(stylesheet(tokens_for))
