"""Error log shared by the GUI thread and the worker threads.

The packaged app has no console (main.py points stderr at the null device), so anything that is only
printed is lost. Everything unexpected goes to <AppLocalData>/error.log instead.
"""

from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()


def _log_file() -> Path:
    from PySide6.QtCore import QStandardPaths

    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "error.log"


def log_text(text: str) -> None:
    """Append one entry; never raises."""
    try:
        path = _log_file()
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}")
    except Exception:
        pass


def log_exception(exc_info=None) -> str:
    """Log the exception being handled (or ``exc_info``) and return its traceback text."""
    text = "".join(traceback.format_exception(*(exc_info or sys.exc_info())))
    log_text(text)
    if sys.__stderr__:
        sys.__stderr__.write(text)
    return text
