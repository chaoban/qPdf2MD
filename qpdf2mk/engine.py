"""PDF → Markdown conversion engine.

Qt-free on purpose: it can be driven from the GUI worker thread, a CLI or tests.
Two strategies are offered:

* ``layout`` – pymupdf4llm's AI layout analysis (GNN). Best structure detection:
  headings, lists, tables, reading order, page headers/footers.
* ``fast``   – font-size heuristics. Much quicker, good for plain text documents.

Both can OCR scanned pages first (RapidOCR / PP-OCR models on onnxruntime): the
recognised lines are written into the in-memory page as real text, then extracted
like any other text.
"""

from __future__ import annotations

import base64
import datetime as _dt
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

from .tidy import count_words, tidy_markdown

ProgressFn = Callable[[float, str], None]


class ConversionError(Exception):
    """A conversion failure with a message that is safe to show to the user."""


class PasswordRequired(ConversionError):
    def __init__(self, wrong: bool = False):
        super().__init__("密碼錯誤，請重新輸入" if wrong else "此 PDF 受密碼保護")
        self.wrong = wrong


class Cancelled(Exception):
    """Raised inside the engine when the caller asked to stop."""


@dataclass
class ConvertOptions:
    mode: str = "layout"            # "layout" | "fast"
    ocr: str = "auto"               # "auto" (pages without usable text) | "always" | "off"
    page_range: str = ""            # "" = every page, e.g. "1-3, 7, 10-"
    images: str = "folder"          # "none" | "folder" | "embed"
    image_format: str = "png"       # "png" | "jpg"
    image_dpi: int = 150
    strip_headers_footers: bool = True
    tidy: bool = True
    page_markers: bool = False
    front_matter: bool = False
    output_dir: str = ""            # "" = next to the PDF
    overwrite: bool = False


@dataclass
class ConvertResult:
    source: Path
    output_path: Path
    markdown: str
    pages: int
    images: int
    words: int
    elapsed: float
    title: str
    mode: str
    ocr_pages: int = 0


@dataclass
class EngineInfo:
    version: str
    layout_available: bool
    ocr_available: bool = False


# --------------------------------------------------------------------------- engine loading

_engine_lock = threading.Lock()
_engine: Optional[SimpleNamespace] = None
_local = threading.local()


def load_engine() -> EngineInfo:
    """Import the (heavy) extraction stack once; safe to call from any thread."""
    global _engine
    with _engine_lock:
        if _engine is None:
            import pymupdf4llm
            from pymupdf4llm.helpers import document_layout, pymupdf_rag

            # pymupdf4llm iterates pages through a module-level ProgressBar; routing it
            # through our tracker gives per-page progress and a cancellation point.
            document_layout.ProgressBar = _progress_bar
            ocr = _load_ocr()
            _engine = SimpleNamespace(
                layout=document_layout,
                rag=pymupdf_rag,
                ocr=ocr,
                info=EngineInfo(
                    version=getattr(pymupdf4llm, "__version__", "?"),
                    layout_available=bool(getattr(pymupdf4llm, "_use_layout", False)),
                    ocr_available=ocr is not None,
                ),
            )
        return _engine.info


def _load_ocr() -> Optional[Callable]:
    """pymupdf4llm's RapidOCR page callback, or None when RapidOCR is not installed."""
    try:
        from pymupdf4llm.ocr import rapidocr_api
    except Exception:
        return None
    return rapidocr_api.exec_ocr if callable(rapidocr_api.full_ocr) else None


OCR_DPI = 200  # page rendering resolution handed to the OCR engine


def _ocr_mode(options: ConvertOptions):
    from pymupdf4llm.ocr import OCRMode

    if _engine.ocr is None:
        return OCRMode.NEVER
    # auto: only pages the decision model flags (scans, broken text), keeping an existing OCR layer;
    # always: every page that has images or drawings, replacing an existing OCR layer.
    return {"auto": OCRMode.SELECT_KEEP_OLD, "always": OCRMode.FORCE_DROP_OLD}.get(options.ocr, OCRMode.NEVER)


def _progress_bar(items, *args, **kwargs):
    tracker = getattr(_local, "tracker", None)
    return tracker.wrap(items) if tracker is not None else items


