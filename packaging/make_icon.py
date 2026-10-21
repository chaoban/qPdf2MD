"""Render qpdf2mk.icons.app_icon() into a multi-size Windows .ico file.

    python packaging/make_icon.py <output.ico>

Each size is rendered from the SVG at that size (not scaled down from 256 px) and
stored as a PNG entry, which Windows Vista and later read at every size.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from qpdf2mk import icons  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def png_bytes(pixmap) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.toImage().save(buf, "PNG")
    buf.close()
    return bytes(data)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        dim = 0 if size >= 256 else size  # 0 means 256 in the ICO directory
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    return header + entries + blobs


def main(out: str) -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841 - QPixmap needs an app
    ico = icons.app_icon()
    images = []
    for s in SIZES:
        pm = ico.pixmap(QSize(s, s))
        if pm.width() != s:
            raise SystemExit(f"app_icon() has no {s}px rendition (got {pm.width()}px)")
        images.append((s, png_bytes(pm)))
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_ico(images))
    print(f"wrote {path} ({len(images)} sizes)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
