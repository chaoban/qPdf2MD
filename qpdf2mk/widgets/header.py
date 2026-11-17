"""Top bar: brand, workflow stepper, engine status, language and theme switches."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .. import APP_NAME, APP_TAGLINE, i18n, icons
from ..i18n import tr
from .controls import StatusPill, Stepper
from .joblist import styled_menu

# Labels are message keys: translate them where they are shown.
THEME_META = {
    "system": ("monitor", "跟隨系統"),
    "light": ("sun", "淺色"),
    "dark": ("moon", "深色"),
}


class HeaderBar(QWidget):
    themeClicked = Signal()
    aboutClicked = Signal()
    languageChosen = Signal(str)  # "system" or a language code

    SIDE_WIDTH = 290

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedHeight(66)
        row = QHBoxLayout(self)
        row.setContentsMargins(22, 10, 16, 8)
        row.setSpacing(0)

        left = QWidget()
        left.setMinimumWidth(self.SIDE_WIDTH)
        lrow = QHBoxLayout(left)
        lrow.setContentsMargins(0, 0, 0, 0)
        lrow.setSpacing(12)
        self.logo = QLabel()
        self.logo.setFixedSize(36, 36)
        self.logo.setPixmap(icons.app_icon().pixmap(36, 36))
        lrow.addWidget(self.logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addStretch(1)
        col.addWidget(QLabel(APP_NAME, objectName="AppTitle"))
        col.addWidget(QLabel(tr(APP_TAGLINE), objectName="AppSubtitle"))
        col.addStretch(1)
        lrow.addLayout(col)
        lrow.addStretch(1)
        row.addWidget(left, 1)

        self.stepper = Stepper()
        row.addWidget(self.stepper, 0, Qt.AlignmentFlag.AlignVCenter)

        right = QWidget()
        right.setMinimumWidth(self.SIDE_WIDTH)
        rrow = QHBoxLayout(right)
        rrow.setContentsMargins(0, 0, 0, 0)
        rrow.setSpacing(6)
        rrow.addStretch(1)
        self.engine = StatusPill()
        rrow.addWidget(self.engine, 0, Qt.AlignmentFlag.AlignVCenter)
        rrow.addSpacing(6)

        self.lang_btn = QToolButton()
        self.lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.binder.bind(self.lang_btn, "globe")
        self.lang_menu = styled_menu(self)
        group = QActionGroup(self)
        group.setExclusive(True)
        self._lang_actions = {}
        choices = [(i18n.SYSTEM, tr("跟隨系統", context="language"))] + list(i18n.LANGUAGES.items())
        for i, (code, label) in enumerate(choices):
            act = self.lang_menu.addAction(label)
            act.setCheckable(True)
            group.addAction(act)
            act.triggered.connect(lambda _=False, c=code: self.languageChosen.emit(c))
            self._lang_actions[code] = act
            if i == 0:
                self.lang_menu.addSeparator()
        self.lang_btn.clicked.connect(self._show_language_menu)
        rrow.addWidget(self.lang_btn)

        self.theme_btn = QToolButton()
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self.themeClicked)
        rrow.addWidget(self.theme_btn)
        self.about_btn = QToolButton()
        self.about_btn.setToolTip(tr("關於 {app}", app=APP_NAME))
        self.about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.binder.bind(self.about_btn, "info")
        self.about_btn.clicked.connect(self.aboutClicked)
        rrow.addWidget(self.about_btn)
        row.addWidget(right, 1)

        self.set_language_pref(i18n.SYSTEM)

    def set_theme_mode(self, mode: str) -> None:
        name, label = THEME_META.get(mode, THEME_META["system"])
        icons.binder.bind(self.theme_btn, name)
        self.theme_btn.setToolTip(tr("主題：{theme}（點擊切換）", theme=tr(label)))

    def set_language_pref(self, pref: str) -> None:
        """Tick the stored preference in the menu ("system" or a language code)."""
        act = self._lang_actions.get(pref) or self._lang_actions[i18n.SYSTEM]
        act.setChecked(True)
        self.lang_btn.setToolTip(tr("介面語言：{language}", language=i18n.LANGUAGES[i18n.current()]))

    def _show_language_menu(self) -> None:
        menu_w = self.lang_menu.sizeHint().width()
        pos = self.lang_btn.mapToGlobal(QPoint(self.lang_btn.width() - menu_w, self.lang_btn.height() + 4))
        self.lang_menu.exec(pos)
