"""Application bootstrap: Qt setup, theme, background engine warm-up."""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import APP_NAME, ORG_NAME, icons, theme
from .engine import load_engine
from .main_window import MainWindow
from .theme import ThemeManager


class EngineLoader(QThread):
    """Imports the conversion stack (≈1–2 s) without blocking the first paint."""

    loaded = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.loaded.emit(load_engine())
        except Exception as exc:  # pragma: no cover - depends on the environment
            traceback.print_exc()
            self.failed.emit(f"{type(exc).__name__}: {exc}")


def _install_excepthook() -> None:
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))

    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "error.log", "a", encoding="utf-8") as fh:
                fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
        except OSError:
            pass
        sys.__stderr__ and sys.__stderr__.write(text)

    sys.excepthook = hook


def is_packaged() -> bool:
    """True when running from an MSIX package (Microsoft Store install), which has its own identity."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        length = ctypes.c_uint32(0)
        # APPMODEL_ERROR_NO_PACKAGE (15700) means a plain, unpackaged process.
        return ctypes.windll.kernel32.GetCurrentPackageFullName(ctypes.byref(length), None) != 15700
    except Exception:
        return False


def create_app(argv: list[str], settings: QSettings | None = None) -> tuple[QApplication, MainWindow, EngineLoader]:
    # An MSIX package already gives the process its AppUserModelID (<PackageFamilyName>!qPdf2MD); overriding it
    # would split the running window from its Start menu entry and taskbar pin.
    if sys.platform == "win32" and not is_packaged():
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{ORG_NAME}.{APP_NAME}")
        except Exception:
            pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setFont(theme.ui_font(9.5))
    app.setWindowIcon(icons.app_icon())
    _install_excepthook()

    settings = settings or QSettings(ORG_NAME, APP_NAME)
    tm = ThemeManager(app, str(settings.value("theme", "system")))
    tm.apply(force=True)

    window = MainWindow(tm, settings)
    loader = EngineLoader(app)
    loader.loaded.connect(window.set_engine_ready)
    loader.failed.connect(window.set_engine_failed)
    return app, window, loader


def run(argv: list[str]) -> int:
    app, window, loader = create_app(argv)
    window.show()
    theme.apply_window_frame(window, theme.current())
    loader.start()
    files = [a for a in argv[1:] if not a.startswith("-")]
    if files:
        QTimer.singleShot(200, lambda: window.add_paths(files))
    code = app.exec()
    loader.wait(3000)
    return code
