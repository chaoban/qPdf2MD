# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for qPdf2MD: one-folder, windowed (no console) build.

Run it through build_exe.bat, which prepares the build environment and keeps every
build artifact outside OneDrive. Directly:

    python -m PyInstaller --noconfirm --workpath <work> --distpath <dist> qPdf2MD.spec
"""

import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules
from PyInstaller.utils.win32 import versioninfo as vi

ROOT = Path(SPECPATH)
WORK = Path(workpath)
sys.path.insert(0, str(ROOT))

from qpdf2mk import APP_NAME, APP_TAGLINE, APP_VERSION, COPYRIGHT, LICENSE_SPDX, PUBLISHER  # noqa: E402  (plain constants, no Qt import)
from qpdf2mk.legal import NOTICES_NAME, build_third_party_notices  # noqa: E402  (Qt-free)

# Executable icon, rendered from qpdf2mk.icons.app_icon() so it always matches the window icon.
ICON = WORK / f"{APP_NAME}.ico"
subprocess.run([sys.executable, str(ROOT / "packaging" / "make_icon.py"), str(ICON)], check=True)

# File properties shown by Explorer (Details tab).
ver = tuple(int(p) for p in (APP_VERSION.split(".") + ["0"] * 4)[:4])
VERSION_FILE = WORK / "version_info.txt"
VERSION_FILE.write_text(
    str(
        vi.VSVersionInfo(
            ffi=vi.FixedFileInfo(filevers=ver, prodvers=ver),
            kids=[
                vi.StringFileInfo([
                    vi.StringTable("040404B0", [
                        vi.StringStruct("CompanyName", PUBLISHER),
                        vi.StringStruct("LegalCopyright", f"{COPYRIGHT}. Licensed under {LICENSE_SPDX}."),
                        vi.StringStruct("FileDescription", f"{APP_NAME} — {APP_TAGLINE}"),
                        vi.StringStruct("FileVersion", APP_VERSION),
                        vi.StringStruct("InternalName", APP_NAME),
                        vi.StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                        vi.StringStruct("ProductName", APP_NAME),
                        vi.StringStruct("ProductVersion", APP_VERSION),
                    ])
                ]),
                vi.VarFileInfo([vi.VarStruct("Translation", [0x0404, 1200])]),
            ],
        )
    ),
    encoding="utf-8",
)

# License texts for the About box: the GNU licenses from licenses/ plus THIRD_PARTY_NOTICES.txt, written
# from the packages installed in this build environment so the list always matches what is shipped.
NOTICES = WORK / NOTICES_NAME
NOTICES.write_text(build_third_party_notices(), encoding="utf-8")
LEGAL = [(str(ROOT / "licenses"), "licenses"), (str(NOTICES), "licenses"), (str(ROOT / "LICENSE"), ".")]

# The conversion stack loads model files by path and links native DLLs that static
# analysis alone can miss, so collect them explicitly:
#   pymupdf.layout  ONNX layout / table models + YAML configs (resources/onnx, onnx/*.yaml)
#   pymupdf4llm     ocr_decision_model.onnx
#   pymupdf         mupdfcpp64.dll next to _mupdf.pyd
#   onnxruntime     onnxruntime.dll / providers_shared.dll in capi/
#   rapidocr        OCR models (PP-OCRv6 det/rec, text-direction cls) + YAML configs; its
#                   entry module is imported lazily, so list the submodules explicitly
datas = collect_data_files("pymupdf.layout") + collect_data_files("pymupdf4llm") + collect_data_files("rapidocr") + LEGAL
binaries = collect_dynamic_libs("pymupdf") + collect_dynamic_libs("onnxruntime")

# RapidOCR runs on onnxruntime only; its other inference back ends need frameworks we do not ship.
UNUSED_OCR_ENGINES = [f"rapidocr.inference_engine.{e}" for e in ("openvino", "paddle", "pytorch", "tensorrt", "mnn")]
hiddenimports = collect_submodules("pymupdf.layout") + collect_submodules(
    "rapidocr", filter=lambda name: not name.startswith(tuple(UNUSED_OCR_ENGINES))
)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "_tkinter", "matplotlib", "scipy", "pandas", "IPython", "torch", "pytest",
              "paddle", "openvino", "tensorrt", "MNN", *UNUSED_OCR_ENGINES],
    noarchive=False,
)
# Not needed at runtime: the software OpenGL fallback (20 MB; the UI is plain QtWidgets and never
# creates a GL context) and OpenCV's FFmpeg video I/O plugin (30 MB; OCR only reads in-memory images).
DROP = ("opengl32sw.dll", "opencv_videoio_ffmpeg")
a.binaries = [b for b in a.binaries if not Path(b[0]).name.lower().startswith(DROP)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    icon=str(ICON),
    version=str(VERSION_FILE),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