class _Tracker:
    # (start, end, label) of each pymupdf4llm phase on the overall 0..1 scale
    PHASES = ((0.03, 0.90, "正在分析第 {i} / {n} 頁"), (0.90, 0.95, "正在產生 Markdown {i} / {n}"))

    def __init__(self, progress: Optional[ProgressFn], cancel: Optional[threading.Event]):
        self._progress = progress
        self._cancel = cancel
        self.phase = 0
        self.fraction = 0.0
        self.ocr_pages = 0

    def check(self) -> None:
        if self._cancel is not None and self._cancel.is_set():
            raise Cancelled()

    def emit(self, fraction: float, text: str) -> None:
        self.fraction = min(max(fraction, 0.0), 1.0)
        if self._progress is not None:
            self._progress(self.fraction, text)

    def ocr_callback(self, exec_ocr: Callable) -> Callable:
        """Wrap the OCR page callback with a cancellation point, a status line and a page count."""

        def run(page, dpi=OCR_DPI, language=None, keep_ocr_text=False):
            self.check()
            self.emit(self.fraction, f"正在辨識第 {page.number + 1} 頁的文字（OCR）")
            exec_ocr(page, dpi=dpi, language=language, keep_ocr_text=keep_ocr_text)
            self.ocr_pages += 1

        return run

    def wrap(self, items):
        start, end, label = self.PHASES[min(self.phase, len(self.PHASES) - 1)]
        items = list(items)
        n = len(items) or 1
        for i, item in enumerate(items):
            self.check()
            self.emit(start + (end - start) * i / n, label.format(i=i + 1, n=n))
            yield item
        self.emit(end, label.format(i=n, n=n))


# --------------------------------------------------------------------------- helpers

_RANGE_SEP = re.compile(r"[,，、;；\s]+")
_RANGE_TOKEN = re.compile(r"(\d*)-(\d*)")


def parse_page_range(spec: str, page_count: Optional[int]) -> list[int]:
    """Parse "1-3, 5, 9-" into sorted 0-based page indices.

    With ``page_count=None`` only the syntax is validated (used for live UI feedback).
    Raises ValueError with a user-facing message.
    """
    spec = re.sub(r"\s*[-~–—至到]\s*", "-", (spec or "").strip())
    if not spec:
        return list(range(page_count or 0))
    limit = page_count if page_count is not None else 10**9
    pages: set[int] = set()
    for token in _RANGE_SEP.split(spec):
        if not token:
            continue
        m = _RANGE_TOKEN.fullmatch(token)
        if m:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else limit
        elif token.isdigit():
            a = b = int(token)
        else:
            raise ValueError(f"無法辨識「{token}」，請使用像 1-3, 5, 8- 的格式")
        if a > b:
            a, b = b, a
        if a < 1:
            raise ValueError("頁碼從 1 開始")
        if a > limit:
            raise ValueError(f"第 {a} 頁超出範圍（此文件共 {limit} 頁）")
        pages.update(range(a - 1, min(b, limit)))
    if not pages:
        raise ValueError("頁面範圍是空的")
    return sorted(pages)


def resolve_output_path(source: Path, options: ConvertOptions) -> Path:
    folder = Path(options.output_dir) if options.output_dir else source.parent
    target = folder / f"{source.stem}.md"
    if options.overwrite or not target.exists():
        return target
    n = 1
    while True:
        candidate = folder / f"{source.stem} ({n}).md"
        if not candidate.exists():
            return candidate
        n += 1


def images_dir_for(md_path: Path) -> Path:
    return md_path.with_name(f"{md_path.stem}_images")


_DATA_IMAGE = re.compile(r"!\[([^\]]*)\]\(data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)\)")
_FIRST_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)


def _md_link_target(path: str) -> str:
    """CommonMark-safe link destination (angle brackets when it contains spaces etc.)."""
    return f"<{path}>" if re.search(r"[\s()<>]", path) else path


