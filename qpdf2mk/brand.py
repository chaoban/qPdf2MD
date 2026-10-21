"""Publisher branding: the SAISAI wordmark, drawn from vectors and recoloured for the theme."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from . import theme

INK = "#242C32"     # "SAIS"
ORANGE = "#EE7C24"  # "AI"

# Traced from the SAISAI logo artwork (viewBox 278 × 40).
_VIEWBOX = (278, 40)
_SAIS = (
    "M133.56 37.94L175.81 37.81L180.56 35.69L185.19 31.44L187.81 26.19L187.81 22.06L185.81 19.31L181.31 17.31"
    "L159.31 17.19L157.06 16.56L155.31 13.81L142.94 14.06L142.06 15.81L142.06 19.94L146.06 23.81L150.19 24.44"
    "L172.31 24.56L173.81 25.56L174.06 27.31L172.81 28.81L169.81 29.56L142.94 29.81L138.19 33.19Z"
    "M1.44 37.81L43.81 37.81L48.44 35.94L51.81 33.31L55.69 27.44L56.31 22.94L54.06 19.19L50.31 17.31L26.31 17.06"
    "L23.56 13.69L11.69 13.69L10.44 15.19L10.31 19.81L12.94 22.81L15.19 23.94L40.31 24.69L42.06 25.56L42.19 27.44"
    "L39.44 29.44L9.94 30.06Z"
    "M103.06 2.31L102.31 1.69L89.69 1.81L84.94 3.19L52.31 37.81L65.69 37.94L90.69 12.06L91.94 13.19L95.69 26.56"
    "L93.81 25.56L81.94 25.81L75.81 31.69L92.31 32.06L96.31 28.44L99.56 38.06L112.56 37.81L112.81 36.81Z"
    "M144.06 10.44L186.31 10.81L190.19 8.44L197.06 2.06L153.19 1.94L148.56 4.19Z"
    "M140.69 1.81L127.31 1.81L115.06 37.19L115.44 38.06L128.94 37.81L140.81 4.19Z"
    "M12.56 10.56L54.19 10.81L59.44 7.81L65.69 1.94L21.06 2.06L17.31 4.06L14.81 6.56Z"
)
_AI = (
    "M276.69 1.81L262.94 2.19L251.44 35.19L251.19 38.06L264.81 37.81L276.94 3.06Z"
    "M236.94 2.19L224.19 1.56L220.06 2.06L218.31 3.06L186.06 37.81L199.69 37.81L224.31 11.94L225.81 13.31"
    "L228.81 23.06L228.81 25.19L215.56 25.94L209.56 31.69L226.56 32.06L230.44 29.81L233.19 37.81L246.44 37.81Z"
)


def logo_svg(ink: str = INK, accent: str = ORANGE) -> bytes:
    w, h = _VIEWBOX
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
        f'<path fill="{ink}" fill-rule="evenodd" d="{_SAIS}"/>'
        f'<path fill="{accent}" fill-rule="evenodd" d="{_AI}"/></svg>'
    ).encode()


class Logo(QWidget):
    """The SAISAI wordmark at a fixed height. Dark themes get light "SAIS" letters so it stays legible."""

    def __init__(self, height: int, parent=None):
        super().__init__(parent)
        self.setFixedSize(round(height * _VIEWBOX[0] / _VIEWBOX[1]), height)

    def paintEvent(self, event):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        QSvgRenderer(QByteArray(logo_svg(p.text if p.is_dark else INK))).render(painter, QRectF(self.rect()))
        painter.end()


class LogoBanner(QWidget):
    """The wordmark centred on a soft brand-orange card, for the top of the About box."""

    def __init__(self, height: int = 104, logo_height: int = 44, parent=None):
        super().__init__(parent)
        self._logo_height = logo_height
        self.setFixedHeight(height)

    def paintEvent(self, event):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(ORANGE)
        fill.setAlphaF(0.16 if p.is_dark else 0.11)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(self.rect()), 16, 16)
        h = self._logo_height
        w = h * _VIEWBOX[0] / _VIEWBOX[1]
        target = QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)
        QSvgRenderer(QByteArray(logo_svg(p.text if p.is_dark else INK))).render(painter, target)
        painter.end()
