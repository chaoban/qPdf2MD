"""The file queue: card-style list items with thumbnail, status badge and progress."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QFrame,
)

from .. import icons, theme
from ..jobs import Job, JobListModel, Status, human_size

CARD_H = 86
GAP = 8

_BADGES = {
    Status.PENDING: ("待轉換", "text_muted", None),
    Status.QUEUED: ("排隊中", "text_muted", "clock"),
    Status.RUNNING: ("轉換中", "accent", None),
    Status.DONE: ("完成", "success", "check"),
    Status.FAILED: ("失敗", "danger", "alert"),
    Status.CANCELLED: ("已取消", "warning", None),
    Status.LOCKED: ("需要密碼", "warning", "lock"),
}


def styled_menu(parent=None) -> QMenu:
    menu = QMenu(parent)
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return menu


class JobDelegate(QStyledItemDelegate):
    removeClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbs: dict[int, tuple[int, QPixmap]] = {}
        self._name_font = theme.ui_font(10, QFont.Weight.DemiBold)
        self._meta_font = theme.ui_font(8.8)
        self._badge_font = theme.ui_font(8.3, QFont.Weight.Bold)

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), CARD_H + GAP)

    @staticmethod
    def _card_rect(rect: QRect) -> QRectF:
        return QRectF(rect).adjusted(10, GAP / 2, -10, -GAP / 2)

    @classmethod
    def close_rect(cls, rect: QRect) -> QRectF:
        card = cls._card_rect(rect)
        return QRectF(card.right() - 30, card.top() + 8, 22, 22)

    def _thumb(self, job: Job) -> QPixmap | None:
        if job.thumbnail is None:
            return None
        key = id(job.thumbnail)
        cached = self._thumbs.get(job.id)
        if cached is None or cached[0] != key:
            cached = (key, QPixmap.fromImage(job.thumbnail))
            self._thumbs[job.id] = cached
        return cached[1]

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        job: Job = index.data(JobListModel.JobRole)
        if job is None:
            return
        p = theme.current()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        card = self._card_rect(option.rect)
        path = QPainterPath()
        path.addRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        if selected:
            bg = p.color("accent", 0.14 if p.is_dark else 0.07)
            border = p.color("accent", 0.85)
        elif hover:
            bg, border = p.color("surface_hover"), p.color("border_strong")
        else:
            bg, border = p.color("surface_alt" if p.is_dark else "surface"), p.color("border")
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1.2 if selected else 1.0))
        painter.drawPath(path)

        # -- thumbnail
        thumb_box = QRectF(card.left() + 12, card.top() + 12, 46, card.height() - 24)
        tpath = QPainterPath()
        tpath.addRoundedRect(thumb_box, 5, 5)
        painter.fillPath(tpath, p.color("page"))
        pm = self._thumb(job)
        if pm is not None and not pm.isNull():
            painter.save()
            painter.setClipPath(tpath)
            scaled = QRectF(0, 0, pm.width(), pm.height())
            s = max(thumb_box.width() / scaled.width(), thumb_box.height() / scaled.height())
            w, h = scaled.width() * s, scaled.height() * s
            painter.drawPixmap(QRectF(thumb_box.left(), thumb_box.top(), w, h), pm, scaled)
            painter.restore()
        else:
            icon_name = "lock" if job.status == Status.LOCKED else "file-text"
            icons.paint(painter, icon_name, thumb_box.adjusted(12, 18, -12, -18), "#9AA1AE", 1.8)
        painter.setPen(QPen(p.color("border_strong" if not p.is_dark else "border"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(thumb_box, 5, 5)

        # -- texts
        x = thumb_box.right() + 14
        right = card.right() - (36 if hover and not job.is_active else 14)
        painter.setFont(self._name_font)
        painter.setPen(p.color("text"))
        name = QFontMetrics(self._name_font).elidedText(job.name, Qt.TextElideMode.ElideMiddle, int(right - x))
        painter.drawText(QRectF(x, card.top() + 11, right - x, 20), Qt.AlignmentFlag.AlignVCenter, name)

        painter.setFont(self._meta_font)
        painter.setPen(p.color("text_muted"))
        if job.status == Status.LOCKED and not job.page_count:
            meta = f"已加密　·　{human_size(job.size)}"
        elif job.page_count:
            meta = f"{job.page_count} 頁　·　{human_size(job.size)}"
        else:
            meta = f"讀取中…　·　{human_size(job.size)}"
        painter.drawText(QRectF(x, card.top() + 32, card.right() - x - 14, 18), Qt.AlignmentFlag.AlignVCenter, meta)

        # -- status badge + detail
        label, role, icon_name = _BADGES[job.status]
        if job.status == Status.RUNNING:
            label = f"轉換中 {round(job.progress * 100)}%"
        fm = QFontMetrics(self._badge_font)
        bw = fm.horizontalAdvance(label) + 18 + (15 if icon_name else 0)
        badge = QRectF(x, card.top() + 54, bw, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(p.color(role, 0.16 if p.is_dark else 0.11) if role != "text_muted" else p.color("surface_hover" if not p.is_dark else "border"))
        painter.drawRoundedRect(badge, 10, 10)
        bx = badge.left() + 9
        color = getattr(p, role)
        if job.status == Status.RUNNING:
            painter.setBrush(p.color("accent"))
            painter.drawEllipse(QPointF(bx + 3, badge.center().y()), 3, 3)
            bx += 10
            badge.setWidth(badge.width() + 10)
        elif icon_name:
            icons.paint(painter, icon_name, QRectF(bx - 1, badge.center().y() - 6, 12, 12), color, 2.4)
            bx += 15
        painter.setFont(self._badge_font)
        painter.setPen(p.color(role))
        painter.drawText(QRectF(bx, badge.top(), badge.right() - bx, badge.height()), Qt.AlignmentFlag.AlignVCenter, label)

        detail = self._detail(job)
        if detail:
            dx = badge.right() + 8
            painter.setFont(self._meta_font)
            painter.setPen(p.color("danger" if job.status == Status.FAILED else "text_faint"))
            text = QFontMetrics(self._meta_font).elidedText(detail, Qt.TextElideMode.ElideRight, int(card.right() - dx - 12))
            painter.drawText(QRectF(dx, badge.top(), card.right() - dx - 12, badge.height()), Qt.AlignmentFlag.AlignVCenter, text)

        # -- progress bar along the bottom edge of the card
        if job.status == Status.RUNNING:
            track = QRectF(card.left() + 12, card.bottom() - 5, card.width() - 24, 2.5)
            painter.setBrush(p.color("accent", 0.15))
            painter.drawRoundedRect(track, 1.25, 1.25)
            painter.setBrush(p.color("accent"))
            painter.drawRoundedRect(QRectF(track.left(), track.top(), max(track.height(), track.width() * job.progress), track.height()), 1.25, 1.25)

        # -- remove button on hover
        if hover and not job.is_active:
            cr = self.close_rect(option.rect)
            painter.setBrush(p.color("border" if p.is_dark else "surface_hover"))
            painter.drawEllipse(cr)
            icons.paint(painter, "x", cr.adjusted(6, 6, -6, -6), p.text_muted, 2.4)
        painter.restore()

    @staticmethod
    def _detail(job: Job) -> str:
        if job.status == Status.RUNNING:
            return job.message
        if job.status == Status.DONE and job.result:
            return f"→ {job.result.output_path.name}"
        if job.status == Status.FAILED:
            return job.error
        if job.status == Status.LOCKED:
            return "點兩下輸入密碼"
        return ""

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            job: Job = index.data(JobListModel.JobRole)
            if job and not job.is_active and self.close_rect(option.rect).contains(event.position()):
                self.removeClicked.emit(job.id)
                return True
        return super().editorEvent(event, model, option, index)

    def forget(self, job_id: int) -> None:
        self._thumbs.pop(job_id, None)


class JobListView(QListView):
    removeRequested = Signal(int)
    activated_job = Signal(int)
    contextRequested = Signal(int, object)

    def __init__(self, model: JobListModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.delegate = JobDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.delegate.removeClicked.connect(self.removeRequested)
        self.doubleClicked.connect(self._on_double)
        self.customContextMenuRequested.connect(self._on_context)

    def _job_at(self, index) -> Job | None:
        return index.data(JobListModel.JobRole) if index.isValid() else None

    def _on_double(self, index):
        job = self._job_at(index)
        if job:
            self.activated_job.emit(job.id)

    def _on_context(self, pos):
        job = self._job_at(self.indexAt(pos))
        if job:
            self.setCurrentIndex(self.indexAt(pos))
            self.contextRequested.emit(job.id, self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete:
            job = self._job_at(self.currentIndex())
            if job and not job.is_active:
                self.removeRequested.emit(job.id)
                return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            job = self._job_at(self.currentIndex())
            if job:
                self.activated_job.emit(job.id)
                return
        super().keyPressEvent(e)


class FilesPanel(QFrame):
    addRequested = Signal()
    clearDoneRequested = Signal()
    clearAllRequested = Signal()

    def __init__(self, model: JobListModel, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(18, 0, 12, 0)
        header.setSpacing(8)
        header.addWidget(QLabel("檔案佇列", objectName="PanelTitle"))
        self.count = QLabel("0", objectName="CountBadge")
        header.addWidget(self.count)
        header.addStretch(1)
        self.add_btn = QToolButton()
        self.add_btn.setToolTip("加入 PDF 檔案（Ctrl+O）")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icons.binder.bind(self.add_btn, "plus")
        self.add_btn.clicked.connect(self.addRequested)
        header.addWidget(self.add_btn)
        self.more_btn = QToolButton()
        self.more_btn.setToolTip("更多動作")
        self.more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        icons.binder.bind(self.more_btn, "more")
        menu = styled_menu(self)
        self.act_clear_done = menu.addAction("清除已完成的檔案")
        self.act_clear_done.triggered.connect(self.clearDoneRequested)
        self.act_clear_all = menu.addAction("移除全部檔案")
        self.act_clear_all.triggered.connect(self.clearAllRequested)
        self.more_btn.setMenu(menu)
        header.addWidget(self.more_btn)
        layout.addLayout(header)

        self.view = JobListView(model)
        layout.addWidget(self.view, 1)

        hint = QLabel("拖曳 PDF 或資料夾到視窗任意處即可加入", objectName="Faint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def refresh_theme(self, *_):
        self.act_clear_done.setIcon(icons.themed("broom"))
        self.act_clear_all.setIcon(icons.themed("trash"))
        self.view.viewport().update()
