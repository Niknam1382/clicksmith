"""Small reusable widgets and helpers."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from contextlib import contextmanager
from enum import Enum
from typing import Any, TypeVar

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from ..core.i18n import tr
from ..core.models import Step, StepType

E = TypeVar("E", bound=Enum)


@contextmanager
def blocked(*widgets: QWidget):
    """Temporarily silence the signals of *widgets*."""
    previous = [w.blockSignals(True) for w in widgets]
    try:
        yield
    finally:
        for widget, old in zip(widgets, previous, strict=True):
            widget.blockSignals(old)


def repolish(widget: QWidget) -> None:
    """Re-evaluate style-sheet selectors after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value: str) -> None:
    widget.setProperty(name, value)
    repolish(widget)


def set_role(widget: QWidget, role: str) -> None:
    set_prop(widget, "role", role)


def enum_or(enum_cls: type[E], value: Any, default: E) -> E:
    try:
        return enum_cls(value)
    except ValueError:
        return default


def int_or(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def set_data(combo: QComboBox, value: Any) -> None:
    combo.setCurrentIndex(max(0, combo.findData(value)))


def make_card(title: str) -> tuple[QGroupBox, QGridLayout]:
    box = QGroupBox(title)
    grid = QGridLayout(box)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(8)
    return box, grid


def make_spin(low: int, high: int, suffix: str = "", width: int = 0) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(low, high)
    if suffix:
        spin.setSuffix(suffix)
    if width:
        spin.setMinimumWidth(width)
    spin.setAccelerated(True)
    return spin


def make_combo(items: Iterable[tuple[str, Any]]) -> QComboBox:
    combo = QComboBox()
    for label, data in items:
        combo.addItem(label, data)
    return combo


def make_label(text: str, role: str = "muted", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


def make_row(*widgets: QWidget, stretch: bool = True) -> QWidget:
    """Lay *widgets* out horizontally inside a plain container widget."""
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for widget in widgets:
        layout.addWidget(widget)
    if stretch:
        layout.addStretch(1)
    return holder


def format_delay(ms: int) -> str:
    if ms >= 1000 and ms % 100 == 0:
        return f"{ms / 1000:g} s"
    return f"{ms} ms"


_BUTTON_NAMES = {"left": "Left", "right": "Right", "middle": "Middle"}


def describe_step(step: Step) -> tuple[str, str]:
    """(action, details) texts for the macro table."""
    kind = step.type
    where = tr("cursor") if step.use_cursor else f"({step.x}, {step.y})"
    button = tr(_BUTTON_NAMES.get(step.button.value, "Left"))
    if kind == StepType.CLICK:
        times = f" ×{step.clicks}" if step.clicks > 1 else ""
        hold = f", {step.hold_ms} ms" if step.hold_ms else ""
        return tr("Click"), f"{button}{times} · {where}{hold}"
    if kind == StepType.MOVE:
        return tr("Move mouse"), f"{where}" + (f" · {step.duration_ms} ms" if step.duration_ms else "")
    if kind == StepType.DRAG:
        return tr("Drag"), f"{button} · ({step.x}, {step.y}) → ({step.x2}, {step.y2})"
    if kind == StepType.SCROLL:
        return tr("Scroll"), f"↕ {step.dy:+d}  ↔ {step.dx:+d} · {where}"
    if kind == StepType.TEXT:
        preview = step.text.replace("\n", "↵")
        return tr("Type text"), preview if len(preview) <= 60 else preview[:57] + "..."
    if kind == StepType.KEY:
        return tr("Press keys"), step.keys
    return tr("Wait"), ""


class Sparkline(QWidget):
    """A tiny live line chart (clicks per second over the last few seconds)."""

    def __init__(self, colour: str = "#FF8A3D", points: int = 75) -> None:
        super().__init__()
        self._data: deque[float] = deque(maxlen=points)
        self._colour = QColor(colour)
        self.setMinimumHeight(40)
        self.setMinimumWidth(160)

    def set_colour(self, colour: str) -> None:
        self._colour = QColor(colour)
        self.update()

    def push(self, value: float) -> None:
        self._data.append(value)
        self.update()

    def clear(self) -> None:
        self._data.clear()
        self.update()

    def paintEvent(self, _event) -> None:
        if len(self._data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        top = max(max(self._data), 1.0)
        step = width / (self._data.maxlen - 1)
        offset = (self._data.maxlen - len(self._data)) * step
        points = [
            QPointF(offset + i * step, height - 3 - (v / top) * (height - 6))
            for i, v in enumerate(self._data)
        ]
        line = QPainterPath(points[0])
        for point in points[1:]:
            line.lineTo(point)
        area = QPainterPath(line)
        area.lineTo(points[-1].x(), height)
        area.lineTo(points[0].x(), height)
        area.closeSubpath()
        fill = QLinearGradient(0, 0, 0, height)
        top_colour = QColor(self._colour)
        top_colour.setAlpha(90)
        bottom_colour = QColor(self._colour)
        bottom_colour.setAlpha(0)
        fill.setColorAt(0, top_colour)
        fill.setColorAt(1, bottom_colour)
        painter.fillPath(area, QBrush(fill))
        painter.setPen(QPen(self._colour, 1.6))
        painter.drawPath(line)
        painter.end()


__all__ = [
    "Qt",
    "Sparkline",
    "blocked",
    "describe_step",
    "enum_or",
    "format_delay",
    "int_or",
    "make_card",
    "make_combo",
    "make_label",
    "make_row",
    "make_spin",
    "repolish",
    "set_data",
    "set_prop",
    "set_role",
]
