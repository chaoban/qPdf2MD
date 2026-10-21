"""Design tokens, palettes and the application-wide stylesheet."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget

UI_FONTS = ["Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "sans-serif"]
MONO_FONTS = ["Cascadia Mono", "Cascadia Code", "Consolas", "Microsoft JhengHei UI", "monospace"]


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_2: str
    on_accent: str
    success: str
    warning: str
    danger: str
    page: str
    code_bg: str
    shadow: str

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"

    def color(self, role: str, alpha: float = 1.0) -> QColor:
        c = QColor(getattr(self, role))
        c.setAlphaF(alpha)
        return c

    def rgba(self, role: str, alpha: float) -> str:
        c = QColor(getattr(self, role))
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha * 255)})"


DARK = Palette(
    name="dark",
    window="#0D0F13",
    surface="#15181E",
    surface_alt="#1B1F27",
    surface_hover="#222733",
    border="#252A34",
    border_strong="#323946",
    text="#E8EAF0",
    text_muted="#A0A8B8",
    text_faint="#6A7385",
    accent="#7C6CFF",
    accent_hover="#9083FF",
    accent_pressed="#6A5AF0",
    accent_2="#3FB8FF",
    on_accent="#FFFFFF",
    success="#3DD68C",
    warning="#F5B740",
    danger="#FF6B6B",
    page="#FFFFFF",
    code_bg="#1F2430",
    shadow="#000000",
)

LIGHT = Palette(
    name="light",
    window="#F3F4F8",
    surface="#FFFFFF",
    surface_alt="#F6F7FA",
    surface_hover="#EDEFF5",
    border="#E3E6EE",
    border_strong="#D0D5E0",
    text="#161A22",
    text_muted="#5B6476",
    text_faint="#98A0AE",
    accent="#5B4CF5",
    accent_hover="#6C5EFF",
    accent_pressed="#4A3BE0",
    accent_2="#0A9BEA",
    on_accent="#FFFFFF",
    success="#12A66A",
    warning="#C98400",
    danger="#E5484D",
    page="#FFFFFF",
    code_bg="#F2F3F8",
    shadow="#1A2045",
)

_current: Palette = LIGHT


def current() -> Palette:
    return _current


def ui_font(point_size: float | None = None, weight: QFont.Weight | None = None) -> QFont:
    f = QFont()
    f.setFamilies(UI_FONTS)
    if point_size:
        f.setPointSizeF(point_size)
    if weight is not None:
        f.setWeight(weight)
    return f


def mono_font(point_size: float = 10.0) -> QFont:
    f = QFont()
    f.setFamilies(MONO_FONTS)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSizeF(point_size)
    return f


def build_qpalette(p: Palette) -> QPalette:
    pal = QPalette()
    c = QColor
    roles = {
        QPalette.ColorRole.Window: p.window,
        QPalette.ColorRole.WindowText: p.text,
        QPalette.ColorRole.Base: p.surface,
        QPalette.ColorRole.AlternateBase: p.surface_alt,
        QPalette.ColorRole.Text: p.text,
        QPalette.ColorRole.Button: p.surface_alt,
        QPalette.ColorRole.ButtonText: p.text,
        QPalette.ColorRole.BrightText: p.on_accent,
        QPalette.ColorRole.Highlight: p.accent,
        QPalette.ColorRole.HighlightedText: p.on_accent,
        QPalette.ColorRole.ToolTipBase: p.surface_alt,
        QPalette.ColorRole.ToolTipText: p.text,
        QPalette.ColorRole.PlaceholderText: p.text_faint,
        QPalette.ColorRole.Link: p.accent if not p.is_dark else p.accent_hover,
        QPalette.ColorRole.LinkVisited: p.accent,
        QPalette.ColorRole.Light: p.surface_hover,
        QPalette.ColorRole.Midlight: p.border,
        QPalette.ColorRole.Mid: p.border_strong,
        QPalette.ColorRole.Dark: p.border_strong,
        QPalette.ColorRole.Shadow: p.shadow,
    }
    for role, value in roles.items():
        pal.setColor(role, c(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, c(p.text_faint))
    return pal


def build_stylesheet(p: Palette) -> str:
    sel_bg = p.rgba("accent", 0.35 if p.is_dark else 0.22)
    return f"""
