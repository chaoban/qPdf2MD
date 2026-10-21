"""Main window: wires the queue, renderer and panels into one workflow."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, COPYRIGHT, LICENSE_NAME, brand, icons, theme
from .engine import ConvertResult, EngineInfo, images_dir_for
from .jobs import ConversionQueue, Job, JobListModel, ProbeResult, RenderService, Status
from .theme import ThemeManager
from .widgets.controls import ThinProgress
from .widgets.dialogs import AboutDialog, PasswordDialog
from .widgets.feedback import DragOverlay, DropZone, ToastManager
from .widgets.header import THEME_META, HeaderBar
from .widgets.joblist import FilesPanel, styled_menu
from .widgets.preview import PreviewPanel
from .widgets.settings_panel import SettingsPanel

MAX_SCAN = 2000


def collect_pdfs(paths: Iterable[str | Path]) -> tuple[list[Path], bool]:
    """Expand files and folders (recursively) into a list of PDF paths."""
    found: list[Path] = []
    had_folder = False
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            had_folder = True
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                for f in sorted(files):
                    if f.lower().endswith(".pdf"):
                        found.append(Path(root) / f)
                        if len(found) >= MAX_SCAN:
                            return found, had_folder
        elif p.suffix.lower() == ".pdf" and p.is_file():
            found.append(p)
    return found, had_folder


def reveal_in_explorer(path: Path) -> None:
    if sys.platform == "win32":
        if path.exists():
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            os.startfile(str(path.parent))  # type: ignore[attr-defined]
    else:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


class MainWindow(QMainWindow):
    def __init__(self, theme_manager: ThemeManager, settings: QSettings):
        super().__init__()
        self.tm = theme_manager
        self.store = settings
        self._engine_info: Optional[EngineInfo] = None
        self._engine_error = ""
        self._batch_total = 0
        self._batch_done = 0
        self._last_output: Optional[Path] = None
        self._stopping = False

        self.setWindowTitle(f"{APP_NAME} — PDF 轉 Markdown")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(1120, 720)
        self.setAcceptDrops(True)

        self.model = JobListModel(self)
        self.renderer = RenderService(self)
        self.queue = ConversionQueue(self)

        root = QWidget(objectName="Root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.header = HeaderBar()
        v.addWidget(self.header)
        self.batch_bar = ThinProgress()
        v.addWidget(self.batch_bar)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_empty_page())
        workspace = QWidget(objectName="Workspace")
        wl = QHBoxLayout(workspace)
        wl.setContentsMargins(14, 8, 14, 14)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(12)
        self.splitter.setChildrenCollapsible(False)
        self.files = FilesPanel(self.model)
        self.files.setMinimumWidth(300)
        self.preview = PreviewPanel(self.renderer)
        self.preview.setMinimumWidth(440)
        self.options = SettingsPanel()
        self.options.setMinimumWidth(330)
        self.options.setMaximumWidth(460)
        for i, w in enumerate((self.files, self.preview, self.options)):
            self.splitter.addWidget(w)
            self.splitter.setStretchFactor(i, 1 if i == 1 else 0)
        self.splitter.setSizes([340, 760, 360])
        wl.addWidget(self.splitter)
        self.stack.addWidget(workspace)

        self.overlay = DragOverlay(root)
        self.toasts = ToastManager(root)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_options)

        self._wire()
        self._shortcuts()
        self._restore()
        self.set_engine_loading()
        self.refresh_theme(self.tm.palette)
        self._update_ui()

    # ------------------------------------------------------------------ construction
    def _build_empty_page(self) -> QWidget:
        page = QWidget(objectName="EmptyPage")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 20, 40, 36)
        outer.addStretch(2)
        title = QLabel("把 PDF 變成乾淨、結構化的 Markdown", objectName="HeroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)
        outer.addSpacing(8)
        sub = QLabel("AI 版面分析自動辨識標題、清單、表格與圖片，完整保留文件結構——適合筆記、技術文件與 AI 知識庫。",
                     objectName="HeroSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        outer.addWidget(sub)
        outer.addSpacing(28)
        self.dropzone = DropZone()
        self.dropzone.setFixedSize(700, 300)
        self.dropzone.clicked.connect(self.open_files_dialog)
        outer.addWidget(self.dropzone, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addSpacing(30)

        features = QHBoxLayout()
        features.setSpacing(14)
        features.addStretch(1)
        self._feature_icons: list[tuple[QLabel, str]] = []
        for icon_name, head, text in (
            ("sparkles", "AI 版面分析", "辨識標題層級與閱讀順序"),
            ("scan", "掃描文件 OCR", "辨識掃描頁的中英日文字"),
            ("pages", "表格與清單", "轉為標準 GFM 語法"),
            ("image", "圖片擷取", "另存檔案或內嵌 Base64"),
            ("zap", "批次轉換", "整個資料夾一次完成"),
        ):
            card = QFrame(objectName="Panel")
            card.setFixedWidth(166)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(4)
            ico = QLabel()
            self._feature_icons.append((ico, icon_name))
            cl.addWidget(ico)
            cl.addSpacing(4)
            cl.addWidget(QLabel(head, objectName="FieldLabel"))
            t = QLabel(text, objectName="Hint")
            t.setWordWrap(True)
            cl.addWidget(t)
            features.addWidget(card)
        features.addStretch(1)
        outer.addLayout(features)
        outer.addSpacing(22)
        keys = QLabel("Ctrl + O 開啟檔案　·　支援一次拖放多個 PDF 或整個資料夾", objectName="Faint")
        keys.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(keys)
        outer.addStretch(3)
        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addStretch(1)
        footer.addWidget(brand.Logo(14), 0, Qt.AlignmentFlag.AlignVCenter)
        footer.addWidget(QLabel(f"{COPYRIGHT}　·　依 {LICENSE_NAME} 授權發布　·　F1 關於與授權資訊", objectName="Faint"),
                         0, Qt.AlignmentFlag.AlignVCenter)
        footer.addStretch(1)
        outer.addLayout(footer)
        return page

    def _wire(self) -> None:
        self.files.addRequested.connect(self.open_files_dialog)
        self.files.clearDoneRequested.connect(self.clear_done)
        self.files.clearAllRequested.connect(self.clear_all)
        view = self.files.view
        view.selectionModel().currentChanged.connect(self._on_current_changed)
        view.removeRequested.connect(self.remove_job)
        view.activated_job.connect(self._on_activate)
        view.contextRequested.connect(self._on_context_menu)

        self.preview.actionRequested.connect(self._on_preview_action)
        self.options.startRequested.connect(lambda: self.start_conversion())
        self.options.stopRequested.connect(self.stop_conversion)
        self.options.optionsChanged.connect(self._save_timer.start)
        self.options.optionsChanged.connect(self._update_ui)

        self.header.themeClicked.connect(self._cycle_theme)
        self.header.aboutClicked.connect(self._show_about)

        self.queue.jobStarted.connect(self._on_job_started)
        self.queue.jobProgress.connect(self._on_job_progress)
        self.queue.jobFinished.connect(self._on_job_finished)
        self.queue.jobFailed.connect(self._on_job_failed)
        self.queue.jobCancelled.connect(self._on_job_cancelled)
        self.queue.batchFinished.connect(self._on_batch_finished)
        self.renderer.probed.connect(self._on_probed)
        self.tm.changed.connect(self.refresh_theme)

    def _shortcuts(self) -> None:
        def sc(keys, fn):
            for k in keys if isinstance(keys, (list, tuple)) else [keys]:
                QShortcut(QKeySequence(k), self, activated=fn)

        sc("Ctrl+O", self.open_files_dialog)
        sc(["Ctrl+Return", "Ctrl+Enter"], lambda: self.start_conversion() if not self.queue.running else None)
        sc("Esc", lambda: self.stop_conversion() if self.queue.running else None)
        sc("Ctrl+Shift+C", lambda: self._on_preview_action("copy", self.preview.job.id) if self.preview.job else None)
        sc("Ctrl+1", lambda: self.preview.set_tab("pdf"))
        sc("Ctrl+2", lambda: self.preview.set_tab("rendered"))
        sc("Ctrl+3", lambda: self.preview.set_tab("source"))
        sc("F1", self._show_about)

    # ------------------------------------------------------------------ settings
    def _restore(self) -> None:
        geo = self.store.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            w, h = min(1460, int(screen.width() * 0.9)), min(900, int(screen.height() * 0.9))
            self.resize(w, h)
            self.move(screen.center().x() - w // 2, screen.center().y() - h // 2)
        split = self.store.value("splitter")
        if split is not None:
            self.splitter.restoreState(split)
        try:
            self.options.load_state(json.loads(self.store.value("options", "{}") or "{}"))
        except (TypeError, ValueError):
            pass
        for le in self.findChildren(QLineEdit):
            le.setAcceptDrops(False)

    def _save_options(self) -> None:
        self.store.setValue("options", json.dumps(self.options.state(), ensure_ascii=False))

    def _save_all(self) -> None:
        self.store.setValue("geometry", self.saveGeometry())
        self.store.setValue("splitter", self.splitter.saveState())
        self.store.setValue("theme", self.tm.mode)
        self._save_options()
        self.store.sync()

    # ------------------------------------------------------------------ theme & engine
    def refresh_theme(self, p) -> None:
        icons.binder.refresh()
        self.header.set_theme_mode(self.tm.mode)
        self.dropzone.refresh_theme()
        for label, name in self._feature_icons:
            label.setPixmap(icons.pixmap(name, p.accent_hover if p.is_dark else p.accent, 22, self.devicePixelRatioF()))
        self.files.refresh_theme()
        self.preview.refresh_theme()
        self.options.refresh_theme()
        theme.apply_window_frame(self, p)
        for w in self.findChildren(QWidget):
            w.update()

    def _cycle_theme(self) -> None:
        mode = self.tm.cycle()
        self.store.setValue("theme", mode)
        self.toasts.show("info", f"已切換為「{THEME_META[mode][1]}」主題", duration=1800)

    def set_engine_loading(self) -> None:
        self.header.engine.set_state("warning", "引擎載入中", pulsing=True, tooltip="正在載入 PDF 解析與 AI 版面分析模型…")

    def set_engine_ready(self, info: EngineInfo) -> None:
        self._engine_info = info
        layout = "AI 版面分析可用" if info.layout_available else "AI 版面分析不可用，使用快速模式"
        ocr = "OCR 文字辨識可用（RapidOCR）" if info.ocr_available else "OCR 文字辨識不可用"
        self.header.engine.set_state("success", "引擎就緒", tooltip=f"pymupdf4llm {info.version}\n{layout}\n{ocr}")
        self.options.set_engine_info(info.layout_available, info.ocr_available)

    def set_engine_failed(self, message: str) -> None:
        self._engine_error = message
        self.header.engine.set_state("danger", "引擎錯誤", tooltip=message)
        self.toasts.show("error", f"轉換引擎載入失敗：{message}", duration=0)

    def _engine_text(self) -> str:
        if self._engine_info:
            enabled = [name for name, ok in (("AI 版面分析", self._engine_info.layout_available),
                                             ("OCR 文字辨識", self._engine_info.ocr_available)) if ok]
            return f"轉換引擎 pymupdf4llm {self._engine_info.version}" + (f"（{'、'.join(enabled)}已啟用）" if enabled else "")
        return self._engine_error or "轉換引擎載入中…"

    def _show_about(self) -> None:
        AboutDialog(self, self._engine_text()).exec()

    # ------------------------------------------------------------------ adding & removing
    def open_files_dialog(self) -> None:
        start = self.store.value("last_dir", str(Path.home() / "Documents"))
        files, _ = QFileDialog.getOpenFileNames(self, "選擇要轉換的 PDF 檔案", start, "PDF 文件 (*.pdf);;所有檔案 (*)")
        if files:
            self.store.setValue("last_dir", str(Path(files[0]).parent))
            self.add_paths(files)

    def add_paths(self, paths: Iterable[str | Path]) -> None:
        pdfs, had_folder = collect_pdfs(paths)
        if not pdfs:
            self.toasts.show("warning", "資料夾中沒有找到 PDF 檔案" if had_folder else "只支援 PDF 檔案")
            return
        added: list[Job] = []
        dup = 0
        for path in pdfs:
            if self.model.find_path(path):
                dup += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            job = Job(path=path, size=size)
            self.model.add(job)
            self.renderer.probe(job.id, path)
            added.append(job)
        if added:
            self._select(added[0].id)
        if len(added) > 1 or dup:
            msg = f"已加入 {len(added)} 個檔案" if added else "這些檔案已經在清單中"
            if added and dup:
                msg += f"，略過 {dup} 個重複的檔案"
            self.toasts.show("success" if added else "info", msg, duration=2600)
        elif len(added) == 1 and len(self.model.jobs) == 1:
            pass  # the first file: the screen change is feedback enough
        self._update_ui()

    def remove_job(self, job_id: int) -> None:
        job = self.model.get(job_id)
        if job is None or job.is_active:
            return
        row = self.model.row_of(job_id)
        was_selected = self.preview.job is not None and self.preview.job.id == job_id
        self.renderer.forget(job.path)
        self.files.view.delegate.forget(job_id)
        self.model.remove(job_id)
        if was_selected:
            jobs = self.model.jobs
            if jobs:
                self._select(jobs[min(row, len(jobs) - 1)].id)
            else:
                self.preview.set_job(None)
        self._update_ui()

    def clear_done(self) -> None:
        ids = [j.id for j in self.model.jobs if j.status == Status.DONE]
        for i in ids:
            self.remove_job(i)
        if ids:
            self.toasts.show("info", f"已清除 {len(ids)} 個已完成的檔案", duration=2200)

    def clear_all(self) -> None:
        for j in self.model.jobs:
            if not j.is_active:
                self.remove_job(j.id)

    def _select(self, job_id: int) -> None:
        row = self.model.row_of(job_id)
        if row >= 0:
            idx = self.model.index(row)
            self.files.view.setCurrentIndex(idx)
            self.files.view.scrollTo(idx)

    def _on_current_changed(self, current, _previous) -> None:
        job = current.data(JobListModel.JobRole) if current.isValid() else None
        self.preview.set_job(job)

    # ------------------------------------------------------------------ probing & passwords
    def _on_probed(self, job_id: int, result: ProbeResult) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        job.probed = True
        if result.ok and result.locked:
            job.encrypted = True
            if not job.is_active:
                job.status = Status.LOCKED
        elif result.ok:
            job.page_count = result.page_count
            job.page_size = result.page_size
            job.title = result.title
            job.thumbnail = result.thumbnail
            if job.status == Status.LOCKED:
                job.status = Status.PENDING
        else:
            job.error = result.error
            if not job.is_active:
                job.status = Status.FAILED
        self._refresh_job(job)
        self._update_ui()

    def unlock(self, job: Job) -> bool:
        import pymupdf

        def check(password: str) -> bool:
            try:
                with pymupdf.open(job.path) as doc:
                    return bool(doc.authenticate(password))
            except Exception:
                return False

        dlg = PasswordDialog(self, job.name, check)
        if dlg.exec():
            job.password = dlg.password()
            job.status = Status.PENDING
            job.error = ""
            self.renderer.probe(job.id, job.path, job.password)
            self._refresh_job(job)
            self._update_ui()
            return True
        return False

    # ------------------------------------------------------------------ conversion
    def start_conversion(self, only: Optional[set[int]] = None) -> None:
        if self.queue.running:
            return
        problem = self.options.validate()
        if problem:
            msg, widget = problem
            self.toasts.show("error", msg)
            widget.setFocus()
            return
        jobs = [j for j in self.model.jobs if only is None or j.id in only]
        todo = [j for j in jobs if j.status != Status.DONE] if only is None else jobs
        if only is None and not todo:
            todo = jobs  # everything is done: the button reads "re-convert all"
        if not todo:
            return
        for job in todo:
            if job.status == Status.LOCKED and not self.unlock(job):
                continue
        todo = [j for j in todo if j.status != Status.LOCKED and not (j.status == Status.FAILED and not j.page_count and j.probed and not j.encrypted)]
        if not todo:
            self.toasts.show("warning", "沒有可以轉換的檔案")
            return
        for job in todo:
            job.status = Status.QUEUED
            job.progress = 0.0
            job.message = ""
            job.error = ""
            self._refresh_job(job)
        self._batch_total = len(todo)
        self._batch_done = 0
        self._stopping = False
        self.queue.start([(j.id, str(j.path), j.password) for j in todo], self.options.options())
        self.options.set_running(True)
        self.batch_bar.set_active(True)
        self._update_ui()

    def stop_conversion(self) -> None:
        if not self.queue.running or self._stopping:
            return
        self._stopping = True
        for job_id in self.queue.cancel():
            job = self.model.get(job_id)
            if job:
                job.status = Status.CANCELLED
                self._refresh_job(job)
        self.options.start_btn.setText("  正在停止…")
        self.options.start_btn.setEnabled(False)

    def _refresh_job(self, job: Job) -> None:
        self.model.touch(job.id)
        self.preview.update_job(job)

    def _on_job_started(self, job_id: int) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        job.status = Status.RUNNING
        job.progress = 0.0
        job.message = "準備中…"
        if self.preview.job is None:
            self._select(job_id)
        self._refresh_job(job)
        self._update_ui()

    def _on_job_progress(self, job_id: int, fraction: float, text: str) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        job.progress = fraction
        job.message = text
        self._refresh_job(job)
        overall = (self._batch_done + fraction) / max(self._batch_total, 1)
        self.batch_bar.set_value(overall)
        self.setWindowTitle(f"{APP_NAME} — 轉換中 {round(overall * 100)}%")

    def _on_job_finished(self, job_id: int, result: ConvertResult) -> None:
        self._batch_done += 1
        self.batch_bar.set_value(self._batch_done / max(self._batch_total, 1))
        self._last_output = result.output_path
        job = self.model.get(job_id)
        if job is None:
            return
        job.status = Status.DONE
        job.result = result
        job.progress = 1.0
        self._refresh_job(job)
        self.preview.show_result_of(job)
        self._update_ui()

    def _on_job_failed(self, job_id: int, message: str, is_password: bool) -> None:
        self._batch_done += 1
        job = self.model.get(job_id)
        if job is None:
            return
        if is_password:
            job.status = Status.LOCKED
            job.password = None
        else:
            job.status = Status.FAILED
        job.error = message
        self._refresh_job(job)
        self._update_ui()

    def _on_job_cancelled(self, job_id: int) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        job.status = Status.CANCELLED
        job.progress = 0.0
        self._refresh_job(job)
        self._update_ui()

    def _on_batch_finished(self, done: int, failed: int, cancelled: int) -> None:
        self._stopping = False
        self.options.set_running(False)
        self.batch_bar.set_value(1.0)
        self.batch_bar.set_active(False)
        self.setWindowTitle(f"{APP_NAME} — PDF 轉 Markdown")
        self._update_ui()
        if not self.isActiveWindow():
            QApplication.alert(self)
        last = self._last_output
        if cancelled and not done:
            self.toasts.show("info", "已停止轉換")
        elif cancelled and last is not None:
            self.toasts.show("info", f"已停止轉換，完成的 {done} 個檔案已儲存", "開啟資料夾",
                             lambda p=last: reveal_in_explorer(p), duration=6000)
        elif failed and done:
            self.toasts.show("warning", f"完成 {done} 個檔案，{failed} 個轉換失敗", duration=6000)
        elif failed:
            self.toasts.show("error", "轉換失敗，請查看檔案佇列中的錯誤說明" if failed == 1 else f"{failed} 個檔案轉換失敗", duration=6000)
        elif done == 1 and last is not None:
            self.toasts.show("success", f"已儲存 {last.name}", "開啟檔案", lambda p=last: self._open_path(p), duration=6000)
        elif done and last is not None:
            msg = f"已完成 {done} 個檔案的轉換" + (f"（{cancelled} 個已取消）" if cancelled else "")
            self.toasts.show("success", msg, "開啟資料夾", lambda p=last: reveal_in_explorer(p), duration=6000)

    # ------------------------------------------------------------------ actions
    def _open_path(self, path: Path) -> None:
        if not path.exists():
            self.toasts.show("error", "找不到檔案，可能已被移動或刪除")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_activate(self, job_id: int) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        if job.status == Status.LOCKED:
            self.unlock(job)
        elif job.status == Status.DONE and job.result:
            self._open_path(job.result.output_path)

    def _on_preview_action(self, action: str, job_id: int) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        result = job.result
        if action == "copy" and result:
            QApplication.clipboard().setText(result.markdown)
            self.toasts.show("success", "已複製 Markdown 到剪貼簿", duration=2000)
        elif action == "open" and result:
            self._open_path(result.output_path)
        elif action == "reveal":
            reveal_in_explorer(result.output_path if result else job.path)
        elif action == "save_as" and result:
            self._save_as(result)
        elif action in ("convert", "retry"):
            self.start_conversion({job_id})
        elif action == "unlock":
            self.unlock(job)
        elif action == "open_pdf":
            self._open_path(job.path)
        elif action == "remove":
            self.remove_job(job_id)
        elif action in ("pdf", "rendered", "source"):
            self.preview.set_tab(action)

    def _save_as(self, result: ConvertResult) -> None:
        start = str(Path(self.store.value("last_save_dir", str(result.output_path.parent))) / result.output_path.name)
        target, _ = QFileDialog.getSaveFileName(self, "另存 Markdown", start, "Markdown (*.md);;所有檔案 (*)")
        if not target:
            return
        target_path = Path(target)
        if target_path.suffix.lower() not in (".md", ".markdown"):
            target_path = target_path.with_suffix(".md")
        try:
            target_path.write_text(result.markdown, encoding="utf-8", newline="\n")
            images = images_dir_for(result.output_path)
            if images.is_dir() and target_path.parent.resolve() != result.output_path.parent.resolve():
                shutil.copytree(images, target_path.parent / images.name, dirs_exist_ok=True)
        except OSError as exc:
            self.toasts.show("error", f"儲存失敗：{exc}")
            return
        self.store.setValue("last_save_dir", str(target_path.parent))
        self.toasts.show("success", f"已另存為 {target_path.name}", "顯示", lambda: reveal_in_explorer(target_path))

    def _on_context_menu(self, job_id: int, global_pos) -> None:
        job = self.model.get(job_id)
        if job is None:
            return
        menu = styled_menu(self)
        done = job.status == Status.DONE and job.result is not None

        def add(text, icon_name, action, enabled=True):
            act = menu.addAction(icons.themed(icon_name), text)
            act.setEnabled(enabled)
            act.triggered.connect(lambda: self._on_preview_action(action, job_id))

        if done:
            add("預覽 Markdown", "eye", "rendered")
            add("開啟 .md 檔案", "external", "open")
            add("複製 Markdown", "copy", "copy")
            add("在檔案總管中顯示", "folder", "reveal")
            menu.addSeparator()
        if job.status == Status.LOCKED:
            add("輸入密碼…", "lock", "unlock")
        else:
            add("重新轉換" if done else "轉換此檔案", "refresh" if done else "play", "convert", not self.queue.running)
        add("開啟原始 PDF", "file", "open_pdf")
        menu.addSeparator()
        add("從清單移除", "trash", "remove", not job.is_active)
        menu.exec(global_pos)

    # ------------------------------------------------------------------ ui state
    def _update_ui(self) -> None:
        jobs = self.model.jobs
        total = len(jobs)
        self.stack.setCurrentIndex(1 if total else 0)
        done = sum(1 for j in jobs if j.status == Status.DONE)
        pending = total - done
        if not self.queue.running:
            self.options.set_counts(pending, total, done)
        self.files.count.setText(str(total))
        if not total:
            step = 0
        elif self.queue.running:
            step = 2
        elif done:
            step = 3
        else:
            step = 1
        self.header.stepper.set_step(step)

    # ------------------------------------------------------------------ drag & drop
    @staticmethod
    def _drop_paths(mime) -> list[str]:
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile()]

    def dragEnterEvent(self, e):
        paths = self._drop_paths(e.mimeData())
        pdfs = [p for p in paths if p.lower().endswith(".pdf")]
        folders = any(Path(p).is_dir() for p in paths)
        if pdfs or folders:
            e.acceptProposedAction()
            if self.stack.currentIndex() == 0:
                self.dropzone.set_drag_active(True)
            else:
                self.overlay.present(len(pdfs), folders)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.overlay.dismiss()
        self.dropzone.set_drag_active(False)

    def dropEvent(self, e):
        self.overlay.dismiss()
        self.dropzone.set_drag_active(False)
        paths = self._drop_paths(e.mimeData())
        if paths:
            e.acceptProposedAction()
            self.activateWindow()
            QTimer.singleShot(0, lambda: self.add_paths(paths))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.centralWidget().rect())

    # ------------------------------------------------------------------ shutdown
    def closeEvent(self, e):
        if self.queue.running:
            box = QMessageBox(QMessageBox.Icon.Question, "轉換進行中", f"仍有檔案正在轉換，確定要結束 {APP_NAME} 嗎？", parent=self)
            leave = box.addButton("停止並結束", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("繼續轉換", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not leave:
                e.ignore()
                return
        self._save_all()
        self.hide()
        clean = self.queue.shutdown(6000)
        self.renderer.shutdown()
        e.accept()
        if not clean:
            os._exit(0)  # a page is stuck in the layout model; don't hang the user's desktop
