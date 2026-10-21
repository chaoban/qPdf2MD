"""Job model plus the background services: conversion queue and PDF page rendering."""

from __future__ import annotations

import itertools
import threading
import time
import traceback
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    QThread,
    QThreadPool,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QImage

from .engine import (
    Cancelled,
    ConversionError,
    ConvertOptions,
    ConvertResult,
    PasswordRequired,
    convert_pdf,
)


class Status(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOCKED = "locked"


_ids = itertools.count(1)


@dataclass(eq=False)
class Job:
    path: Path
    id: int = field(default_factory=lambda: next(_ids))
    size: int = 0
    page_count: int = 0
    page_size: tuple[float, float] = (595.0, 842.0)
    title: str = ""
    thumbnail: Optional[QImage] = None
    encrypted: bool = False
    password: Optional[str] = None
    probed: bool = False
    status: Status = Status.PENDING
    progress: float = 0.0
    message: str = ""
    result: Optional[ConvertResult] = None
    error: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_active(self) -> bool:
        return self.status in (Status.QUEUED, Status.RUNNING)


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


# --------------------------------------------------------------------------- list model

class JobListModel(QAbstractListModel):
    JobRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[Job] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._jobs)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._jobs)):
            return None
        job = self._jobs[index.row()]
        if role == self.JobRole:
            return job
        if role == Qt.ItemDataRole.DisplayRole:
            return job.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(job.path)
        return None

    # ---- helpers
    @property
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def add(self, job: Job) -> int:
        row = len(self._jobs)
        self.beginInsertRows(QModelIndex(), row, row)
        self._jobs.append(job)
        self.endInsertRows()
        return row

    def remove(self, job_id: int) -> None:
        row = self.row_of(job_id)
        if row >= 0:
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._jobs[row]
            self.endRemoveRows()

    def get(self, job_id: int) -> Optional[Job]:
        return next((j for j in self._jobs if j.id == job_id), None)

    def row_of(self, job_id: int) -> int:
        return next((i for i, j in enumerate(self._jobs) if j.id == job_id), -1)

    def find_path(self, path: Path) -> Optional[Job]:
        key = _path_key(path)
        return next((j for j in self._jobs if _path_key(j.path) == key), None)

    def touch(self, job_id: int) -> None:
        row = self.row_of(job_id)
        if row >= 0:
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)


def _path_key(path: Path) -> str:
    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path).casefold()


# --------------------------------------------------------------------------- conversion queue

class _ConvertWorker(QObject):
    progress = Signal(int, float, str)
    finished = Signal(int, object)
    failed = Signal(int, str, bool)
    cancelled = Signal(int)

    def __init__(self, cancel_event: threading.Event):
        super().__init__()
        self._cancel = cancel_event

    @Slot(int, str, object, object)
    def run(self, job_id: int, path: str, options: ConvertOptions, password) -> None:
        last = [0.0]

        def on_progress(fraction: float, text: str) -> None:
            now = time.monotonic()
            if now - last[0] >= 0.05 or fraction >= 1.0:  # keep the UI thread unflooded
                last[0] = now
                self.progress.emit(job_id, fraction, text)

        try:
            result = convert_pdf(path, options, password=password, progress=on_progress, cancel_event=self._cancel)
        except Cancelled:
            self.cancelled.emit(job_id)
        except PasswordRequired as exc:
            self.failed.emit(job_id, str(exc), True)
        except ConversionError as exc:
            self.failed.emit(job_id, str(exc), False)
        except PermissionError as exc:
            self.failed.emit(job_id, f"沒有寫入權限：{exc.filename or exc}", False)
        except OSError as exc:
            self.failed.emit(job_id, f"檔案存取失敗：{exc}", False)
        except Exception as exc:  # unexpected engine failure: keep the app alive
            traceback.print_exc()
            self.failed.emit(job_id, f"轉換時發生錯誤：{type(exc).__name__}: {exc}", False)
        else:
            self.finished.emit(job_id, result)