QWidget {{ color: {p.text}; }}
QMainWindow, #Root, #Workspace, #EmptyPage {{ background: {p.window}; }}
QToolTip {{
    background: {p.surface_alt}; color: {p.text}; border: 1px solid {p.border_strong};
    border-radius: 6px; padding: 6px 9px;
}}

/* ---------- surfaces ---------- */
#Panel {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 14px; }}
#PanelHeader {{ background: transparent; }}
#Divider {{ background: {p.border}; max-height: 1px; min-height: 1px; border: none; }}
#HeaderBar {{ background: {p.window}; }}

/* ---------- typography ---------- */
#AppTitle {{ font-size: 16px; font-weight: 700; }}
#AppSubtitle {{ color: {p.text_muted}; font-size: 12px; }}
#PanelTitle {{ font-size: 14px; font-weight: 600; }}
#SectionTitle {{ color: {p.text_faint}; font-size: 11px; font-weight: 700; }}
#FieldLabel {{ font-weight: 600; }}
#Hint {{ color: {p.text_muted}; font-size: 12px; }}
#Faint {{ color: {p.text_faint}; font-size: 12px; }}
#ErrorText {{ color: {p.danger}; font-size: 12px; }}
#CountBadge {{
    background: {p.surface_hover}; color: {p.text_muted}; border-radius: 9px;
    padding: 1px 8px; font-size: 11px; font-weight: 700;
}}
#HeroTitle {{ font-size: 26px; font-weight: 700; }}
#HeroSubtitle {{ color: {p.text_muted}; font-size: 14px; }}
#StateTitle {{ font-size: 16px; font-weight: 600; }}
#StateText {{ color: {p.text_muted}; font-size: 13px; }}
#StatChip {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px;
    color: {p.text_muted}; padding: 3px 9px; font-size: 12px;
}}

/* ---------- buttons ---------- */
QPushButton {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 9px;
    padding: 7px 14px; color: {p.text}; font-weight: 600;
}}
QPushButton:hover {{ background: {p.surface_hover}; border-color: {p.border_strong}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {p.text_faint}; background: {p.surface_alt}; border-color: {p.border}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#Primary {{
    background: {p.accent}; border: 1px solid {p.accent}; color: {p.on_accent};
    padding: 11px 18px; border-radius: 11px; font-size: 14px;
}}
QPushButton#Primary:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton#Primary:pressed {{ background: {p.accent_pressed}; }}
QPushButton#Primary:disabled {{ background: {p.border}; border-color: {p.border}; color: {p.text_faint}; }}
QPushButton#Stop {{
    background: {p.rgba("danger", 0.14)}; border: 1px solid {p.rgba("danger", 0.45)}; color: {p.danger};
    padding: 11px 18px; border-radius: 11px; font-size: 14px;
}}
QPushButton#Stop:hover {{ background: {p.rgba("danger", 0.22)}; }}
QPushButton#Link {{
    background: transparent; border: none; color: {p.accent if not p.is_dark else p.accent_hover};
    padding: 4px 6px; font-weight: 600;
}}
QPushButton#Link:hover {{ text-decoration: underline; }}
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 5px; color: {p.text_muted};
}}
QToolButton:hover {{ background: {p.surface_hover}; color: {p.text}; }}
QToolButton:pressed {{ background: {p.border}; }}
QToolButton:disabled {{ color: {p.text_faint}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}
QToolButton#Labeled {{ padding: 5px 10px 5px 8px; font-weight: 600; }}

/* ---------- inputs ---------- */
QLineEdit {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 9px;
    padding: 7px 10px; selection-background-color: {sel_bg}; selection-color: {p.text};
}}
QLineEdit:hover {{ border-color: {p.border_strong}; }}
QLineEdit:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled {{ color: {p.text_faint}; }}
QLineEdit[invalid="true"] {{ border-color: {p.danger}; }}

QSlider::groove:horizontal {{ height: 4px; background: {p.border_strong}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {p.on_accent}; border: 2px solid {p.accent}; width: 12px; height: 12px;
    margin: -6px 0; border-radius: 8px;
}}
QSlider::sub-page:horizontal:disabled {{ background: {p.text_faint}; }}
QSlider::handle:horizontal:disabled {{ border-color: {p.text_faint}; }}

