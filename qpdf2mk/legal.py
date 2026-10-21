"""License texts and the third-party notices shown in the About box.

Qt-free on purpose: qPdf2MD.spec imports it at build time to write THIRD_PARTY_NOTICES.txt from the
packages actually installed in the build environment, and the packaged app reads that file back.
When running from source (run.bat) the notices are generated live from the same metadata.

    python -m qpdf2mk.legal [output.txt]      write the notices (stdout without an argument)
"""

from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Iterable, Optional

from . import APP_NAME, APP_VERSION, CONTACT_EMAIL, COPYRIGHT, LICENSE_SPDX, PUBLISHER, SOURCE_URL

ROOT = Path(__file__).resolve().parents[1]
NOTICES_NAME = "THIRD_PARTY_NOTICES.txt"

# Full license texts bundled in licenses/ (tab title, file name)
LICENSE_TABS = (
    ("GNU AGPL v3", "AGPL-3.0.txt"),
    ("GNU LGPL v3", "LGPL-3.0.txt"),
    ("GNU GPL v3", "GPL-3.0.txt"),
)

QT_OPEN_SOURCE_URL = "https://www.qt.io/download-open-source"
QT_ARCHIVE_URL = "https://download.qt.io/archive/qt/"
QT_LICENSES_URL = "https://doc.qt.io/qt-6/licenses-used-in-qt.html"
PYTHON_LICENSE_URL = "https://docs.python.org/3/license.html"
MUPDF_SOURCE_URL = "https://github.com/ArtifexSoftware/mupdf"

RULE = "-" * 78

# Distributions whose own license files are only a stub or the Qt commercial option;
# they are covered by the hand-written sections at the top instead.
_COVERED = {"pyside6-essentials", "shiboken6", "pymupdf", "pymupdf4llm", "pymupdf-layout"}
_LICENSE_FILE = re.compile(r"(^|[/\\])(licen[cs]e|copying|notice|thirdpartynotices|third[-_]party[-_]notices)[^/\\]*$", re.I)
_SKIP_FILE = re.compile(r"LicenseRef-Qt-Commercial", re.I)
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


# --------------------------------------------------------------------------- locating bundled files

