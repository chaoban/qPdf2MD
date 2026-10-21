"""Preview panel: original PDF pages, rendered Markdown and highlighted Markdown source."""

from __future__ import annotations

import base64
import math
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPixmap,
    QSyntaxHighlighter,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrameFormat,
    QTextImageFormat,
    QTextLength,
    QTextTable,
    QTextTableFormat,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import icons, theme
from ..jobs import Job, RenderService, Status, human_size
from .controls import ProgressRing, SegmentedControl

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_DATA_URI = re.compile(r"(data:image/[A-Za-z0-9.+-]+;base64,)([A-Za-z0-9+/=]{120,})")


# --------------------------------------------------------------------------- PDF pages

class _PageWidget(QWidget):
    PAD_X, PAD_TOP, PAD_BOTTOM = 8, 4, 10

    def __init__(self, index: int, aspect: float, parent=None):
        super().__init__(parent)
        self.index = index
        self.aspect = aspect
        self.image: Optional[QImage] = None
        self.page_w = 0

    @property
    def rendered_w(self) -> int:
        return self.image.width() if self.image is not None else 0

    def set_width(self, w: int) -> None:
        self.page_w = w
        self.setFixedSize(w + 2 * self.PAD_X, round(w * self.aspect) + self.PAD_TOP + self.PAD_BOTTOM)

    def set_image(self, image: QImage) -> None:
        self.image = image
        aspect = image.height() / max(image.width(), 1)
        if abs(aspect - self.aspect) > 0.01:
            self.aspect = aspect
            self.set_width(self.page_w)
        self.update()

    def drop_image(self) -> None:
        if self.image is not None:
            self.image = None
            self.update()

    def paintEvent(self, _):
        p = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        page = QRectF(self.PAD_X, self.PAD_TOP, self.page_w, self.height() - self.PAD_TOP - self.PAD_BOTTOM)
        painter.setPen(Qt.PenStyle.NoPen)
        for spread, alpha in ((6, 0.04), (3, 0.06), (1.2, 0.10)):
            painter.setBrush(p.color("shadow", alpha * (2.2 if p.is_dark else 1.0)))
            painter.drawRoundedRect(page.adjusted(-spread, -spread + 2, spread, spread + 2), 4 + spread, 4 + spread)
        painter.setBrush(p.color("page"))
        painter.drawRoundedRect(page, 3, 3)
        if self.image is not None:
            painter.drawImage(page, self.image)
        else:
            painter.setPen(QColor("#B4BAC6"))
            painter.setFont(theme.ui_font(11, QFont.Weight.DemiBold))
            painter.drawText(page, Qt.AlignmentFlag.AlignCenter, f"第 {self.index + 1} 頁")


