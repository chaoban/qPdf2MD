"""qPdf2MD entry point.

    python main.py [file.pdf | folder ...]
"""

import os
import sys

# pythonw has no console: give stray prints somewhere harmless to go.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qpdf2mk.app import run  # noqa: E402

if __name__ == "__main__":
    # In the packaged exe a worker process re-runs this file; let it run the worker instead of the GUI.
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(run(sys.argv))