def _export_images(text: str, page_no: int, md_path: Path) -> tuple[str, int]:
    """Write embedded base64 images of one page into <stem>_images/ and link them relatively."""
    folder = images_dir_for(md_path)
    count = 0

    def replace(m: re.Match) -> str:
        nonlocal count
        count += 1
        ext = m.group(2).lower().replace("jpeg", "jpg")
        name = f"p{page_no:03d}-{count:02d}.{ext}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(base64.b64decode(m.group(3)))
        alt = m.group(1).strip() or f"第 {page_no} 頁圖片 {count}"
        return f"![{alt}]({_md_link_target(f'{folder.name}/{name}')})"

    return _DATA_IMAGE.sub(replace, text), count


def _yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --------------------------------------------------------------------------- conversion

def convert_pdf(
    source: str | os.PathLike,
    options: ConvertOptions,
    *,
    password: Optional[str] = None,
    progress: Optional[ProgressFn] = None,
    cancel_event: Optional[threading.Event] = None,
) -> ConvertResult:
    """Convert one PDF and write the Markdown file. Returns details for the UI."""
    import pymupdf

    started = time.perf_counter()
    source = Path(source)
    tracker = _Tracker(progress, cancel_event)
    tracker.emit(0.0, "正在載入轉換引擎")
    info = load_engine()
    tracker.check()
    tracker.emit(0.01, "正在開啟文件")

    if not source.is_file():
        raise ConversionError("找不到檔案，可能已被移動或刪除")
    try:
        doc = pymupdf.open(source)
    except Exception as exc:  # corrupt / not a PDF
        raise ConversionError(f"無法開啟 PDF：{exc}") from exc

    try:
        if doc.needs_pass:
            if not password:
                raise PasswordRequired()
            if not doc.authenticate(password):
                raise PasswordRequired(wrong=True)
        if doc.page_count == 0:
            raise ConversionError("這份 PDF 沒有任何頁面")
        try:
            pages = parse_page_range(options.page_range, doc.page_count)
        except ValueError as exc:
            raise ConversionError(str(exc)) from exc

        mode = "layout" if options.mode == "layout" and info.layout_available else "fast"
        with_images = options.images != "none"
        if mode == "layout":
            chunks = _convert_layout(doc, pages, options, with_images, tracker)
        else:
            chunks = _convert_fast(doc, pages, options, with_images, tracker)
        metadata = dict(doc.metadata or {})
    finally:
        doc.close()

    tracker.check()
    tracker.emit(0.96, "正在整理並寫入檔案")
    output_path = resolve_output_path(source, options)

    parts: list[str] = []
    image_count = 0
    for page_no, text in chunks:
        if options.images == "folder":
            text, n = _export_images(text, page_no, output_path)
            image_count += n
        elif options.images == "embed":
            image_count += len(_DATA_IMAGE.findall(text))
        if options.page_markers:
            text = f"<!-- page {page_no} -->\n\n{text}"
        parts.append(text.strip("\n"))
    markdown = "\n\n".join(p for p in parts if p.strip())
    if options.tidy:
        markdown = tidy_markdown(markdown)
    elif not markdown.endswith("\n"):
        markdown += "\n"

    heading = _FIRST_HEADING.search(markdown)
    title = (metadata.get("title") or "").strip() or (heading.group(1).strip("* ") if heading else "") or source.stem

    if options.front_matter:
        fm = ["---", f"title: {_yaml_str(title)}"]
        if (metadata.get("author") or "").strip():
            fm.append(f"author: {_yaml_str(metadata['author'].strip())}")
        fm += [
            f"source: {_yaml_str(source.name)}",
            f"pages: {len(pages)}",
            f"converted: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "---",
            "",
        ]
        markdown = "\n".join(fm) + "\n" + markdown

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_name(output_path.name + ".part")
    tmp.write_text(markdown, encoding="utf-8", newline="\n")
    os.replace(tmp, output_path)
    tracker.emit(1.0, "完成")

    return ConvertResult(
        source=source,
        output_path=output_path,
        markdown=markdown,
        pages=len(pages),
        images=image_count,
        words=count_words(markdown),
        elapsed=time.perf_counter() - started,
        title=title,
        mode=mode,
        ocr_pages=tracker.ocr_pages,
    )