class PdfPagesView(QScrollArea):
    pageChanged = Signal(int, int)
    MAX_PAGES = 3000

    def __init__(self, renderer: RenderService, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._canvas = QWidget(objectName="PdfCanvas")
        self._vbox = QVBoxLayout(self._canvas)
        self._vbox.setContentsMargins(20, 18, 20, 26)
        self._vbox.setSpacing(8)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._canvas)
        self._renderer = renderer
        self._renderer.rendered.connect(self._on_rendered)
        self._pages: list[_PageWidget] = []
        self._path: Optional[str] = None
        self._gen = -1
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._refresh)
        self.verticalScrollBar().valueChanged.connect(lambda *_: self._timer.start())

    @property
    def path(self) -> Optional[str]:
        return self._path

    def set_document(self, path: Path, page_count: int, page_size: tuple[float, float]) -> None:
        key = str(path)
        if key == self._path and len(self._pages) == min(page_count, self.MAX_PAGES):
            return
        self.clear()
        self._path = key
        self._renderer.generation += 1
        self._gen = self._renderer.generation
        aspect = page_size[1] / max(page_size[0], 1)
        for i in range(min(page_count, self.MAX_PAGES)):
            pw = _PageWidget(i, aspect, self._canvas)
            self._pages.append(pw)
            self._vbox.addWidget(pw, 0, Qt.AlignmentFlag.AlignHCenter)
        self._apply_width()
        self.verticalScrollBar().setValue(0)
        self._timer.start()

    def clear(self) -> None:
        for pw in self._pages:
            pw.deleteLater()
        self._pages = []
        self._path = None
        self._renderer.wanted = None

    def _target_width(self) -> int:
        return max(220, min(self.viewport().width() - 56, 880))

    def _apply_width(self) -> None:
        w = self._target_width()
        for pw in self._pages:
            pw.set_width(w)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_width()
        self._timer.start()

    def showEvent(self, e):
        super().showEvent(e)
        self._timer.start()

    def _refresh(self) -> None:
        if not self._pages or not self.isVisible():
            return
        top = self.verticalScrollBar().value()
        vh = self.viewport().height()
        lo, hi = top - vh * 0.5, top + vh * 1.8
        need = int(self._target_width() * self.devicePixelRatioF())
        bucket = int(math.ceil(need / 128) * 128)
        wanted: set[tuple[str, int]] = set()
        current = 0
        for pw in self._pages:
            y, h = pw.y(), pw.height()
            if y + h >= lo and y <= hi:
                wanted.add((self._path, pw.index))
                if pw.rendered_w < need * 0.95 or pw.rendered_w > bucket * 1.6:
                    self._renderer.render(Path(self._path), pw.index, bucket, self._gen)
            elif y + h < top - 4 * vh or y > top + 5 * vh:
                pw.drop_image()
            if y + h * 0.5 <= top + vh * 0.5:
                current = pw.index
        self._renderer.wanted = wanted
        self.pageChanged.emit(current + 1, len(self._pages))

    def _on_rendered(self, path: str, page: int, gen: int, image: QImage) -> None:
        if gen == self._gen and path == self._path and 0 <= page < len(self._pages):
            self._pages[page].set_image(image)


# --------------------------------------------------------------------------- rendered markdown

_UNDERSCORE_EM = re.compile(r"(?<![\w_\\])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])")
_FENCE_SPLIT = re.compile(r"(^```.*?^```[^\n]*$)", re.M | re.S)


def _preview_markdown(md: str) -> str:
    """Adjust Markdown for QTextDocument: front matter → table, _em_ → *em* (outside code).

    Qt's GitHub dialect renders _text_ as underline, which reads like a link.
    """
    parts = _FENCE_SPLIT.split(_front_matter_as_table(md))
    for i in range(0, len(parts), 2):
        parts[i] = _UNDERSCORE_EM.sub(r"*\1*", parts[i])
    return "".join(parts)


def _front_matter_as_table(md: str) -> str:
    m = _FRONT_MATTER.match(md)
    if not m:
        return md
    rows = []
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append(f"| {k.strip()} | {v.strip().strip(chr(34))} |")
    table = "| 屬性 | 值 |\n|---|---|\n" + "\n".join(rows) + "\n\n"
    return table + md[m.end():]