/* ---------- text views ---------- */
QTextBrowser, QPlainTextEdit {{
    background: {p.surface}; border: none; selection-background-color: {sel_bg}; selection-color: {p.text};
}}
#SourceView {{ background: {p.surface}; }}

/* ---------- lists & scroll ---------- */
QListView {{ background: transparent; border: none; outline: none; }}
QScrollArea {{ background: transparent; border: none; }}
#SettingsScroll > QWidget, #SettingsForm {{ background: transparent; }}
#PdfCanvas {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px 2px 2px 0; }}
QScrollBar::handle:vertical {{ background: {p.border_strong}; border-radius: 4px; min-height: 36px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0 2px 2px 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border_strong}; border-radius: 4px; min-width: 36px; margin: 2px 0; }}
QScrollBar::handle:horizontal:hover {{ background: {p.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: transparent; }}

/* ---------- menus ---------- */
QMenu {{
    background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 7px 18px 7px 10px; border-radius: 6px; background: transparent; }}
QMenu::item:selected {{ background: {p.surface_hover}; color: {p.text}; }}
QMenu::item:disabled {{ color: {p.text_faint}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 8px; }}
QMenu::icon {{ padding-left: 6px; }}

/* ---------- dialogs ---------- */
QDialog {{ background: {p.surface}; }}
QMessageBox {{ background: {p.surface}; }}
#AboutName {{ font-size: 24px; font-weight: 700; }}
#AboutMeta {{ color: {p.text_muted}; font-size: 14px; }}
#AboutStrong {{ font-size: 14px; font-weight: 700; }}
#AboutText {{ color: {p.text}; font-size: 13px; }}
QTabWidget#LicenseTabs::pane {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 10px; top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {p.text_muted}; border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px; padding: 7px 16px; margin-right: 2px; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {p.text}; background: {p.surface_hover}; }}
QTabBar::tab:selected {{ color: {p.text}; background: {p.surface_alt}; border-color: {p.border}; }}
#LicenseText {{ background: {p.surface_alt}; border: none; padding: 6px; }}
"""


class ThemeManager(QObject):
    """Owns the light/dark/system mode and pushes palette + stylesheet into the app."""

    changed = Signal(object)
    MODES = ("system", "light", "dark")

    def __init__(self, app: QApplication, mode: str = "system"):
        super().__init__(app)
        self._app = app
        self._mode = mode if mode in self.MODES else "system"
        self._palette: Palette | None = None
        app.styleHints().colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def palette(self) -> Palette:
        return self._palette or _current

    def set_mode(self, mode: str) -> None:
        if mode not in self.MODES:
            return
        self._mode = mode
        self.apply(force=True)

    def cycle(self) -> str:
        self.set_mode(self.MODES[(self.MODES.index(self._mode) + 1) % len(self.MODES)])
        return self._mode

    def _system_is_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _resolve(self) -> Palette:
        if self._mode == "system":
            return DARK if self._system_is_dark() else LIGHT
        return DARK if self._mode == "dark" else LIGHT

    def _on_system_scheme_changed(self, *_):
        if self._mode == "system" and self._resolve() is not self._palette:
            self.apply()

    def apply(self, force: bool = False) -> None:
        global _current
        p = self._resolve()
        if p is self._palette and not force:
            return
        self._palette = p
        _current = p
        self._app.setPalette(build_qpalette(p))
        self._app.setStyleSheet(build_stylesheet(p))
        self.changed.emit(p)
        for w in self._app.topLevelWidgets():
            apply_window_frame(w, p)
            w.update()


def apply_window_frame(widget: QWidget, p: Palette) -> None:
    """Match the native Windows title bar to the palette (dark mode + caption colour on Win11)."""
    if sys.platform != "win32" or not widget.isWindow():
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        dark = ctypes.c_int(1 if p.is_dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new / pre-20H1)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark)) == 0:
                break
        col = QColor(p.window)
        caption = ctypes.c_uint(col.red() | (col.green() << 8) | (col.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption))  # DWMWA_CAPTION_COLOR
        txt = QColor(p.text)
        text = ctypes.c_uint(txt.red() | (txt.green() << 8) | (txt.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text), ctypes.sizeof(text))  # DWMWA_TEXT_COLOR
    except Exception:
        pass
