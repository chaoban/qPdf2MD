"""Top bar: brand, workflow stepper, engine status and theme switch."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from .. import APP_NAME, APP_TAGLINE, icons
from .controls import StatusPill, Stepper

THEME_META = {
    "system": ("monitor", "跟隨系統"),
    "light": ("sun", "淺色"),
    "dark": ("moon", "深色"),
}


class HeaderBar(QWidget):
    themeClicked = Signal()
    aboutClicked = Signal()

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
        col.addWidget(QLabel(APP_TAGLINE, objectName="AppSubtitle"))
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
        self.theme_btn = QToolButton()
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.clicked.connect(self.themeClicked)
        rrow.addWidget(self.theme_btn)
        self.about_btn = QToolButton()
        self.about_btn.setToolTip(f"關於 {APP_NAME}")
        self.about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.binder.bind(self.about_btn, "info")
        self.about_btn.clicked.connect(self.aboutClicked)
        rrow.addWidget(self.about_btn)
        row.addWidget(right, 1)

    def set_theme_mode(self, mode: str) -> None:
        name, label = THEME_META.get(mode, THEME_META["system"])
        icons.binder.bind(self.theme_btn, name)
        self.theme_btn.setToolTip(f"主題：{label}（點擊切換）")