class ConversionQueue(QObject):
    """Runs conversions one at a time on a dedicated thread."""

    jobStarted = Signal(int)
    jobProgress = Signal(int, float, str)
    jobFinished = Signal(int, object)
    jobFailed = Signal(int, str, bool)
    jobCancelled = Signal(int)
    batchFinished = Signal(int, int, int)  # done, failed, cancelled
    _dispatch = Signal(int, str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = threading.Event()
        self._thread = QThread(self)
        self._thread.setObjectName("ConversionThread")
        self._worker = _ConvertWorker(self._cancel)
        self._worker.moveToThread(self._thread)
        self._dispatch.connect(self._worker.run)
        self._worker.progress.connect(self.jobProgress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._thread.start()

        self._pending: deque[tuple[int, str, Optional[str]]] = deque()
        self._options: Optional[ConvertOptions] = None
        self._current: Optional[int] = None
        self._stats = [0, 0, 0]

    @property
    def running(self) -> bool:
        return self._current is not None

    @property
    def current(self) -> Optional[int]:
        return self._current

    def start(self, items: list[tuple[int, str, Optional[str]]], options: ConvertOptions) -> None:
        if self.running or not items:
            return
        self._cancel.clear()
        self._options = options
        self._pending = deque(items)
        self._stats = [0, 0, 0]
        self._next()

    def remove_pending(self, job_id: int) -> None:
        self._pending = deque(item for item in self._pending if item[0] != job_id)

    def cancel(self) -> list[int]:
        """Stop the running job and drop the rest. Returns ids that never started."""
        dropped = [item[0] for item in self._pending]
        self._pending.clear()
        self._stats[2] += len(dropped)
        if self._current is not None:
            self._cancel.set()
        return dropped

    def shutdown(self, timeout_ms: int = 4000) -> bool:
        self.cancel()
        self._thread.quit()
        return self._thread.wait(timeout_ms)

    def _next(self) -> None:
        if not self._pending:
            self._current = None
            done, failed, cancelled = self._stats
            self.batchFinished.emit(done, failed, cancelled)
            return
        job_id, path, password = self._pending.popleft()
        self._current = job_id
        self.jobStarted.emit(job_id)
        self._dispatch.emit(job_id, path, self._options, password)

    def _on_finished(self, job_id: int, result) -> None:
        self._stats[0] += 1
        self.jobFinished.emit(job_id, result)
        self._next()

    def _on_failed(self, job_id: int, message: str, is_password: bool) -> None:
        self._stats[1] += 1
        self.jobFailed.emit(job_id, message, is_password)
        self._next()

    def _on_cancelled(self, job_id: int) -> None:
        self._stats[2] += 1
        self.jobCancelled.emit(job_id)
        self._cancel.clear()
        self._next()


# --------------------------------------------------------------------------- rendering service

@dataclass
class ProbeResult:
    ok: bool
    page_count: int = 0
    page_size: tuple[float, float] = (595.0, 842.0)
    title: str = ""
    locked: bool = False
    thumbnail: Optional[QImage] = None
    error: str = ""


def _to_qimage(pix) -> QImage:
    fmt = QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


class _RenderSignals(QObject):
    probed = Signal(int, object)
    rendered = Signal(str, int, int, QImage)


class RenderService(QObject):
    """Opens PDFs and rasterises pages on a single background thread.

    PyMuPDF documents are not thread-safe, so everything here runs on one pooled
    thread that also owns a small cache of open documents.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._pool.setExpiryTimeout(-1)
        self._signals = _RenderSignals()
        self.probed = self._signals.probed
        self.rendered = self._signals.rendered
        self._docs: OrderedDict[str, object] = OrderedDict()
        self._passwords: dict[str, str] = {}
        self._queued: set[tuple] = set()
        self.generation = 0
        # (path, page) pairs the preview still wants; stale scroll requests are skipped
        self.wanted: Optional[set[tuple[str, int]]] = None

    def probe(self, job_id: int, path: Path, password: Optional[str] = None) -> None:
        key = str(path)
        if password:
            self._passwords[key] = password
            self._docs.pop(key, None)  # reopen with the password next time
        self._pool.start(lambda: self._do_probe(job_id, key))

    def render(self, path: Path, page: int, width_px: int, generation: int) -> None:
        req = (str(path), page, width_px, generation)
        if req in self._queued:
            return
        self._queued.add(req)
        self._pool.start(lambda: self._do_render(*req))

    def forget(self, path: Path) -> None:
        key = str(path)
        self._passwords.pop(key, None)
        self._pool.start(lambda: self._close(key))

    def shutdown(self) -> None:
        self.generation += 1
        self._pool.clear()
        self._pool.waitForDone(3000)

    # ---- worker-thread side
    def _open(self, key: str):
        import pymupdf

        doc = self._docs.get(key)
        if doc is not None:
            self._docs.move_to_end(key)
            return doc
        doc = pymupdf.open(key)
        if doc.needs_pass and key in self._passwords:
            doc.authenticate(self._passwords[key])
        self._docs[key] = doc
        while len(self._docs) > 4:
            _, old = self._docs.popitem(last=False)
            old.close()
        return doc

    def _close(self, key: str) -> None:
        doc = self._docs.pop(key, None)
        if doc is not None:
            doc.close()

    def _do_probe(self, job_id: int, key: str) -> None:
        import pymupdf

        try:
            doc = self._open(key)
            if doc.is_encrypted:  # needs_pass stays true even after authenticate()
                self.probed.emit(job_id, ProbeResult(ok=True, locked=True))
                return
            if doc.page_count == 0:
                self.probed.emit(job_id, ProbeResult(ok=False, error="這份 PDF 沒有任何頁面"))
                return
            page = doc.load_page(0)
            rect = page.rect
            zoom = 160 / max(rect.width, 1)
            thumb = _to_qimage(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False))
            title = ((doc.metadata or {}).get("title") or "").strip()
            self.probed.emit(
                job_id,
                ProbeResult(ok=True, page_count=doc.page_count, page_size=(rect.width, rect.height), title=title, thumbnail=thumb),
            )
        except Exception as exc:
            self._docs.pop(key, None)
            self.probed.emit(job_id, ProbeResult(ok=False, error=f"無法讀取 PDF：{exc}"))

    def _do_render(self, key: str, page_no: int, width_px: int, generation: int) -> None:
        import pymupdf

        self._queued.discard((key, page_no, width_px, generation))
        if generation != self.generation:
            return  # the preview moved on to another document
        wanted = self.wanted
        if wanted is not None and (key, page_no) not in wanted:
            return  # scrolled out of view before we got to it
        try:
            doc = self._open(key)
            if doc.is_encrypted or page_no >= doc.page_count:
                return
            page = doc.load_page(page_no)
            zoom = width_px / max(page.rect.width, 1)
            image = _to_qimage(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False))
            self.rendered.emit(key, page_no, generation, image)
        except Exception:
            traceback.print_exc()