def _convert_layout(doc, pages, options, with_images, tracker) -> list[tuple[int, str]]:
    layout = _engine.layout
    keep_margins = not options.strip_headers_footers
    ocr_mode = _ocr_mode(options)
    _local.tracker = tracker
    try:
        tracker.phase = 0
        tracker.emit(0.03, "正在進行 AI 版面分析")
        parsed = layout.parse_document(
            doc,
            image_dpi=options.image_dpi,
            image_format=options.image_format,
            pages=pages,
            show_progress=True,
            embed_images=with_images,
            write_images=False,
            force_text=True,
            use_ocr=ocr_mode,
            ocr_function=tracker.ocr_callback(_engine.ocr) if ocr_mode else None,
            ocr_dpi=OCR_DPI,
        )
        tracker.check()
        tracker.phase = 1
        chunks = parsed.to_markdown(
            header=keep_margins,
            footer=keep_margins,
            embed_images=with_images,
            show_progress=True,
            page_chunks=True,
        )
    finally:
        _local.tracker = None
    return [(int(c["metadata"]["page_number"]), c["text"] or "") for c in chunks]


def _convert_fast(doc, pages, options, with_images, tracker) -> list[tuple[int, str]]:
    import pymupdf

    rag = _engine.rag
    # Importing pymupdf4llm activates the ONNX layout model globally, which would make
    # the heuristic path just as slow. Switch it off for the duration of this run.
    saved_layout = pymupdf._get_layout
    pymupdf._get_layout = None
    try:
        n = len(pages)
        start = 0.05
        ocr_mode = _ocr_mode(options)
        scans: set[int] = set()  # OCR'd pages whose picture is the scan itself
        if ocr_mode:
            # OCR first, so that header detection below also sees the recognised text.
            from pymupdf4llm.helpers.document_layout import make_ocr_decision

            run_ocr = tracker.ocr_callback(_engine.ocr)
            start = 0.60
            for i, pno in enumerate(pages):
                tracker.check()
                tracker.emit(0.03 + 0.57 * i / n, f"正在檢查第 {i + 1} / {n} 頁是否需要 OCR")
                page = doc[pno]
                if make_ocr_decision(page, ocr_mode)[0]:
                    page.remove_rotation()
                    run_ocr(page)
                    if _is_scan(page):
                        scans.add(pno)
        tracker.emit(start - 0.02, "正在分析字型結構")
        headers = rag.IdentifyHeaders(doc, pages=pages)
        if tracker.ocr_pages:
            # OCR text is sized by its line box, which wobbles from line to line;
            # only clearly larger lines should become headings.
            headers = rag.IdentifyHeaders(doc, pages=pages, body_limit=headers.body_limit * 1.25)
        chunks: list[tuple[int, str]] = []
        for i, pno in enumerate(pages):
            tracker.check()
            tracker.emit(start + (0.95 - start) * i / n, f"正在轉換第 {i + 1} / {n} 頁")
            page_images = with_images and pno not in scans  # the text already came out of the scan
            text = rag.to_markdown(
                doc,
                pages=[pno],
                hdr_info=headers,
                embed_images=page_images,
                ignore_images=not page_images,
                image_format=options.image_format,
                dpi=options.image_dpi,
                force_text=True,
                show_progress=False,
            )
            if options.strip_headers_footers:
                text = _strip_page_numbers(text, pno + 1)
            chunks.append((pno + 1, text))
        return chunks
    finally:
        pymupdf._get_layout = saved_layout


def _is_scan(page) -> bool:
    """True when a single image covers most of the page, i.e. the page is a scanned picture."""
    import pymupdf

    area = abs(page.rect)
    return any(abs(pymupdf.Rect(info["bbox"]) & page.rect) >= 0.8 * area for info in page.get_image_info())


def _strip_page_numbers(text: str, page_no: int) -> str:
    """Heuristic mode has no header/footer detection: drop lines that are just this page's number."""
    n = str(page_no)
    pattern = re.compile(
        rf"^\s*(?:(?:page|p\.?|頁)\s*{n}(?:\s*(?:/|of|／)\s*\d+)?|{n}\s*(?:/|of|／)\s*\d+|第\s*{n}\s*頁(?:\s*[/／,，]\s*共\s*\d+\s*頁)?|[-–—]?\s*{n}\s*[-–—]?)\s*$",
        re.I,
    )
    return "\n".join(line for line in text.split("\n") if not pattern.match(line))
