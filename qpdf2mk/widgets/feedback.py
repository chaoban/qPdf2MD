"""Feedback surfaces: toasts, the drag-and-drop overlay and the onboarding drop zone."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import icons, theme
from .controls import _animation, blend

_KIND = {
    "success": ("check-circle", "success"),
    "error": ("alert", "danger"),
    "warning": ("alert", "warning"),
    "info": ("info", "accent"),
}


# --------------------------------------------------------------------------- toasts

class _ToastCard(QFrame):
    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(p.color("border_strong"), 1))
        painter.setBrush(p.color("surface_alt" if p.is_dark else "surface"))
        painter.drawRoundedRect(r, 12, 12)


class Toast(QWidget):
    closed = Signal(object)

    def __init__(self, host: QWidget, kind: str, text: str, action_text: Optional[str] = None,
                 on_action: Optional[Callable[[], None]] = None, duration: int = 4200):
        super().__init__(host)
        p = theme.current()
        icon_name, role = _KIND.get(kind, _KIND["info"])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 10, 18, 22)  # room for the drop shadow
        card = _ToastCard(self)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(p.color("shadow", 0.55 if p.is_dark else 0.16))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 8, 10)
        row.setSpacing(10)
        ico = QLabel()
        ico.setPixmap(icons.pixmap(icon_name, getattr(p, role), 20, self.devicePixelRatioF()))
        row.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(440)
        label.setMinimumWidth(min(label.fontMetrics().horizontalAdvance(text) + 6, 440))
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        row.addWidget(label, 1)
        if action_text and on_action:
            btn = QPushButton(action_text, objectName="Link")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: (on_action(), self.dismiss()))
            row.addWidget(btn)
        close = QToolButton()
        close.setIcon(icons.themed("x", "text_faint"))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.dismiss)
        row.addWidget(close)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._duration = duration
        self._closing = False

    def popup(self):
        self.show()
        self.raise_()
        self._fade.stop()
        self._fade.setDuration(220)
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(1.0)
        self._fade.start()
        if self._duration > 0:
            self._timer.start(self._duration)

    def dismiss(self):
        if self._closing:
            return
        self._closing = True
        self._timer.stop()
        self._fade.stop()
        self._fade.setDuration(260)
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self._finish)
        self._fade.start()

    def _finish(self):
        self.hide()
        self.closed.emit(self)
        self.deleteLater()

    def enterEvent(self, e):
        self._timer.stop()

    def leaveEvent(self, e):
        if not self._closing and self._duration > 0:
            self._timer.start(1800)


class ToastManager(QObject):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._toasts: list[Toast] = []
        host.installEventFilter(self)

    def show(self, kind: str, text: str, action_text: Optional[str] = None,
             on_action: Optional[Callable[[], None]] = None, duration: int = 4200) -> Toast:
        toast = Toast(self._host, kind, text, action_text, on_action, duration)
        toast.closed.connect(self._remove)
        self._toasts.append(toast)
        while len(self._toasts) > 3:
            self._toasts.pop(0).dismiss()
        toast.adjustSize()
        self._relayout()
        toast.popup()
        return toast

    def _remove(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._relayout()

    def _relayout(self):
        y = self._host.height() - 6
        for t in reversed(self._toasts):
            t.adjustSize()
            y -= t.height()
            t.move((self._host.width() - t.width()) // 2, y)
            y += 10

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() == QEvent.Type.Resize:
            self._relayout()
        return False


# --------------------------------------------------------------------------- drag overlay

class DragOverlay(QWidget):
    """Full-window highlight shown while PDFs are dragged over the workspace."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._title = ""
        self._t = 0.0
        self._anim = _animation(self, self._set_t, 160)
        self._anim.finished.connect(self._after)
        self.hide()

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def _after(self):
        if self._t <= 0.01:
            self.hide()

    def present(self, count: int, folders: bool):
        if count:
            self._title = f"放開以加入 {count} 個 PDF 檔案"
        else:
            self._title = "放開以加入資料夾中的 PDF" if folders else "放開以加入檔案"
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def dismiss(self):
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._t)
        painter.fillRect(self.rect(), p.color("window", 0.78))
        r = QRectF(self.rect()).adjusted(18, 18, -18, -18)
        painter.setBrush(p.color("accent", 0.10 if p.is_dark else 0.06))
        pen = QPen(p.color("accent"), 2, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.drawRoundedRect(r, 22, 22)

        c = r.center()
        circle = QRectF(c.x() - 44, c.y() - 78, 88, 88)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color("accent", 0.18))
        painter.drawEllipse(circle)
        icons.paint(painter, "upload", circle.adjusted(24, 24, -24, -24), p.accent_hover if p.is_dark else p.accent, 2.0)
        painter.setPen(p.color("text"))
        painter.setFont(theme.ui_font(15, QFont.Weight.Bold))
        painter.drawText(QRectF(r.left(), c.y() + 24, r.width(), 30), Qt.AlignmentFlag.AlignCenter, self._title)
        painter.setPen(p.color("text_muted"))
        painter.setFont(theme.ui_font(10))
        painter.drawText(QRectF(r.left(), c.y() + 56, r.width(), 24), Qt.AlignmentFlag.AlignCenter, "也可以直接拖曳整個資料夾")


# --------------------------------------------------------------------------- drop zone

class DropZone(QWidget):
    """The large dashed target on the welcome screen."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 290)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = 0.0
        self._drag = False
        self._anim = _animation(self, self._set_hover, 180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 36)
        layout.setSpacing(0)
        layout.addStretch(1)
        self._badge = QLabel()
        self._badge.setFixedSize(84, 84)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(18)
        self._title = QLabel("拖曳 PDF 檔案到這裡", objectName="StateTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)
        layout.addSpacing(6)
        sub = QLabel("或點擊此處選擇檔案　·　可一次加入多個檔案或整個資料夾", objectName="StateText")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        layout.addSpacing(22)
        self.button = QPushButton("  選擇 PDF 檔案", objectName="Primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.binder.bind(self.button, "folder-open", "on_accent")
        self.button.clicked.connect(self.clicked)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        for w in (self._badge, self._title, sub):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.refresh_theme()

    def refresh_theme(self, *_):
        p = theme.current()
        self._badge.setPixmap(icons.pixmap("upload", p.accent_hover if p.is_dark else p.accent, 36, self.devicePixelRatioF(), 1.8))
        self.update()

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    def _animate_to(self, v: float):
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(v)
        self._anim.start()

    def set_drag_active(self, active: bool):
        self._drag = active
        self._animate_to(1.0 if active else 0.0)

    def enterEvent(self, e):
        self._animate_to(0.6)

    def leaveEvent(self, e):
        if not self._drag:
            self._animate_to(0.0)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        t = self._hover
        painter.setBrush(blend(p.color("surface"), blend(p.color("surface"), p.color("accent"), 0.10 if p.is_dark else 0.06), t))
        pen = QPen(blend(p.color("border_strong"), p.color("accent"), t), 1.6, Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.drawRoundedRect(r, 22, 22)
        # soft halo behind the upload badge
        b = self._badge.geometry()
        halo = QRectF(b).adjusted(-6 * t, -6 * t, 6 * t, 6 * t)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color("accent", 0.13 + 0.07 * t))
        painter.drawEllipse(halo)
