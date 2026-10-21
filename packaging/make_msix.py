"""Build the Microsoft Store package (MSIX) from the PyInstaller output of build_exe.bat.

    python packaging/make_msix.py --dist <dist\\qPdf2MD> --out <folder> [--sdk-bin <Windows Kits\\10\\bin\\<ver>\\x64>]
    python packaging/make_msix.py --assets-only --out <folder>     render the images only (any OS)

Steps:
  1. check the release prerequisites (Store identity, SOURCE_URL required by the AGPL, version format)
  2. copy the app into <out>\\layout
  3. render the tile / logo images from qpdf2mk.icons.app_icon_svg() into layout\\Assets
  4. write layout\\AppxManifest.xml from packaging\\msix\\AppxManifest.xml.in
  5. index the images into layout\\resources.pri (MakePri) so Windows can pick scale/target-size variants
  6. pack <out>\\qPdf2MD_<version>_x64.msix (MakeAppx)

The package is not signed: the Store signs it after certification. To try it locally, register the layout
folder instead (Windows Developer Mode on):  Add-AppxPackage -Register <out>\\layout\\AppxManifest.xml
Run it through build_msix.bat, which also rebuilds the exe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qpdf2mk import APP_NAME, APP_TAGLINE, APP_VERSION, PRIVACY_URL, SOURCE_URL  # noqa: E402

MSIX_DIR = ROOT / "packaging" / "msix"
IDENTITY_FILE = MSIX_DIR / "store_identity.json"
TEMPLATE = MSIX_DIR / "AppxManifest.xml.in"
MIN_VERSION = "10.0.17763.0"         # Windows 10 1809, the oldest release Qt 6 supports
MAX_VERSION_TESTED = "10.0.26100.0"  # Windows 11 24H2
DESCRIPTION = "PDF 轉 Markdown 轉換器"

SCALES = (100, 125, 150, 200, 400)
TARGET_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
# (resource name, size at scale-100, share of the shorter side the icon fills)
SCALED_ASSETS = (
    ("Square44x44Logo", (44, 44), 1.0),
    ("Square150x150Logo", (150, 150), 0.66),
    ("Wide310x150Logo", (310, 150), 0.66),
    ("StoreLogo", (50, 50), 1.0),
    ("SplashScreen", (620, 300), 0.5),
)


class BuildError(Exception):
    pass


# --------------------------------------------------------------------------- prerequisites

def msix_version(version: str) -> str:
    parts = version.split(".")
    if not 1 <= len(parts) <= 4 or not all(p.isdigit() for p in parts):
        raise BuildError(f"APP_VERSION「{version}」必須是 1.2.3 這種數字格式")
    parts = (parts + ["0"] * 4)[:4]
    if parts[3] != "0":
        raise BuildError(f"Microsoft Store 要求版本號第四碼為 0，APP_VERSION「{version}」請改用前三碼")
    return ".".join(str(int(p)) for p in parts)


def load_identity() -> dict[str, str]:
    try:
        data = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"無法讀取 {IDENTITY_FILE}：{exc}") from exc
    ident = {k: str(data.get(k, "")).strip() for k in ("Name", "Publisher", "PublisherDisplayName")}
    if any(not v or "XXXX" in v for v in ident.values()):
        raise BuildError(
            f"請先填寫 {IDENTITY_FILE.relative_to(ROOT)}：在 Partner Center 開啟 qPdf2MD →「產品管理」→"
            "「產品身分識別」，把 Package/Identity/Name、Package/Identity/Publisher、"
            "Package/Properties/PublisherDisplayName 三個值原樣貼上。"
        )
    if not re.fullmatch(r"[-.A-Za-z0-9]{3,50}", ident["Name"]):
        raise BuildError(f"Package Name「{ident['Name']}」格式不對，請從 Partner Center 原樣複製")
    if not ident["Publisher"].startswith("CN="):
        raise BuildError(f"Publisher「{ident['Publisher']}」應以 CN= 開頭，請從 Partner Center 原樣複製")
    return ident


def check_release_info() -> None:
    if not SOURCE_URL:
        raise BuildError(
            "qpdf2mk/__init__.py 的 SOURCE_URL 還是空的。qPdf2MD 依 AGPL-3.0 發布，散佈前必須公開原始碼，"
            "請先把原始碼放到公開位置（例如 GitHub），再填入網址。"
        )
    if not PRIVACY_URL:
        print("[qPdf2MD] 提醒：PRIVACY_URL 尚未設定。Partner Center 一定要填隱私權政策網址（可用 PRIVACY.md 的公開連結），"
              "填入 PRIVACY_URL 後「關於」視窗也會顯示。")


# --------------------------------------------------------------------------- images

def render_assets(assets: Path, extra: Path | None = None) -> int:
    """Render every tile / logo variant from the app icon SVG. Returns the number of files written."""
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    from qpdf2mk.icons import app_icon_svg

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - QPainter needs an app
    renderer = QSvgRenderer(QByteArray(app_icon_svg()))

    def save(path: Path, w: int, h: int, share: float) -> None:
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        side = round(min(w, h) * share)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter, QRectF((w - side) / 2, (h - side) / 2, side, side))
        painter.end()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not img.save(str(path), "PNG"):
            raise BuildError(f"無法寫入 {path}")

    count = 0
    for name, (w, h), share in SCALED_ASSETS:
        for scale in SCALES:
            save(assets / f"{name}.scale-{scale}.png", round(w * scale / 100), round(h * scale / 100), share)
            count += 1
    # Taskbar, Start list and Explorer pick these by pixel size; "unplated" = drawn without a coloured plate.
    for size in TARGET_SIZES:
        for suffix in ("", "_altform-unplated", "_altform-lightunplated"):
            save(assets / f"Square44x44Logo.targetsize-{size}{suffix}.png", size, size, 1.0)
            count += 1
    if extra is not None:
        # Partner Center > Store listing > Store logos > "1:1 App tile icon" (300 x 300 px)
        save(extra / "AppTileIcon_300x300.png", 300, 300, 1.0)
        count += 1
    return count


# --------------------------------------------------------------------------- manifest

def write_manifest(path: Path, ident: dict[str, str], version: str) -> None:
    values = {
        "name": ident["Name"],
        "publisher": ident["Publisher"],
        "publisher_display_name": ident["PublisherDisplayName"],
        "version": version,
        "display_name": APP_NAME,
        "description": DESCRIPTION,
        "min_version": MIN_VERSION,
        "max_version_tested": MAX_VERSION_TESTED,
    }
    text = TEMPLATE.read_text(encoding="utf-8")
    text = re.sub(r"\{(\w+)\}", lambda m: escape(values[m.group(1)], {'"': "&quot;"}), text)
    ET.fromstring(text.encode("utf-8"))  # fail here, not in MakeAppx, if the XML is broken
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- Windows SDK tools

def find_sdk_bin(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("WINDOWS_SDK_BIN"):
        candidates.append(Path(os.environ["WINDOWS_SDK_BIN"]))
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    if kits.is_dir():
        versions = [d for d in kits.iterdir() if d.is_dir() and re.fullmatch(r"10\.\d+\.\d+\.\d+", d.name)]
        versions.sort(key=lambda d: tuple(int(x) for x in d.name.split(".")), reverse=True)
        candidates += [d / "x64" for d in versions]
    for c in candidates:
        if (c / "makeappx.exe").is_file() and (c / "makepri.exe").is_file():
            return c
    raise BuildError(
        "找不到 Windows SDK 的 MakeAppx.exe / MakePri.exe。請先安裝 Windows SDK：\n"
        "  winget install --id Microsoft.WindowsSDK.10.0.26100 --exact\n"
        "或用 --sdk-bin 指定 ...\\Windows Kits\\10\\bin\\<版本>\\x64 資料夾。"
    )


def run(cmd: list[str]) -> None:
    print("  >", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    if result.returncode != 0:
        print(result.stdout)
        raise BuildError(f"{Path(cmd[0]).name} 失敗（結束代碼 {result.returncode}），錯誤訊息見上方")


def make_pri(sdk: Path, layout: Path, work: Path) -> None:
    """Index only the manifest and Assets\\ (not the thousands of runtime files) into layout\\resources.pri."""
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(layout / "Assets", work / "Assets")
    shutil.copy2(layout / "AppxManifest.xml", work / "AppxManifest.xml")
    config = work.parent / "priconfig.xml"  # kept outside the indexed folder
    run([str(sdk / "makepri.exe"), "createconfig", "/cf", str(config), "/dq", "zh-TW", "/pv", "10.0.0", "/o"])
    # Without a <packaging> section MakePri keeps every scale / size variant in one resources.pri
    # (instead of splitting them into resource packs, which only a bundle could carry).
    tree = ET.parse(config)
    for parent in tree.getroot().iter():
        for child in list(parent):
            if child.tag == "packaging":
                parent.remove(child)
    tree.write(config, encoding="utf-8", xml_declaration=True)
    run([str(sdk / "makepri.exe"), "new", "/pr", str(work), "/cf", str(config),
         "/mn", str(work / "AppxManifest.xml"), "/of", str(layout / "resources.pri"), "/o"])


# --------------------------------------------------------------------------- main

def build(dist: Path, out: Path, sdk_bin: str | None) -> Path:
    if not (dist / f"{APP_NAME}.exe").is_file():
        raise BuildError(f"找不到 {dist / (APP_NAME + '.exe')}，請先執行 build_exe.bat")
    check_release_info()
    ident = load_identity()
    version = msix_version(APP_VERSION)
    sdk = find_sdk_bin(sdk_bin)
    print(f"[qPdf2MD] MSIX {ident['Name']} {version}（Windows SDK：{sdk}）")

    layout = out / "layout"
    if layout.exists():
        shutil.rmtree(layout)
    print("[qPdf2MD] 複製程式檔案...")
    shutil.copytree(dist, layout)
    print("[qPdf2MD] 產生圖示...")
    n = render_assets(layout / "Assets", extra=out / "store-listing")
    print(f"           {n} 個圖檔；商店清單用的 300x300 圖示：{out / 'store-listing' / 'AppTileIcon_300x300.png'}")
    write_manifest(layout / "AppxManifest.xml", ident, version)
    print("[qPdf2MD] 建立 resources.pri...")
    make_pri(sdk, layout, out / "pri")
    package = out / f"{APP_NAME}_{version}_x64.msix"
    print("[qPdf2MD] 封裝 MSIX，約需 1-3 分鐘...")
    run([str(sdk / "makeappx.exe"), "pack", "/d", str(layout), "/p", str(package), "/o"])
    return package


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", help="PyInstaller output folder that contains qPdf2MD.exe")
    ap.add_argument("--out", required=True, help="working / output folder")
    ap.add_argument("--sdk-bin", help="folder with makeappx.exe and makepri.exe")
    ap.add_argument("--assets-only", action="store_true", help="only render the images into <out>")
    args = ap.parse_args()
    out = Path(args.out)
    try:
        if args.assets_only:
            n = render_assets(out / "Assets", extra=out / "store-listing")
            print(f"wrote {n} images to {out}")
            return 0
        if not args.dist:
            ap.error("--dist is required")
        package = build(Path(args.dist), out, args.sdk_bin)
    except BuildError as exc:
        print(f"[qPdf2MD] {exc}")
        return 1
    print()
    print(f"[qPdf2MD] MSIX 完成：{package}  ({package.stat().st_size / 2**20:.0f} MB)")
    print("  上傳：Partner Center > qPdf2MD > 提交 > 套件，拖入這個 .msix。")
    print("  本機測試（需開啟「開發人員模式」）：在 PowerShell 執行")
    print(f"    Add-AppxPackage -Register \"{out / 'layout' / 'AppxManifest.xml'}\"")
    print("  測完移除：Get-AppxPackage *qPdf2MD* | Remove-AppxPackage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
