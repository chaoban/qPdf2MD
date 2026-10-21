"""Small modal dialogs: PDF password prompt, the About box and the license viewer."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QRectF, Qt, qVersion
from PySide6.QtGui import QAction, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from .. import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    CONTACT_EMAIL,
    COPYRIGHT,
    LICENSE_NAME,
    PRIVACY_URL,
    SOURCE_URL,
    brand,
    icons,
    legal,
    theme,
)


def _badge(name: str, role: str, size: int = 48, dpr: float = 1.0) -> QPixmap:
    p = theme.current()
    img = QImage(int(size * dpr), int(size * dpr), QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(p.color(role, 0.16))
    painter.drawRoundedRect(QRectF(0, 0, size, size), 14, 14)
    pad = size * 0.27
    icons.paint(painter, name, QRectF(pad, pad, size - 2 * pad, size - 2 * pad), getattr(p, role), 2.0)
    painter.end()
    return QPixmap.fromImage(img)


class PasswordDialog(QDialog):
    def __init__(self, parent, filename: str, validator: Callable[[str], bool]):
        super().__init__(parent)
        self._validator = validator
        self.setWindowTitle("需要密碼")
        self.setModal(True)
        self.setFixedWidth(440)
        theme.apply_window_frame(self, theme.current())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(14)
        badge = QLabel()
        badge.setPixmap(_badge("lock", "warning", 48, self.devicePixelRatioF()))
        top.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(QLabel("此 PDF 受密碼保護", objectName="StateTitle"))
        name = QLabel(filename, objectName="Hint")
        name.setWordWrap(True)
        col.addWidget(name)
        top.addLayout(col, 1)
        layout.addLayout(top)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("輸入開啟密碼")
        self.edit.setMinimumHeight(38)
        self._reveal = QAction(icons.themed("eye"), "顯示密碼", self.edit)
        self._reveal.triggered.connect(self._toggle_reveal)
        self.edit.addAction(self._reveal, QLineEdit.ActionPosition.TrailingPosition)
        layout.addWidget(self.edit)
        self.error = QLabel(objectName="ErrorText")
        self.error.hide()
        layout.addWidget(self.error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        skip = QPushButton("略過此檔案")
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.clicked.connect(self.reject)
        buttons.addWidget(skip)
        self.ok = QPushButton("解鎖", objectName="Primary")
        self.ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok.setDefault(True)
        self.ok.clicked.connect(self._try)
        buttons.addWidget(self.ok)
        layout.addSpacing(4)
        layout.addLayout(buttons)
        self.edit.returnPressed.connect(self._try)

    def password(self) -> str:
        return self.edit.text()

    def _toggle_reveal(self):
        hidden = self.edit.echoMode() == QLineEdit.EchoMode.Password
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)

    def _try(self):
        if not self.edit.text():
            self._show_error("請輸入密碼")
            return
        if self._validator(self.edit.text()):
            self.accept()
        else:
            self._show_error("密碼不正確，請再試一次")

    def _show_error(self, msg: str):
        self.error.setText(msg)
        self.error.show()
        self.edit.setProperty("invalid", True)
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)
        self.edit.selectAll()
        self.edit.setFocus()


def _link(url: str, text: Optional[str] = None) -> str:
    p = theme.current()
    color = p.accent_hover if p.is_dark else p.accent
    return f"<a href='{url}' style='color:{color}; text-decoration:none'>{text or url}</a>"


def _rich_label(html: str, width: int, object_name: str = "AboutText") -> QLabel:
    """Wrapped rich text at a fixed width. Dialogs do not resize for height-for-width layouts on their own,
    so the label reserves the height its wrapped text needs."""
    label = QLabel(html, objectName=object_name)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setWordWrap(True)
    label.setOpenExternalLinks(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    label.setFixedWidth(width)
    label.ensurePolished()  # apply the stylesheet font before measuring
    label.setMinimumHeight(label.heightForWidth(width))
    return label


class AboutDialog(QDialog):
    """Publisher banner, product identity, and the legal notices the AGPL asks an interactive program to show."""

    def __init__(self, parent, engine_text: str):
        super().__init__(parent)
        p = theme.current()
        self.setWindowTitle(f"關於 {APP_NAME}")
        self.setModal(True)
        theme.apply_window_frame(self, p)
        width = 508  # content width

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(0)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        banner = brand.LogoBanner(104)
        banner.setFixedWidth(width)
        layout.addWidget(banner)
        layout.addSpacing(20)

        ident = QHBoxLayout()
        ident.setSpacing(18)
        logo = QLabel()
        logo.setPixmap(icons.app_icon().pixmap(72, 72))
        ident.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(QLabel(APP_NAME, objectName="AboutName"))
        col.addWidget(QLabel(f"版本 {APP_VERSION}", objectName="AboutMeta"))
        col.addWidget(QLabel(APP_TAGLINE, objectName="AboutMeta"))
        ident.addLayout(col, 1)
        layout.addLayout(ident)
        layout.addSpacing(18)
        layout.addWidget(QFrame(objectName="Divider"))
        layout.addSpacing(16)

        layout.addWidget(QLabel(COPYRIGHT, objectName="AboutStrong"))
        layout.addSpacing(6)
        source = _link(SOURCE_URL) if SOURCE_URL else f"<span style='color:{p.danger}'>（尚未公開）</span>"
        layout.addWidget(_rich_label(
            f"{APP_NAME} 是自由軟體，依 {LICENSE_NAME} 授權發布，不提供任何擔保。<br>原始碼：{source}", width
        ))
        layout.addSpacing(12)
        contact = f"聯絡信箱：{_link('mailto:' + CONTACT_EMAIL, CONTACT_EMAIL)}"
        if PRIVACY_URL:
            contact += f"<br>隱私權政策：{_link(PRIVACY_URL)}"
        layout.addWidget(_rich_label(contact, width))
        layout.addSpacing(12)
        layout.addWidget(_rich_label(
            f"本軟體使用 Qt {qVersion()} 開發，Qt 依 GNU LGPL v3 授權使用。<br>"
            f"Qt 原始碼：{_link(legal.QT_OPEN_SOURCE_URL)}<br>"
            "PDF 轉換使用 PyMuPDF／pymupdf4llm（GNU AGPL v3），文字辨識使用 RapidOCR（Apache 2.0）。<br>"
            "其他第三方元件與授權全文請見「授權資訊」。", width
        ))
        if engine_text:
            layout.addSpacing(8)
            layout.addWidget(_rich_label(engine_text, width, "Faint"))
        layout.addSpacing(20)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        actions = (
            ("授權資訊…", self._show_licenses),
            ("關於 Qt…", lambda: QMessageBox.aboutQt(self, "關於 Qt")),
            ("關閉", self.accept),
        )
        for text, slot in actions:
            btn = QPushButton(text)
            btn.setMinimumWidth(104)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        btn.setDefault(True)  # 關閉
        layout.addLayout(buttons)

    def _show_licenses(self) -> None:
        LicensesDialog(self).exec()


class LicensesDialog(QDialog):
    """Third-party notices plus the full GNU license texts, one tab each."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"授權資訊 — {APP_NAME}")
        self.setModal(True)
        theme.apply_window_frame(self, theme.current())
        screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        self.resize(min(860, avail.width() - 80), min(680, avail.height() - 80))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        tabs = QTabWidget(objectName="LicenseTabs")
        tabs.setDocumentMode(True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)  # notices are generated live when run from source
        try:
            pages = [("第三方元件", legal.third_party_notices())]
            pages += [(title, legal.license_text(name)) for title, name in legal.LICENSE_TABS]
        finally:
            QApplication.restoreOverrideCursor()
        for title, text in pages:
            view = QPlainTextEdit(objectName="LicenseText")
            view.setReadOnly(True)
            view.setFont(theme.mono_font(9.5))
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
            view.setPlainText(text)
            tabs.addTab(view, title)
        layout.addWidget(tabs, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("關閉")
        close.setMinimumWidth(104)
        close.setDefault(True)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)