def licenses_dir() -> Path:
    """licenses/ next to the sources, or inside the PyInstaller bundle (_internal/licenses)."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "licenses" if base else ROOT / "licenses"


def license_text(file_name: str) -> str:
    path = licenses_dir() / file_name
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return f"找不到授權檔 {file_name}。完整條款請見 https://www.gnu.org/licenses/"


def third_party_notices() -> str:
    bundled = licenses_dir() / NOTICES_NAME
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    return build_third_party_notices()


# --------------------------------------------------------------------------- generating the notices

def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _squash(text: str) -> str:
    """Whitespace- and URL-scheme-insensitive form, to recognise a verbatim copy of a GNU license."""
    return re.sub(r"\s+", " ", text.replace("https://", "http://")).strip()


def runtime_distributions(requirements: Path = ROOT / "requirements.txt") -> list[metadata.Distribution]:
    """The packages listed in requirements.txt plus everything they depend on (installed ones only)."""
    todo: list[str] = []
    for line in requirements.read_text(encoding="utf-8").splitlines():
        m = _REQ_NAME.match(line)
        if m and not line.lstrip().startswith("#"):
            todo.append(m.group(1))
    found: dict[str, metadata.Distribution] = {}
    while todo:
        name = _norm(todo.pop())
        if name in found:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # optional or other-platform dependency that is not installed
        found[name] = dist
        for req in dist.requires or []:
            if re.search(r"extra\s*==", req):
                continue
            m = _REQ_NAME.match(req)
            if m:
                todo.append(m.group(1))
    return sorted(found.values(), key=lambda d: _norm(d.metadata["Name"]))


def _license_label(dist: metadata.Distribution) -> str:
    md = dist.metadata
    for key in ("License-Expression", "License"):
        value = (md.get(key) or "").strip()
        if value and "\n" not in value and len(value) <= 120:
            return value
    classifiers = [c.split("::")[-1].strip() for c in md.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or "見下方授權檔 / see license files below"


def _project_url(dist: metadata.Distribution) -> str:
    md = dist.metadata
    urls: dict[str, str] = {}
    for entry in md.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        urls[label.strip().lower()] = url.strip()
    for key in ("source", "source code", "repository", "homepage", "home"):
        if key in urls:
            return urls[key]
    return (md.get("Home-page") or "").strip() or next(iter(urls.values()), "")


def _license_files(dist: metadata.Distribution) -> Iterable[tuple[str, str]]:
    seen: set[str] = set()
    for f in dist.files or []:
        rel = str(f)
        if not _LICENSE_FILE.search(rel) or _SKIP_FILE.search(rel) or rel.endswith((".py", ".pyc")):
            continue
        try:
            text = Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text and text not in seen:
            seen.add(text)
            yield rel, text


def _header() -> list[str]:
    source = SOURCE_URL or "（尚未設定 SOURCE_URL）"
    return [
        f"{APP_NAME} {APP_VERSION} - Third-Party Software Notices / 第三方軟體授權聲明",
        f"Copyright (C) {COPYRIGHT.removeprefix('© ')}",
        f"Contact / 聯絡信箱: {CONTACT_EMAIL}",
        "",
        f"{APP_NAME} 由 {PUBLISHER} 開發，依 GNU Affero 通用公眾授權條款第 3 版（{LICENSE_SPDX}）發布，",
        f"完整原始碼：{source}",
        "本軟體使用並隨附下列第三方元件，各元件依其原授權條款使用，著作權屬於各自的權利人。",
        "",
        f"{APP_NAME} is developed by {PUBLISHER} and licensed under the GNU Affero General",
        f"Public License version 3 ({LICENSE_SPDX}). Complete source code: {source}",
        "It uses and redistributes the third-party components listed below, each under its own",
        "license. Copyright in those components remains with their respective owners.",
        "",
        "本程式不提供任何擔保；詳見「GNU AGPL v3」分頁第 15、16 條。",
        "This program comes with ABSOLUTELY NO WARRANTY; see sections 15 and 16 of the",
        "GNU AGPL v3 (\"GNU AGPL v3\" tab).",
        "",
    ]


def _section(no: int, title: str, body: list[str]) -> list[str]:
    return [RULE, f"{no}. {title}", RULE, *body, ""]


def _fixed_sections(qt_version: str) -> list[tuple[str, list[str]]]:
    source = SOURCE_URL or "（尚未設定 SOURCE_URL）"
    return [
        (f"Qt {qt_version} / Qt for Python (PySide6, Shiboken6)", [
            "Copyright (C) The Qt Company Ltd. and other contributors.",
            "",
            "License: GNU Lesser General Public License version 3 (LGPL-3.0).",
            "Full text: \"GNU LGPL v3\" and \"GNU GPL v3\" tabs (licenses/LGPL-3.0.txt, GPL-3.0.txt).",
            "",
            "- Qt is used unmodified and is dynamically linked (Qt6*.dll, the PySide6",
            "  modules and the plugin folders).",
            f"- The complete source code and build scripts of {APP_NAME} are public, so you can",
            f"  rebuild it against any compatible Qt / PySide6 version: {source}",
            f"- Qt source code: {QT_ARCHIVE_URL}",
            f"  Qt 6 open-source download: {QT_OPEN_SOURCE_URL}",
            "  Qt for Python source: https://code.qt.io/cgit/pyside/pyside-setup.git/",
            "- Qt includes further third-party code. The complete list and their licenses:",
            f"  {QT_LICENSES_URL}",
            "",
            "Qt 以 LGPL v3 授權使用，未經修改並以動態連結（DLL）方式載入。",
            f"{APP_NAME} 的完整原始碼與打包腳本公開，使用者可自行換用相容版本的 Qt／PySide6 重新建置。",
            "Qt 原始碼可由上方網址取得。",
        ]),
        ("PyMuPDF, pymupdf4llm, PyMuPDF Layout and MuPDF", [
            "Copyright (C) Artifex Software, Inc.",
            "",
            "License: GNU Affero General Public License version 3 (AGPL-3.0).",
            "Full text: \"GNU AGPL v3\" tab (licenses/AGPL-3.0.txt).",
            "",
            "- PyMuPDF source:        https://github.com/pymupdf/PyMuPDF",
            "- pymupdf4llm source:    https://github.com/pymupdf/pymupdf4llm",
            "- PyMuPDF Layout source: https://github.com/ArtifexSoftware/pymupdf_layout",
            f"- MuPDF source:          {MUPDF_SOURCE_URL}",
            "- MuPDF includes third-party libraries (among them FreeType, HarfBuzz, jbig2dec,",
            "  Little CMS, libjpeg, OpenJPEG, zlib and Gumbo), each under its own license;",
            "  see the thirdparty directory of the MuPDF source.",
            "- Portions of this software are copyright (C) The FreeType Project",
            "  (www.freetype.org). All rights reserved.",
            "",
            "PDF 轉換核心依 AGPL v3 授權使用，原始碼可由上方網址取得。",
        ]),
    ]


def _python_section() -> list[str]:
    body = [
        f"Python {sys.version.split()[0]} runtime (python3*.dll and the standard library), bundled by PyInstaller.",
        "Copyright (C) Python Software Foundation. License: PSF License Agreement.",
        f"Full text: {PYTHON_LICENSE_URL}",
        "",
        "The executable is started by the PyInstaller bootloader, which is licensed under the",
        "GPL-2.0 with a special exception that allows its use in programs under any license",
        "(https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt).",
    ]
    py_license = Path(sys.base_prefix) / "LICENSE.txt"
    if py_license.is_file():
        body += ["", py_license.read_text(encoding="utf-8", errors="replace").strip()]
    return body


def build_third_party_notices(qt_version: Optional[str] = None,
                              dists: Optional[list[metadata.Distribution]] = None) -> str:
    if qt_version is None:
        try:
            qt_version = metadata.version("PySide6-Essentials")
        except metadata.PackageNotFoundError:
            qt_version = "6"
    gnu = {_squash(license_text(name)): title for title, name in LICENSE_TABS}

    lines = _header()
    no = 0
    for title, body in _fixed_sections(qt_version):
        no += 1
        lines += _section(no, title, body)
    no += 1
    lines += _section(no, "Python", _python_section())

    for dist in runtime_distributions() if dists is None else dists:
        name = dist.metadata["Name"]
        body = [f"Version: {dist.version}", f"License: {_license_label(dist)}"]
        url = _project_url(dist)
        if url:
            body.append(f"Project: {url}")
        if _norm(name) in _COVERED:
            body += ["", "See the sections above. / 詳見上方說明。"]
        else:
            for rel, text in _license_files(dist):
                tab = gnu.get(_squash(text))
                body += ["", f"[{rel}]"]
                body.append(f"Full text: \"{tab}\" tab. / 全文見「{tab}」分頁。" if tab else text)
        no += 1
        lines += _section(no, name, body)
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    text = build_third_party_notices()
    if len(sys.argv) > 1:
        out = Path(sys.argv[1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out} ({len(text.splitlines())} lines)")
    else:
        sys.stdout.write(text)
