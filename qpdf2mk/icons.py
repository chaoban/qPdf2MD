"""Crisp, theme-aware line icons rendered from inline SVG (24×24 grid, 2px round strokes)."""

from __future__ import annotations

from functools import lru_cache

import shiboken6
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

_PATHS: dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "upload": '<path d="M12 15V4"/><path d="m7 9 5-5 5 5"/><path d="M20 15v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    "file-text": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>',
    "folder": '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.5h7.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/>',
    "folder-open": '<path d="M3 17V6.5A1.5 1.5 0 0 1 4.5 5H9l2 2.5h6.5A1.5 1.5 0 0 1 19 9v1.5"/><path d="M3 17l2.6-5.6A2 2 0 0 1 7.4 10.3H20a1 1 0 0 1 .9 1.4l-2.6 6A2 2 0 0 1 16.5 19H5a2 2 0 0 1-2-2z"/>',
    "play": '<path d="M7.5 5.2v13.6a1 1 0 0 0 1.5.86l11-6.8a1 1 0 0 0 0-1.72l-11-6.8a1 1 0 0 0-1.5.86z" fill="currentColor"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2.5" fill="currentColor"/>',
    "copy": '<rect x="9" y="9" width="12" height="12" rx="2.5"/><path d="M5 15h-.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/>',
    "external": '<path d="M14 4h6v6"/><path d="M10 14 20 4"/><path d="M18 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "code": '<path d="m16 17 5-5-5-5"/><path d="m8 7-5 5 5 5"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="9" cy="9" r="1.8"/><path d="m21 15-4.3-4.3a1.5 1.5 0 0 0-2.1 0L5 20.5"/>',
    "trash": '<path d="M4 7h16"/><path d="M9 7V4.5A1.5 1.5 0 0 1 10.5 3h3A1.5 1.5 0 0 1 15 4.5V7"/><path d="M18.5 7l-.8 12.1A2 2 0 0 1 15.7 21H8.3a2 2 0 0 1-2-1.9L5.5 7"/><path d="M10 11v6M14 11v6"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>',
    "sparkles": '<path d="M11 3.5l1.6 4.3a2 2 0 0 0 1.2 1.2l4.2 1.5-4.2 1.5a2 2 0 0 0-1.2 1.2L11 17.5l-1.6-4.3a2 2 0 0 0-1.2-1.2L4 10.5 8.2 9a2 2 0 0 0 1.2-1.2z"/><path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
    "zap": '<path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
    "moon": '<path d="M20.5 13.4A8.5 8.5 0 1 1 10.6 3.5a6.6 6.6 0 0 0 9.9 9.9z"/>',
    "monitor": '<rect x="2.5" y="4" width="19" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "alert": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16.2v.3"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8.3 12.2 2.6 2.6 4.9-5.4"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16.5v-5M12 7.8v.3"/>',
    "download": '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    "markdown": '<rect x="2" y="5" width="20" height="14" rx="2.5"/><path d="M6 15V9l3 3.2L12 9v6"/><path d="M17 9v6m-2.4-2.4L17 15l2.4-2.4"/>',
    "sliders": '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "more": '<circle cx="5" cy="12" r="1.3" fill="currentColor"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/><circle cx="19" cy="12" r="1.3" fill="currentColor"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    "pages": '<path d="M8 3.5h8.5A2.5 2.5 0 0 1 19 6v11.5"/><rect x="5" y="7" width="11" height="14" rx="2"/>',
    "type": '<path d="M5 7V5h14v2M12 5v14M9 19h6"/>',
    "broom": '<path d="m14.5 3.5-5 9"/><path d="M5.5 12.5h8l1.5 8h-11z"/><path d="M8 16.5v4M11.5 16.5v4"/>',
    "phone": '<path d="M21 16.4v2.9a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 2.7 5.2 2 2 0 0 1 4.7 3h2.9a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.6 10.8a16 16 0 0 0 4.6 4.6l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    "scan":'<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><path d="M8 10h8M8 14h5"/>',
    "keyboard":'<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6.5 10h.01M10 10h.01M14 10h.01M17.5 10h.01M8 14h8"/>',
}

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
    'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

_SIZES = (14, 16, 18, 20, 24, 32, 40, 48, 64)


def svg(name: str, color: str, stroke: float = 1.9) -> bytes:
    body = _PATHS[name].replace("currentColor", color)
    return _SVG.format(c=color, w=stroke, body=body).encode()


def pixmap(name: str, color: str, size: int, dpr: float = 1.0, stroke: float = 1.9) -> QPixmap:
    px = max(1, round(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg(name, color, stroke)))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def paint(painter: QPainter, name: str, rect: QRectF, color: str, stroke: float = 1.9) -> None:
    """Draw an icon straight into a painter (used by custom-painted widgets/delegates)."""
    QSvgRenderer(QByteArray(svg(name, color, stroke))).render(painter, rect)


@lru_cache(maxsize=512)
def icon(name: str, color: str, disabled_color: str | None = None) -> QIcon:
    ico = QIcon()
    for s in _SIZES:
        ico.addPixmap(pixmap(name, color, s), QIcon.Mode.Normal)
        ico.addPixmap(pixmap(name, color, s), QIcon.Mode.Active)
        if disabled_color:
            ico.addPixmap(pixmap(name, disabled_color, s), QIcon.Mode.Disabled)
    return ico


def themed(name: str, role: str = "text_muted") -> QIcon:
    p = theme.current()
    return icon(name, getattr(p, role), p.text_faint)


class IconBinder:
    """Keeps widget icons in sync with the active palette."""

    def __init__(self):
        self._items: list[tuple[object, str, str]] = []

    def bind(self, widget, name: str, role: str = "text_muted"):
        self._items = [(w, n, r) for (w, n, r) in self._items if w is not widget]
        self._items.append((widget, name, role))
        widget.setIcon(themed(name, role))
        return widget

    def refresh(self, *_):
        alive = []
        for w, n, r in self._items:
            if shiboken6.isValid(w):
                w.setIcon(themed(n, r))
                alive.append((w, n, r))
        self._items = alive


binder = IconBinder()


def app_icon_svg() -> bytes:
    """SVG source of the application icon (also rendered into the .ico and the MSIX tile images)."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#8B7BFF"/><stop offset="1" stop-color="#4B3BE6"/></linearGradient>'
        '<linearGradient id="s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#FFFFFF" stop-opacity=".22"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient></defs>'
        '<rect x="3" y="3" width="58" height="58" rx="15" fill="url(#g)"/>'
        '<rect x="3" y="3" width="58" height="30" rx="15" fill="url(#s)"/>'
        '<path d="M14 42V22l8 9 8-9v20" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M44 22v19m-7-7 7 7 7-7" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    ).encode()


def app_icon() -> QIcon:
    """The application icon: a violet gradient tile with a Markdown glyph."""
    ico = QIcon()
    renderer = QSvgRenderer(QByteArray(app_icon_svg()))
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, s, s))
        painter.end()
        ico.addPixmap(pm)
    return ico
