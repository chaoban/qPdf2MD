"""Custom-painted controls: toggle switch, segmented control, stepper, progress visuals."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QConicalGradient, QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .. import icons, theme


def blend(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
        a.alphaF() + (b.alphaF() - a.alphaF()) * t,
    )


def _animation(owner, slot, duration=200, curve=QEasingCurve.Type.OutCubic) -> QVariantAnimation:
    anim = QVariantAnimation(owner)
    anim.setDuration(duration)
    anim.setEasingCurve(curve)
    anim.valueChanged.connect(slot)
    return anim


# --------------------------------------------------------------------------- toggle switch

class ToggleSwitch(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self._hover = False
        self._anim = _animation(self, self._set_pos, 180)
        self.toggled.connect(self._animate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 22)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, checked: bool):
        self._anim.stop()
        if not self.isVisible():
            self._set_pos(1.0 if checked else 0.0)
            return
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.4)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off = p.color("border_strong")
        on = p.color("accent_hover" if self._hover else "accent")
        if self._hover and self._pos < 0.5:
            off = p.color("text_faint")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(blend(off, on, self._pos))
        painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + self._pos * (r.width() - 6 - d)
        knob = QRectF(x, r.top() + 3, d, d)
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawEllipse(knob.translated(0, 0.8))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(knob)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(p.color("accent", 0.55), 1.5))
            painter.drawRoundedRect(r.adjusted(-1, -1, 1, 1), r.height() / 2 + 1, r.height() / 2 + 1)


class ToggleRow(QWidget):
    """A labelled switch row; clicking anywhere on the row toggles it."""

    toggled = Signal(bool)

    def __init__(self, title: str, hint: str = "", checked: bool = False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(14)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = QLabel(title, objectName="FieldLabel")
        col.addWidget(self.title)
        self.hint = QLabel(hint, objectName="Hint")
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        col.addWidget(self.hint)
        layout.addLayout(col, 1)
        self.switch = ToggleSwitch(checked)
        layout.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignTop)
        self.switch.toggled.connect(self.toggled)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self.switch.isChecked()

    def setChecked(self, value: bool) -> None:
        self.switch.setChecked(value)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.rect().contains(e.position().toPoint()):
            self.switch.toggle()


# --------------------------------------------------------------------------- segmented control

class SegmentedControl(QWidget):
    """iOS-style segmented picker with a sliding, raised indicator."""

    changed = Signal(str)

    def __init__(self, items, parent=None, *, height: int = 34):
        super().__init__(parent)
        self._items = [(it[0], it[1], it[2] if len(it) > 2 else None) for it in items]
        self._index = 0
        self._hover = -1
        self._pos = 0.0
        self._compact = False  # icons only (labels move to tooltips) when the parent runs out of room
        self._anim = _animation(self, self._set_pos, 230)
        self.setFixedHeight(height)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        f = theme.ui_font()
        f.setWeight(QFont.Weight.DemiBold)
        self.setFont(f)

    def sizeHint(self) -> QSize:
        return QSize(self.full_width(self._compact), self.height())

    def full_width(self, compact: bool = False) -> int:
        """Width the control needs to show every segment, with or without its label."""
        if compact and all(ico for _, _, ico in self._items):
            return 44 * len(self._items) + 6
        fm = QFontMetrics(self.font())
        return sum(fm.horizontalAdvance(label) + (22 if ico else 0) + 26 for _, label, ico in self._items) + 6

    def isCompact(self) -> bool:
        return self._compact

    def setCompact(self, compact: bool) -> None:
        compact = compact and all(ico for _, _, ico in self._items)
        if compact != self._compact:
            self._compact = compact
            self.setToolTip("")
            self.updateGeometry()
            self.update()

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def value(self) -> str:
        return self._items[self._index][0]

    def setValue(self, key: str, animate: bool = True) -> None:
        idx = next((i for i, it in enumerate(self._items) if it[0] == key), None)
        if idx is None or idx == self._index:
            return
        self._index = idx
        self._anim.stop()
        if animate and self.isVisible():
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(float(idx))
            self._anim.start()
        else:
            self._set_pos(float(idx))
        self.changed.emit(key)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _seg_rect(self, i: float) -> QRectF:
        inner = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        w = inner.width() / len(self._items)
        return QRectF(inner.left() + w * i, inner.top(), w, inner.height())

    def _index_at(self, x: float) -> int:
        inner = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        i = int((x - inner.left()) / (inner.width() / len(self._items)))
        return max(0, min(len(self._items) - 1, i))

    def mouseMoveEvent(self, e):
        idx = self._index_at(e.position().x())
        if idx != self._hover:
            self._hover = idx
            self.setToolTip(self._items[idx][1] if self._compact else "")
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._items[self._index_at(e.position().x())][0])

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.setValue(self._items[max(0, self._index - 1)][0])
        elif e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.setValue(self._items[min(len(self._items) - 1, self._index + 1)][0])
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(p.color("border"), 1))
        painter.setBrush(p.color("window" if p.is_dark else "surface_alt"))
        painter.drawRoundedRect(outer, 10, 10)

        ind = self._seg_rect(self._pos)
        painter.setPen(Qt.PenStyle.NoPen)
        if not p.is_dark:
            painter.setBrush(p.color("shadow", 0.07))
            painter.drawRoundedRect(ind.translated(0, 1), 8, 8)
        painter.setBrush(p.color("surface_hover" if p.is_dark else "surface"))
        painter.setPen(QPen(p.color("border_strong" if p.is_dark else "border"), 1))
        painter.drawRoundedRect(ind.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        fm = QFontMetrics(self.font())
        for i, (_, label, ico) in enumerate(self._items):
            r = self._seg_rect(i)
            active = i == self._index
            role = "text" if active or i == self._hover else "text_muted"
            color = p.color(role)
            tw = 0 if self._compact else fm.horizontalAdvance(label)
            total = tw + (21 if ico else 0) - (6 if self._compact else 0)
            x = r.center().x() - total / 2
            if ico:
                icon_color = p.accent_hover if (active and p.is_dark) else (p.accent if active else getattr(p, role))
                icons.paint(painter, ico, QRectF(x, r.center().y() - 7.5, 15, 15), icon_color, 2.0)
                x += 21
            if self._compact:
                continue
            painter.setPen(color)
            painter.drawText(QRectF(x, r.top(), tw + 2, r.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(p.color("accent", 0.6), 1.5))
            painter.drawRoundedRect(outer, 10, 10)


# --------------------------------------------------------------------------- stepper

class Stepper(QWidget):
    STEPS = ("加入檔案", "調整設定", "轉換", "檢視成果")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step = 0
        self.setFont(theme.ui_font(9.5, QFont.Weight.DemiBold))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)

    def set_step(self, step: int) -> None:
        if step != self._step:
            self._step = step
            self.update()

    def _metrics(self):
        fm = QFontMetrics(self.font())
        widths = [24 + 8 + fm.horizontalAdvance(s) for s in self.STEPS]
        gap = 36
        return widths, gap, sum(widths) + gap * (len(widths) - 1)

    def sizeHint(self) -> QSize:
        return QSize(self._metrics()[2] + 8, 40)

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        widths, gap, total = self._metrics()
        x = (self.width() - total) / 2
        cy = self.height() / 2
        num_font = theme.ui_font(8.5, QFont.Weight.Bold)
        for i, label in enumerate(self.STEPS):
            circle = QRectF(x, cy - 12, 24, 24)
            if i < self._step:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(p.color("accent", 0.18 if p.is_dark else 0.12))
                painter.drawEllipse(circle)
                icons.paint(painter, "check", circle.adjusted(6, 6, -6, -6), p.accent_hover if p.is_dark else p.accent, 2.6)
                text_color = p.color("text_muted")
            elif i == self._step:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(p.color("accent", 0.22))
                painter.drawEllipse(circle.adjusted(-3, -3, 3, 3))
                painter.setBrush(p.color("accent"))
                painter.drawEllipse(circle)
                painter.setFont(num_font)
                painter.setPen(p.color("on_accent"))
                painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(i + 1))
                text_color = p.color("text")
            else:
                painter.setPen(QPen(p.color("border_strong"), 1.4))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(circle.adjusted(0.7, 0.7, -0.7, -0.7))
                painter.setFont(num_font)
                painter.setPen(p.color("text_faint"))
                painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(i + 1))
                text_color = p.color("text_faint")
            painter.setFont(self.font())
            painter.setPen(text_color)
            painter.drawText(QRectF(x + 32, 0, widths[i] - 32, self.height()), Qt.AlignmentFlag.AlignVCenter, label)
            x += widths[i]
            if i < len(self.STEPS) - 1:
                pen = QPen(p.color("accent", 0.55) if i < self._step else p.color("border_strong"), 1.6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(QPointF(x + 9, cy), QPointF(x + gap - 9, cy))
                x += gap


# --------------------------------------------------------------------------- progress visuals

class ThinProgress(QWidget):
    """A 3px gradient bar used for overall batch progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._value = 0.0
        self._shown = 0.0
        self._alpha = 0.0
        self._value_anim = _animation(self, self._set_shown, 350)
        self._alpha_anim = _animation(self, self._set_alpha, 300)

    def _set_shown(self, v):
        self._shown = float(v)
        self.update()

    def _set_alpha(self, v):
        self._alpha = float(v)
        self.update()

    def set_value(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._value) < 1e-4:
            return
        self._value = value
        self._value_anim.stop()
        self._value_anim.setStartValue(self._shown)
        self._value_anim.setEndValue(value)
        self._value_anim.start()

    def set_active(self, active: bool) -> None:
        self._alpha_anim.stop()
        self._alpha_anim.setStartValue(self._alpha)
        self._alpha_anim.setEndValue(1.0 if active else 0.0)
        self._alpha_anim.setDuration(250 if active else 900)
        self._alpha_anim.start()
        if active:
            self._value = self._shown = 0.0

    def paintEvent(self, _):
        if self._alpha <= 0.01:
            return
        p = theme.current()
        painter = QPainter(self)
        painter.setOpacity(self._alpha)
        painter.fillRect(self.rect(), p.color("accent", 0.12))
        w = self.width() * self._shown
        if w > 0:
            grad = QLinearGradient(0, 0, max(w, 1), 0)
            grad.setColorAt(0, p.color("accent"))
            grad.setColorAt(1, p.color("accent_2"))
            painter.fillRect(QRectF(0, 0, w, self.height()), grad)