class MarkdownView(QTextBrowser):
    MAX_WIDTH = 820

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.setAcceptDrops(False)
        self.setFont(theme.ui_font(10.5))
        self._md = ""
        self._base: Optional[Path] = None
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(80)
        self._fit_timer.timeout.connect(self._fit_images)

    def set_markdown(self, md: str, base_dir: Path) -> None:
        self._md, self._base = md, base_dir
        self._rebuild()
        self.verticalScrollBar().setValue(0)

    def refresh_theme(self) -> None:
        if self._md:
            pos = self.verticalScrollBar().value()
            self._rebuild()
            self.verticalScrollBar().setValue(pos)

    def _rebuild(self) -> None:
        doc = self.document()
        doc.clear()
        if self._base is not None:
            doc.setBaseUrl(QUrl.fromLocalFile(str(self._base) + "/"))
        doc.setDocumentMargin(34)
        doc.setMarkdown(_preview_markdown(self._md), QTextDocument.MarkdownFeature.MarkdownDialectGitHub)
        self._style_document()
        self._fit_images()

    def loadResource(self, type_, url: QUrl):
        if type_ == QTextDocument.ResourceType.ImageResource.value or type_ == QTextDocument.ResourceType.ImageResource:
            s = url.toString()
            if s.startswith("data:image"):
                img = QImage()
                try:
                    img.loadFromData(base64.b64decode(s.split(",", 1)[1]))
                except Exception:
                    pass
                return img
        return super().loadResource(type_, url)

    def _open_link(self, url: QUrl) -> None:
        if url.isRelative() and self._base is not None:
            url = QUrl.fromLocalFile(str(self._base / url.toString(QUrl.ComponentFormattingOption.FullyDecoded)))
        QDesktopServices.openUrl(url)

    def resizeEvent(self, e):
        extra = max(0, (self.width() - self.MAX_WIDTH) // 2)
        self.setViewportMargins(extra, 0, extra, 0)
        super().resizeEvent(e)
        self._fit_timer.start()

    def _style_document(self) -> None:
        p = theme.current()
        doc = self.document()
        base = self.font().pointSizeF()
        scales = {1: 1.85, 2: 1.45, 3: 1.22, 4: 1.08, 5: 1.0, 6: 0.95}
        mono = theme.mono_font(base * 0.92)
        text_color = p.color("text")
        link = p.color("accent_hover" if p.is_dark else "accent")

        cur = QTextCursor(doc)
        cur.beginEditBlock()
        block = doc.begin()
        while block.isValid():
            bf = QTextBlockFormat(block.blockFormat())
            level = bf.headingLevel()
            bc = QTextCursor(block)
            in_table = bc.currentTable() is not None
            is_code = bf.hasProperty(QTextFormat.Property.BlockCodeFence) or bf.nonBreakableLines()
            quote = bf.property(QTextFormat.Property.BlockQuoteLevel)

            if level:
                bf.setTopMargin({1: 6, 2: 22}.get(level, 16))
                bf.setBottomMargin(10 if level <= 2 else 6)
                bc.setBlockFormat(bf)
                bc.select(QTextCursor.SelectionType.BlockUnderCursor)
                cf = QTextCharFormat()
                cf.setFontPointSize(base * scales[level])
                cf.setFontWeight(QFont.Weight.Bold)
                cf.setForeground(text_color)
                bc.mergeCharFormat(cf)
            elif is_code:
                bf.setBackground(p.color("code_bg"))
                bf.setLeftMargin(2)
                bf.setRightMargin(2)
                bf.setTopMargin(0)
                bf.setBottomMargin(0)
                bc.setBlockFormat(bf)
                bc.select(QTextCursor.SelectionType.BlockUnderCursor)
                cf = QTextCharFormat()
                cf.setFont(mono)
                cf.setForeground(p.color("text"))
                bc.mergeCharFormat(cf)
            elif not in_table:
                in_list = block.textList() is not None
                bf.setTopMargin(0)
                bf.setLineHeight(130 if in_list else 150, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                bf.setBottomMargin(2 if in_list else 10)
                if quote:
                    bf.setLeftMargin(18)
                    bf.setBackground(p.color("accent", 0.07))
                bc.setBlockFormat(bf)

            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    cf = frag.charFormat()
                    fc = QTextCursor(doc)
                    fc.setPosition(frag.position())
                    fc.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                    if cf.isAnchor():
                        nf = QTextCharFormat()
                        nf.setForeground(link)
                        nf.setFontUnderline(False)
                        fc.mergeCharFormat(nf)
                    elif cf.fontFixedPitch() and not is_code:
                        nf = QTextCharFormat()
                        nf.setFont(mono)
                        nf.setBackground(p.color("code_bg"))
                        nf.setForeground(p.color("danger" if not p.is_dark else "warning"))
                        fc.mergeCharFormat(nf)
                    elif quote:
                        nf = QTextCharFormat()
                        nf.setForeground(p.color("text_muted"))
                        fc.mergeCharFormat(nf)
                it += 1
            block = block.next()

        for frame in doc.rootFrame().childFrames():
            if isinstance(frame, QTextTable):
                tf = QTextTableFormat(frame.format())
                tf.setBorder(1)
                tf.setBorderBrush(QBrush(p.color("border_strong")))
                tf.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                tf.setBorderCollapse(True)
                tf.setCellPadding(7)
                tf.setCellSpacing(0)
                tf.setTopMargin(4)
                tf.setBottomMargin(14)
                tf.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
                frame.setFormat(tf)
                for c in range(frame.columns()):
                    cell = frame.cellAt(0, c)
                    fmt = cell.format()
                    fmt.setBackground(p.color("surface_alt" if not p.is_dark else "surface_hover"))
                    fmt.setFontWeight(QFont.Weight.Bold)
                    cell.setFormat(fmt)
        cur.endEditBlock()

        pal = self.palette()
        pal.setColor(pal.ColorRole.Text, text_color)
        pal.setColor(pal.ColorRole.Base, p.color("surface"))
        pal.setColor(pal.ColorRole.Link, link)
        self.setPalette(pal)

    def _fit_images(self) -> None:
        """Scale down images wider than the reading column (QTextDocument never does)."""
        doc = self.document()
        max_w = self.viewport().width() - 2 * doc.documentMargin() - 8
        if max_w <= 50:
            return
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                cf = frag.charFormat()
                if frag.isValid() and cf.isImageFormat():
                    imgf = QTextImageFormat(cf.toImageFormat())
                    res = doc.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(imgf.name()))
                    if isinstance(res, QPixmap):
                        res = res.toImage()
                    elif isinstance(res, (QByteArray, bytes)):
                        res = QImage.fromData(res)
                    if isinstance(res, QImage) and not res.isNull():
                        w, h = res.width() / self.devicePixelRatioF(), res.height() / self.devicePixelRatioF()
                        target = min(w, max_w)
                        if abs(imgf.width() - target) > 1:
                            imgf.setWidth(target)
                            imgf.setHeight(h * target / max(w, 1))
                            fc = QTextCursor(doc)
                            fc.setPosition(frag.position())
                            fc.setPosition(frag.position() + frag.length(), QTextCursor.MoveMode.KeepAnchor)
                            fc.setCharFormat(imgf)
                it += 1
            block = block.next()
        cur.endEditBlock()


# --------------------------------------------------------------------------- source view

class MarkdownHighlighter(QSyntaxHighlighter):
    _HEADING = re.compile(r"^#{1,6}\s.*$")
    _LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
    _QUOTE = re.compile(r"^\s*>.*$")
    _BOLD = re.compile(r"\*\*[^*]+\*\*|__[^_]+__")
    _ITALIC = re.compile(r"(?<![*\w])\*[^*\s][^*]*\*(?!\*)|(?<![_\w])_[^_\s][^_]*_(?![_\w])")
    _CODE = re.compile(r"`[^`]+`")
    _LINK = re.compile(r"(!?\[)([^\]]*)(\]\()([^)]*)(\))")
    _COMMENT = re.compile(r"<!--.*?-->")
    _HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")

    def __init__(self, document):
        super().__init__(document)
        self.set_palette(theme.current())

    def set_palette(self, p) -> None:
        def fmt(role, bold=False, italic=False, alpha=1.0):
            f = QTextCharFormat()
            f.setForeground(p.color(role, alpha))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        accent = "accent_hover" if p.is_dark else "accent"
        self.f_heading = fmt(accent, bold=True)
        self.f_marker = fmt(accent, bold=True)
        self.f_bold = fmt("text", bold=True)
        self.f_italic = fmt("text", italic=True)
        self.f_code = fmt("warning" if p.is_dark else "danger")
        self.f_fence = fmt("text_faint")
        self.f_codeblock = fmt("success")
        self.f_link = fmt("accent_2")
        self.f_url = fmt("text_faint")
        self.f_quote = fmt("text_muted", italic=True)
        self.f_table = fmt("text_faint", bold=True)
        self.f_comment = fmt("text_faint", italic=True)
        self.f_meta = fmt("text_muted")
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        prev = self.previousBlockState()
        stripped = text.strip()
        # state 1 = inside code fence, 2 = inside front matter
        if prev == 1:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                self.setFormat(0, len(text), self.f_fence)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self.f_codeblock)
                self.setCurrentBlockState(1)
            return
        if prev == 2 or (self.currentBlock().blockNumber() == 0 and stripped == "---"):
            self.setFormat(0, len(text), self.f_meta)
            self.setCurrentBlockState(0 if (prev == 2 and stripped == "---") else 2)
            return
        if stripped.startswith("```") or stripped.startswith("~~~"):
            self.setFormat(0, len(text), self.f_fence)
            self.setCurrentBlockState(1)
            return
        self.setCurrentBlockState(0)

        if self._HEADING.match(text):
            self.setFormat(0, len(text), self.f_heading)
            return
        if self._HR.match(text):
            self.setFormat(0, len(text), self.f_fence)
            return
        if self._QUOTE.match(text):
            self.setFormat(0, len(text), self.f_quote)
        m = self._LIST.match(text)
        if m:
            self.setFormat(0, m.end(), self.f_marker)
        if stripped.startswith("|"):
            for i, ch in enumerate(text):
                if ch == "|":
                    self.setFormat(i, 1, self.f_table)
            if re.fullmatch(r"[\s|:-]+", text):
                self.setFormat(0, len(text), self.f_table)
        for rx, f in ((self._BOLD, self.f_bold), (self._ITALIC, self.f_italic), (self._CODE, self.f_code), (self._COMMENT, self.f_comment)):
            for mm in rx.finditer(text):
                self.setFormat(mm.start(), mm.end() - mm.start(), f)
        for mm in self._LINK.finditer(text):
            self.setFormat(mm.start(2), len(mm.group(2)), self.f_link)
            self.setFormat(mm.start(4), len(mm.group(4)), self.f_url)


