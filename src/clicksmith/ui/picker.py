"""Full-screen position picker.

A dim overlay covers every screen; the click that selects a point is swallowed by the overlay so
it never reaches the application underneath (unlike "capture on click" approaches, which press
whatever button you point at). Coordinates come from the input backend, i.e. physical pixels,
exactly the space the engine clicks in - so the result is right at any display scaling.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core.input.base import InputBackend


class _Overlay(QWidget):
    picked = Signal(int, int)
    cancelled = Signal()

    def __init__(self, parent, screen, backend: InputBackend, hint: str, accent: str) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self._backend = backend
        self._hint = hint
        self._accent = QColor(accent)
        self._pos = None
        self._physical: tuple[int, int] | None = None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(8, 10, 14, 130))  # alpha > 0 keeps it clickable
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        if self._pos is not None:
            painter.setPen(QPen(self._accent, 1))
            painter.drawLine(0, self._pos.y(), self.width(), self._pos.y())
            painter.drawLine(self._pos.x(), 0, self._pos.x(), self.height())
            if self._physical is not None:
                text = f"{self._physical[0]}, {self._physical[1]}"
                box = QRect(
                    self._pos.x() + 16,
                    self._pos.y() + 16,
                    painter.fontMetrics().horizontalAdvance(text) + 18,
                    28,
                )
                if box.right() > self.width():
                    box.moveRight(self._pos.x() - 16)
                if box.bottom() > self.height():
                    box.moveBottom(self._pos.y() - 16)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(20, 22, 28, 235))
                painter.drawRoundedRect(box, 6, 6)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        banner_width = painter.fontMetrics().horizontalAdvance(self._hint) + 44
        banner = QRect((self.width() - banner_width) // 2, 28, banner_width, 44)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 22, 28, 235))
        painter.drawRoundedRect(banner, 22, 22)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(banner, Qt.AlignmentFlag.AlignCenter, self._hint)
        painter.end()

    def mouseMoveEvent(self, event) -> None:
        self._pos = event.position().toPoint()
        self._physical = self._backend.position()
        self.update()

    def leaveEvent(self, _event) -> None:
        self._pos = None
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = self._backend.position()
            self.picked.emit(x, y)
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class PickerSession(QObject):
    """Shows the overlays and reports ``(x, y)`` (or ``None`` if cancelled) via ``finished``."""

    finished = Signal(object)

    def __init__(self, owner: QWidget, backend: InputBackend, hint: str, accent: str) -> None:
        super().__init__(owner)
        self._owner = owner.window()
        self._backend = backend
        self._hint = hint
        self._accent = accent
        self._overlays: list[_Overlay] = []
        self._done = False

    def start(self) -> None:
        # Make the owner invisible (not hidden: a hidden modal dialog would end its exec() loop)
        # so the user can point at things that are underneath it. Overlays are children of the
        # owner, which keeps them usable while a modal dialog is open.
        self._owner.setWindowOpacity(0.0)
        for screen in QGuiApplication.screens():
            overlay = _Overlay(self._owner, screen, self._backend, self._hint, self._accent)
            overlay.picked.connect(self._on_picked)
            overlay.cancelled.connect(self._on_cancelled)
            overlay.show()
            self._overlays.append(overlay)
        if not self._overlays:
            self._finish(None)
            return
        under_cursor = QGuiApplication.screenAt(QCursor.pos())
        focus = next((o for o in self._overlays if o.screen() == under_cursor), self._overlays[0])
        focus.raise_()
        focus.activateWindow()
        focus.setFocus()

    def _on_picked(self, x: int, y: int) -> None:
        self._finish((x, y))

    def _on_cancelled(self) -> None:
        self._finish(None)

    def _finish(self, result) -> None:
        if self._done:
            return
        self._done = True
        for overlay in self._overlays:
            overlay.close()
            overlay.deleteLater()
        self._overlays.clear()
        self._owner.setWindowOpacity(1.0)
        self.finished.emit(result)
        self.deleteLater()