class ProgressRing(QWidget):
    """Circular progress with a percentage label; spins while the value is unknown."""

    def __init__(self, size: int = 92, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value = 0.0
        self._shown = 0.0
        self._spin = 0.0
        self._anim = _animation(self, self._set_shown, 300)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _set_shown(self, v):
        self._shown = float(v)
        self.update()

    def _tick(self):
        self._spin = (self._spin + 4.5) % 360
        self.update()

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(1.0, value))
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(self._value)
        self._anim.start()

    def reset(self) -> None:
        self._anim.stop()
        self._value = self._shown = 0.0
        self.update()

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        stroke = 6.0
        r = QRectF(self.rect()).adjusted(stroke, stroke, -stroke, -stroke)
        painter.setPen(QPen(p.color("border"), stroke))
        painter.drawEllipse(r)

        grad = QConicalGradient(r.center(), 90 - self._spin * 0.25)
        grad.setColorAt(0.0, p.color("accent_2"))
        grad.setColorAt(1.0, p.color("accent"))
        pen = QPen(grad, stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        if self._shown < 0.02:
            painter.drawArc(r, int((90 - self._spin) * 16), int(-80 * 16))
        else:
            painter.drawArc(r, 90 * 16, int(-360 * 16 * self._shown))

        painter.setPen(p.color("text"))
        painter.setFont(theme.ui_font(15, QFont.Weight.Bold))
        label = f"{round(self._shown * 100)}%" if self._shown >= 0.02 else "…"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, label)


