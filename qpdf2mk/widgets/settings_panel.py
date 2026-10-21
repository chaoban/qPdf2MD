"""Right-hand panel: conversion options and the primary start/stop action."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import icons
from ..engine import ConvertOptions, parse_page_range
from .controls import SegmentedControl, ToggleRow

MODE_HINTS = {
    "layout": "以 AI 模型分析版面，精準辨識標題、清單、表格與閱讀順序，並自動略過頁首頁尾。每頁約需 1–2 秒。",
    "fast": "依字型大小推斷文件結構，速度極快，適合以文字為主、版面單純的文件。",
}
OCR_HINTS = {
    "auto": "自動找出掃描頁或沒有文字層的頁面，只辨識這些頁面。支援繁體中文、簡體中文、英文與日文。",
    "always": "每一頁都辨識，連圖片裡的文字也一併轉出，並取代 PDF 原有的 OCR 文字層。速度較慢。",
    "off": "不辨識文字。掃描版 PDF 將無法轉出文字內容。",
}
IMAGE_HINTS = {
    "folder": "圖片存放於「檔名_images」資料夾，並以相對路徑引用，適合 Git、Obsidian、Typora。",
    "embed": "以 Base64 內嵌於 .md 中，單一檔案即可攜帶，但檔案會明顯變大。",
    "none": "略過所有圖片，只保留文字內容。",
}

DEFAULTS = {
    "mode": "layout",
    "ocr": "auto",
    "pages": "all",
    "page_range": "",
    "images": "folder",
    "image_format": "png",
    "image_dpi": 150,
    "strip_headers_footers": True,
    "tidy": True,
    "page_markers": False,
    "front_matter": False,
    "output": "same",
    "output_dir": "",
    "conflict": "rename",
}


def _section(title: str) -> QLabel:
    return QLabel(title, objectName="SectionTitle")


def _hint(text: str = "") -> QLabel:
    label = QLabel(text, objectName="Hint")
    label.setWordWrap(True)
    return label


class SettingsPanel(QFrame):
    startRequested = Signal()
    stopRequested = Signal()
    optionsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self._running = False
        self._layout_available = True
        self._ocr_available = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 14, 0, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(20, 0, 12, 10)
        header.addWidget(QLabel("轉換設定", objectName="PanelTitle"))
        header.addStretch(1)
        self.reset_btn = QToolButton(objectName="Labeled")
        self.reset_btn.setText(" 重設")
        self.reset_btn.setToolTip("還原為預設設定")
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        icons.binder.bind(self.reset_btn, "refresh")
        self.reset_btn.clicked.connect(lambda: self.load_state(DEFAULTS))
        header.addWidget(self.reset_btn)
        outer.addLayout(header)

        scroll = QScrollArea(objectName="SettingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.form = QWidget()
        self.form.setObjectName("SettingsForm")
        self.form.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        form = QVBoxLayout(self.form)
        form.setContentsMargins(20, 4, 18, 18)
        form.setSpacing(8)
        scroll.setWidget(self.form)
        outer.addWidget(scroll, 1)

        # -- recognition mode
        form.addWidget(_section("辨識模式"))
        self.mode = SegmentedControl([("layout", "AI 版面分析", "sparkles"), ("fast", "快速模式", "zap")])
        form.addWidget(self.mode)
        self.mode_hint = _hint()
        form.addWidget(self.mode_hint)
        form.addSpacing(14)

        # -- OCR for scanned pages
        form.addWidget(_section("文字辨識（OCR）"))
        self.ocr = SegmentedControl([("auto", "自動", "scan"), ("always", "全部頁面", "pages"), ("off", "關閉", "x")])
        form.addWidget(self.ocr)
        self.ocr_hint = _hint()
        form.addWidget(self.ocr_hint)
        form.addSpacing(14)

        # -- page range
        form.addWidget(_section("頁面範圍"))
        self.pages = SegmentedControl([("all", "全部頁面"), ("custom", "指定頁面")])
        form.addWidget(self.pages)
        self.page_range = QLineEdit()
        self.page_range.setPlaceholderText("例如：1-5, 8, 12-")
        self.page_range.setClearButtonEnabled(True)
        form.addWidget(self.page_range)
        self.page_error = QLabel(objectName="ErrorText")
        self.page_error.setWordWrap(True)
        form.addWidget(self.page_error)
        form.addSpacing(14)

        # -- images
        form.addWidget(_section("圖片"))
        self.images = SegmentedControl([("folder", "存成檔案", "image"), ("embed", "內嵌", "code"), ("none", "不輸出", "x")])
        form.addWidget(self.images)
        self.images_hint = _hint()
        form.addWidget(self.images_hint)
        self.image_opts = QWidget()
        io = QVBoxLayout(self.image_opts)
        io.setContentsMargins(0, 4, 0, 0)
        io.setSpacing(8)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(12)
        fmt_row.addWidget(QLabel("格式", objectName="FieldLabel"))
        fmt_row.addStretch(1)
        self.image_format = SegmentedControl([("png", "PNG"), ("jpg", "JPG")], height=30)
        self.image_format.setFixedWidth(130)
        fmt_row.addWidget(self.image_format)
        io.addLayout(fmt_row)
        dpi_row = QHBoxLayout()
        dpi_row.setSpacing(12)
        dpi_row.addWidget(QLabel("解析度", objectName="FieldLabel"))
        self.dpi = QSlider(Qt.Orientation.Horizontal)
        self.dpi.setRange(72, 300)
        self.dpi.setSingleStep(6)
        self.dpi.setPageStep(24)
        self.dpi.setCursor(Qt.CursorShape.PointingHandCursor)
        dpi_row.addWidget(self.dpi, 1)
        self.dpi_label = QLabel(objectName="Hint")
        self.dpi_label.setFixedWidth(58)
        self.dpi_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        dpi_row.addWidget(self.dpi_label)
        io.addLayout(dpi_row)
        form.addWidget(self.image_opts)
        form.addSpacing(14)

        # -- content
        form.addWidget(_section("內容處理"))
        self.strip = ToggleRow("移除頁首、頁尾與頁碼", "略過每頁重複出現的頁眉、頁腳與頁碼文字")
        self.tidy = ToggleRow("自動整理格式", "合併斷行、修正清單縮排、清除多餘空行與標題粗體")
        self.markers = ToggleRow("加入頁面分隔標記", "在每頁開頭插入 <!-- page N --> 註解，方便對照原稿")
        self.front = ToggleRow("加入 YAML 前置資料", "於檔案開頭寫入標題、作者、來源與頁數（Front Matter）")
        for row in (self.strip, self.tidy, self.markers, self.front):
            form.addWidget(row)
            form.addSpacing(4)
        form.addSpacing(10)

        # -- output
        form.addWidget(_section("輸出位置"))
        self.output = SegmentedControl([("same", "與 PDF 相同", "file"), ("custom", "指定資料夾", "folder")])
        form.addWidget(self.output)
        self.dir_row = QWidget()
        dr = QHBoxLayout(self.dir_row)
        dr.setContentsMargins(0, 0, 0, 0)
        dr.setSpacing(6)
        self.output_dir = QLineEdit()
        self.output_dir.setReadOnly(True)
        self.output_dir.setPlaceholderText("尚未選擇資料夾")
        dr.addWidget(self.output_dir, 1)
        self.browse = QPushButton("選擇…")
        self.browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse.clicked.connect(self._browse)
        dr.addWidget(self.browse)
        form.addWidget(self.dir_row)
        conflict_row = QHBoxLayout()
        conflict_row.setSpacing(12)
        conflict_row.addWidget(QLabel("檔名重複時", objectName="FieldLabel"))
        conflict_row.addStretch(1)
        self.conflict = SegmentedControl([("rename", "自動改名"), ("overwrite", "覆寫")], height=30)
        self.conflict.setFixedWidth(170)
        conflict_row.addWidget(self.conflict)
        form.addSpacing(2)
        form.addLayout(conflict_row)
        form.addStretch(1)

        # -- footer with the primary action
        divider = QFrame(objectName="Divider")
        outer.addWidget(divider)
        foot = QVBoxLayout()
        foot.setContentsMargins(18, 12, 18, 16)
        foot.setSpacing(8)
        self.summary = QLabel(objectName="Hint")
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.addWidget(self.summary)
        self.start_btn = QPushButton(objectName="Primary")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setMinimumHeight(46)
        self.start_btn.clicked.connect(self._on_primary)
        foot.addWidget(self.start_btn)
        self.shortcut = QLabel("Ctrl + Enter", objectName="Faint")
        self.shortcut.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.addWidget(self.shortcut)
        outer.addLayout(foot)

        # -- wiring
        self.mode.changed.connect(self._sync)
        self.ocr.changed.connect(self._sync)
        self.pages.changed.connect(self._sync)
        self.images.changed.connect(self._sync)
        self.output.changed.connect(self._sync)
        self.page_range.textChanged.connect(self._sync)
        self.dpi.valueChanged.connect(self._sync)
        for w in (self.image_format, self.conflict):
            w.changed.connect(lambda *_: self.optionsChanged.emit())
        for row in (self.strip, self.tidy, self.markers, self.front):
            row.toggled.connect(lambda *_: self.optionsChanged.emit())

        self.load_state(DEFAULTS)
        self.set_counts(0, 0)

    # ---- state
    def state(self) -> dict:
        return {
            "mode": self.mode.value(),
            "ocr": self.ocr.value(),
            "pages": self.pages.value(),
            "page_range": self.page_range.text().strip(),
            "images": self.images.value(),
            "image_format": self.image_format.value(),
            "image_dpi": self.dpi.value(),
            "strip_headers_footers": self.strip.isChecked(),
            "tidy": self.tidy.isChecked(),
            "page_markers": self.markers.isChecked(),
            "front_matter": self.front.isChecked(),
            "output": self.output.value(),
            "output_dir": self.output_dir.text(),
            "conflict": self.conflict.value(),
        }

    def load_state(self, data: dict) -> None:
        s = {**DEFAULTS, **(data or {})}

        def as_bool(v):
            return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")

        self.mode.setValue(str(s["mode"]), animate=False)
        self.ocr.setValue(str(s["ocr"]), animate=False)
        self.pages.setValue(str(s["pages"]), animate=False)
        self.page_range.setText(str(s["page_range"]))
        self.images.setValue(str(s["images"]), animate=False)
        self.image_format.setValue(str(s["image_format"]), animate=False)
        try:
            self.dpi.setValue(int(s["image_dpi"]))
        except (TypeError, ValueError):
            self.dpi.setValue(150)
        self.strip.setChecked(as_bool(s["strip_headers_footers"]))
        self.tidy.setChecked(as_bool(s["tidy"]))
        self.markers.setChecked(as_bool(s["page_markers"]))
        self.front.setChecked(as_bool(s["front_matter"]))
        self.output.setValue(str(s["output"]), animate=False)
        self.output_dir.setText(str(s["output_dir"]))
        self.output_dir.setToolTip(str(s["output_dir"]))
        self.conflict.setValue(str(s["conflict"]), animate=False)
        self._sync()

    def options(self) -> ConvertOptions:
        s = self.state()
        return ConvertOptions(
            mode=s["mode"],
            ocr=s["ocr"],
            page_range=s["page_range"] if s["pages"] == "custom" else "",
            images=s["images"],
            image_format=s["image_format"],
            image_dpi=s["image_dpi"],
            strip_headers_footers=s["strip_headers_footers"],
            tidy=s["tidy"],
            page_markers=s["page_markers"],
            front_matter=s["front_matter"],
            output_dir=s["output_dir"] if s["output"] == "custom" else "",
            overwrite=s["conflict"] == "overwrite",
        )

    def validate(self) -> tuple[str, QWidget] | None:
        """Return (message, widget to focus) when the options cannot be used."""
        s = self.state()
        if s["pages"] == "custom":
            if not s["page_range"]:
                return "請輸入要轉換的頁面範圍", self.page_range
            try:
                parse_page_range(s["page_range"], None)
            except ValueError as exc:
                return str(exc), self.page_range
        if s["output"] == "custom":
            if not s["output_dir"]:
                return "請先選擇輸出資料夾", self.browse
            if not Path(s["output_dir"]).is_dir():
                return "輸出資料夾不存在，請重新選擇", self.browse
        return None

    # ---- runtime state
    def set_engine_info(self, layout_available: bool, ocr_available: bool) -> None:
        self._layout_available = layout_available
        self._ocr_available = ocr_available
        self._sync()

    def set_running(self, running: bool) -> None:
        self._running = running
        self.form.setEnabled(not running)
        self.reset_btn.setEnabled(not running)
        self.start_btn.setObjectName("Stop" if running else "Primary")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self._refresh_button()

    def set_counts(self, pending: int, total: int, done: int = 0) -> None:
        self._pending, self._total, self._done = pending, total, done
        self._refresh_button()

    def refresh_theme(self, *_):
        self._refresh_button()

    def _refresh_button(self) -> None:
        pending, total = getattr(self, "_pending", 0), getattr(self, "_total", 0)
        btn = self.start_btn
        if self._running:
            btn.setText("  停止轉換")
            icons.binder.bind(btn, "stop", "danger")
            btn.setEnabled(True)
            self.summary.setText("轉換進行中，完成的檔案會即時出現在預覽中")
            self.shortcut.setText("Esc 停止")
            return
        icons.binder.bind(btn, "play", "on_accent")
        self.shortcut.setText("Ctrl + Enter")
        if total == 0:
            btn.setText("  開始轉換")
            btn.setEnabled(False)
            self.summary.setText("請先加入 PDF 檔案")
        elif pending == 0:
            btn.setText(f"  全部重新轉換（{total}）")
            btn.setEnabled(True)
            self.summary.setText(f"{total} 個檔案皆已轉換完成")
        else:
            btn.setText(f"  開始轉換（{pending}）" if pending > 1 else "  開始轉換")
            btn.setEnabled(True)
            where = "原 PDF 所在資料夾" if self.output.value() == "same" else "指定資料夾"
            self.summary.setText(f"{pending} 個檔案待轉換　·　輸出至{where}")

    def _on_primary(self) -> None:
        (self.stopRequested if self._running else self.startRequested).emit()

    def _browse(self) -> None:
        start = self.output_dir.text() or str(Path.home() / "Documents")
        folder = QFileDialog.getExistingDirectory(self, "選擇 Markdown 輸出資料夾", start)
        if folder:
            self.output_dir.setText(str(Path(folder)))
            self.output_dir.setToolTip(str(Path(folder)))
            self._sync()

    def _sync(self, *_):
        mode = self.mode.value()
        hint = MODE_HINTS[mode]
        if mode == "layout" and not self._layout_available:
            hint = "AI 版面分析模組無法載入，將自動改用快速模式。"
        self.mode_hint.setText(hint)
        ocr_hint = OCR_HINTS.get(self.ocr.value(), "")
        if self.ocr.value() != "off" and not self._ocr_available:
            ocr_hint = "OCR 元件無法載入，掃描頁面將無法轉出文字。"
        self.ocr_hint.setText(ocr_hint)
        custom_pages = self.pages.value() == "custom"
        self.page_range.setVisible(custom_pages)
        err = ""
        if custom_pages and self.page_range.text().strip():
            try:
                parse_page_range(self.page_range.text(), None)
            except ValueError as exc:
                err = str(exc)
        self.page_error.setText(err)
        self.page_error.setVisible(bool(err))
        self.page_range.setProperty("invalid", bool(err))
        self.page_range.style().unpolish(self.page_range)
        self.page_range.style().polish(self.page_range)
        img = self.images.value()
        self.images_hint.setText(IMAGE_HINTS[img])
        self.image_opts.setVisible(img != "none")
        self.dpi_label.setText(f"{self.dpi.value()} DPI")
        self.dir_row.setVisible(self.output.value() == "custom")
        self._refresh_button()
        self.optionsChanged.emit()