class SourceView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SourceView")
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFont(theme.mono_font(10))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setAcceptDrops(False)
        self.document().setDocumentMargin(22)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.highlighter = MarkdownHighlighter(self.document())

    def set_markdown(self, md: str) -> None:
        # Keep huge base64 payloads from turning the source view into a wall of noise.
        shown = _DATA_URI.sub(lambda m: f"{m.group(1)}…（{len(m.group(2)) * 3 // 4 // 1024 + 1} KB 內嵌圖片）", md)
        self.setPlainText(shown)

    def refresh_theme(self) -> None:
        self.highlighter.set_palette(theme.current())


# --------------------------------------------------------------------------- state view

class StateView(QWidget):
    actionRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.addStretch(3)
        self.ring = ProgressRing(96)
        layout.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        self.icon = QLabel()
        self.icon.setFixedSize(72, 72)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)
        self.title = QLabel(objectName="StateTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addSpacing(4)
        self.text = QLabel(objectName="StateText")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        self.text.setMaximumWidth(460)
        layout.addWidget(self.text, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(18)
        self.button = QPushButton()
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(lambda: self.actionRequested.emit(self._action))
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(4)
        self._action = ""
        self._icon_spec: tuple[str, str] | None = None

    def show_state(self, title: str, text: str, *, icon: str | None = None, role: str = "text_faint",
                   progress: float | None = None, button: str | None = None, action: str = "",
                   primary: bool = False) -> None:
        self.title.setText(title)
        self.text.setText(text)
        self.text.setVisible(bool(text))
        # QLabel under-estimates wrapped CJK width; give it room for one full line up to the cap.
        self.text.setMinimumWidth(min(self.text.fontMetrics().horizontalAdvance(text) + 12, 460))
        if progress is not None:
            self.ring.show()
            self.ring.set_value(progress)
            self.icon.hide()
        else:
            self.ring.hide()
            self.ring.reset()
            self._icon_spec = (icon or "info", role)
            self._paint_icon()
            self.icon.show()
        self._action = action
        self.button.setVisible(bool(button))
        if button:
            self.button.setText(button)
            self.button.setObjectName("Primary" if primary else "")
            self.button.style().unpolish(self.button)
            self.button.style().polish(self.button)

    def _paint_icon(self) -> None:
        if not self._icon_spec:
            return
        name, role = self._icon_spec
        p = theme.current()
        dpr = self.devicePixelRatioF()
        size = 72
        canvas = QImage(int(size * dpr), int(size * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.setDevicePixelRatio(dpr)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        tint = role if role != "text_faint" else "accent"
        painter.setBrush(p.color(tint, 0.14 if p.is_dark else 0.09))
        painter.drawEllipse(QRectF(0, 0, size, size))
        icons.paint(painter, name, QRectF(22, 22, 28, 28), getattr(p, tint if tint != "accent" or not p.is_dark else "accent_hover"), 1.8)
        painter.end()
        self.icon.setPixmap(QPixmap.fromImage(canvas))

    def refresh_theme(self) -> None:
        self._paint_icon()
        self.ring.update()


# --------------------------------------------------------------------------- chips

class StatChip(QFrame):
    def __init__(self, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatChip")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 10, 3)
        row.setSpacing(6)
        self._icon_name = icon_name
        self._icon = QLabel()
        row.addWidget(self._icon)
        self.label = QLabel()
        row.addWidget(self.label)
        self.refresh_theme()

    def set_text(self, text: str) -> None:
        self.label.setText(text)

    def refresh_theme(self) -> None:
        self._icon.setPixmap(icons.pixmap(self._icon_name, theme.current().text_faint, 14, self.devicePixelRatioF(), 2.0))


# --------------------------------------------------------------------------- panel

class PreviewPanel(QFrame):
    actionRequested = Signal(str, int)  # action, job id

    TABS = [("pdf", "原始 PDF", "file"), ("rendered", "預覽", "eye"), ("source", "Markdown", "code")]

    def __init__(self, renderer: RenderService, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self._job: Optional[Job] = None
        self._loaded: dict[str, tuple[int, int]] = {}  # tab -> (job id, id(markdown))
        self._page_info = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(18, 0, 12, 12)
        header.setSpacing(10)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self.title = QLabel("預覽", objectName="PanelTitle")
        self.subtitle = QLabel("", objectName="Faint")
        for label in (self.title, self.subtitle):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setMinimumWidth(60)
            title_col.addWidget(label)
        header.addLayout(title_col, 1)
        self.tabs = SegmentedControl(self.TABS)
        self.tabs.setFixedWidth(self.tabs.sizeHint().width() + 12)
        self.tabs.changed.connect(self._on_tab)
        header.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addSpacing(4)
        self.buttons: dict[str, QToolButton] = {}
        for key, icon_name, tip in (
            ("copy", "copy", "複製 Markdown（Ctrl+Shift+C）"),
            ("open", "external", "用預設程式開啟 .md"),
            ("reveal", "folder", "在檔案總管中顯示"),
            ("save_as", "download", "另存新檔…"),
        ):
            btn = QToolButton()
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            icons.binder.bind(btn, icon_name)
            btn.clicked.connect(lambda _=False, k=key: self._emit(k))
            header.addWidget(btn)
            self.buttons[key] = btn
        layout.addLayout(header)

        divider = QFrame(objectName="Divider")
        layout.addWidget(divider)

        self.stack = QStackedWidget()
        self.empty = StateView()
        self.pdf = PdfPagesView(renderer)
        self.pdf.pageChanged.connect(self._on_page_changed)
        self.rendered = MarkdownView()
        self.source = SourceView()
        self.state = StateView()
        self.state.actionRequested.connect(self._emit)
        for w in (self.empty, self.pdf, self.rendered, self.source, self.state):
            self.stack.addWidget(w)
        layout.addWidget(self.stack, 1)

        self.footer = QWidget()
        foot = QHBoxLayout(self.footer)
        foot.setContentsMargins(16, 8, 16, 10)
        foot.setSpacing(6)
        self.chips = {
            "pages": StatChip("pages"),
            "words": StatChip("type"),
            "images": StatChip("image"),
            "time": StatChip("clock"),
            "mode": StatChip("sparkles"),
        }
        for chip in self.chips.values():
            foot.addWidget(chip)
        foot.addStretch(1)
        self.out_label = QLabel(objectName="Faint")
        foot.addWidget(self.out_label)
        self._footer_divider = QFrame(objectName="Divider")
        layout.addWidget(self._footer_divider)
        layout.addWidget(self.footer)

        self.empty.show_state("尚未選擇檔案", "從左側佇列選擇一個 PDF，即可在這裡預覽原稿與轉換結果。", icon="eye")
        self.set_job(None)

    # ---- public API
    @property
    def job(self) -> Optional[Job]:
        return self._job

    def set_job(self, job: Optional[Job], prefer_result: bool = True) -> None:
        changed = (job is None) != (self._job is None) or (job is not None and self._job is not None and job.id != self._job.id)
        self._job = job
        if changed:
            self._loaded.clear()
            if job is not None:
                want = "rendered" if (job.status == Status.DONE and prefer_result) else "pdf"
                if self.tabs.value() == "source" and job.status == Status.DONE:
                    want = "source"
                self.tabs.setValue(want, animate=False)
        self._sync()

    def update_job(self, job: Job) -> None:
        if self._job is not None and job.id == self._job.id:
            self._job = job
            self._sync()

    def show_result_of(self, job: Job) -> None:
        """Called when the selected job just finished: jump to the rendered result."""
        if self._job is not None and job.id == self._job.id:
            self._loaded.clear()
            if self.tabs.value() != "source":
                self.tabs.setValue("rendered")
            self._sync()

    def current_tab(self) -> str:
        return self.tabs.value()

    def set_tab(self, key: str) -> None:
        self.tabs.setValue(key)

    def refresh_theme(self, *_):
        for v in (self.empty, self.state):
            v.refresh_theme()
        for chip in self.chips.values():
            chip.refresh_theme()
        self.source.refresh_theme()
        self.rendered.refresh_theme()
        self.pdf.viewport().update()
        for child in self.pdf.widget().findChildren(_PageWidget):
            child.update()

    # ---- internals
    def _emit(self, action: str) -> None:
        if self._job is not None and action:
            self.actionRequested.emit(action, self._job.id)

    def _on_tab(self, _key: str) -> None:
        self._sync()

    def _on_page_changed(self, cur: int, total: int) -> None:
        self._page_info = f"第 {cur} / {total} 頁"
        if self.tabs.value() == "pdf":
            self._update_subtitle()

    @staticmethod
    def _set_elided(label: QLabel, text: str, mode=Qt.TextElideMode.ElideMiddle) -> None:
        label.setProperty("fullText", text)
        label.setToolTip(text if text else "")
        fm = QFontMetrics(label.font())
        label.setText(fm.elidedText(text, mode, max(40, label.width())))

    def _update_subtitle(self) -> None:
        job = self._job
        if job is None:
            self._set_elided(self.subtitle, "")
            return
        tab = self.tabs.value()
        if tab == "pdf" and job.page_count:
            text = f"{self._page_info or f'共 {job.page_count} 頁'}　·　{human_size(job.size)}"
        elif job.result is not None and job.status == Status.DONE:
            text = str(job.result.output_path.parent)
        else:
            text = str(job.path.parent)
        self._set_elided(self.subtitle, text)

    def _sync(self) -> None:
        job = self._job
        done = job is not None and job.status == Status.DONE and job.result is not None
        for btn in self.buttons.values():
            btn.setEnabled(done)
        self.tabs.setEnabled(job is not None)

        if job is None:
            self._set_elided(self.title, "預覽")
            self._set_elided(self.subtitle, "")
            self.stack.setCurrentWidget(self.empty)
            self.pdf.clear()
            self._set_footer(None)
            return

        self._set_elided(self.title, job.name)
        tab = self.tabs.value()
        self._update_subtitle()

        if job.status == Status.LOCKED:
            self.stack.setCurrentWidget(self.state)
            self.state.show_state("此 PDF 受密碼保護", "輸入開啟密碼後即可預覽並轉換這份文件。", icon="lock", role="warning",
                                  button="輸入密碼", action="unlock", primary=True)
        elif tab == "pdf":
            if job.page_count:
                self.pdf.set_document(job.path, job.page_count, job.page_size)
                self.stack.setCurrentWidget(self.pdf)
            elif job.status == Status.FAILED and not job.probed:
                self.stack.setCurrentWidget(self.state)
                self.state.show_state("無法讀取此檔案", job.error, icon="alert", role="danger")
            else:
                self.stack.setCurrentWidget(self.state)
                self.state.show_state("正在讀取 PDF…", "", icon="file-text")
        elif done:
            md = job.result.markdown
            key = (job.id, id(md))
            view = self.rendered if tab == "rendered" else self.source
            if self._loaded.get(tab) != key:
                if tab == "rendered":
                    self.rendered.set_markdown(md, job.result.output_path.parent)
                else:
                    self.source.set_markdown(md)
                self._loaded[tab] = key
            self.stack.setCurrentWidget(view)
        else:
            self.stack.setCurrentWidget(self.state)
            self._show_job_state(job)
        self._set_footer(job.result if done else None)

    def _show_job_state(self, job: Job) -> None:
        s = job.status
        if s == Status.RUNNING:
            self.state.show_state("正在轉換", job.message or "準備中…", progress=job.progress)
        elif s == Status.QUEUED:
            self.state.show_state("排隊中", "前面的檔案轉換完成後就會輪到這份文件。", icon="clock")
        elif s == Status.FAILED:
            self.state.show_state("轉換失敗", job.error, icon="alert", role="danger", button="重試", action="retry", primary=True)
        elif s == Status.CANCELLED:
            self.state.show_state("轉換已取消", "可以隨時重新開始轉換這份文件。", icon="info", role="warning",
                                  button="重新轉換", action="convert", primary=True)
        else:
            self.state.show_state("尚未轉換", "調整右側的轉換設定後，按下「開始轉換」，結果會立刻顯示在這裡。",
                                  icon="markdown", button="只轉換這個檔案", action="convert", primary=True)

    def _set_footer(self, result) -> None:
        visible = result is not None
        self.footer.setVisible(visible)
        self._footer_divider.setVisible(visible)
        if not visible:
            return
        self.chips["pages"].set_text(f"{result.pages} 頁")
        self.chips["words"].set_text(f"{result.words:,} 字")
        self.chips["images"].set_text(f"{result.images} 張圖片")
        self.chips["time"].set_text(f"{result.elapsed:.1f} 秒")
        mode = "AI 版面分析" if result.mode == "layout" else "快速模式"
        self.chips["mode"].set_text(f"{mode} · OCR {result.ocr_pages} 頁" if result.ocr_pages else mode)
        self.out_label.setText(result.output_path.name)
        self.out_label.setToolTip(str(result.output_path))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for label in (self.title, self.subtitle):
            self._set_elided(label, label.property("fullText") or "")