class StatusPill(QWidget):
    """Tiny dot + label used for the engine state in the header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._role = "warning"
        self._text = "引擎載入中"
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.setFont(theme.ui_font(9, QFont.Weight.DemiBold))
        self.setFixedHeight(28)
        self._timer.start()

    def set_state(self, role: str, text: str, pulsing: bool = False, tooltip: str = "") -> None:
        self._role, self._text = role, text
        self.setToolTip(tooltip)
        if pulsing:
            self._timer.start()
        else:
            self._timer.stop()
            self._pulse = 0.0
        self.updateGeometry()
        self.update()

    def _tick(self):
        self._pulse = (self._pulse + 0.05) % 1.0
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(QFontMetrics(self.font()).horizontalAdvance(self._text) + 34, 28)

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(p.color("border"), 1))
        painter.setBrush(p.color("surface"))
        painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        dot = QPointF(14, r.center().y())
        if self._timer.isActive():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(p.color(self._role, 0.35 * (1 - self._pulse)))
            rad = 3.5 + 5 * self._pulse
            painter.drawEllipse(dot, rad, rad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color(self._role))
        painter.drawEllipse(dot, 3.5, 3.5)
        painter.setPen(p.color("text_muted"))
        painter.drawText(r.adjusted(25, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, self._text)


class Spinner(QWidget):
    def __init__(self, size: int = 16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        pen = QPen(p.color("accent"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(r, -self._angle * 16, 270 * 16)
