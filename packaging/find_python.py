r"""Find a Python that can host qPdf2MD's environments (used through packaging\find_python.bat).

    python packaging/find_python.py            print the path of a suitable python.exe; exit 1 if none
    <python> packaging/find_python.py --check  exit 0 if <python> itself is suitable, else say why, exit 1

Suitable: Python 3.10+, 64-bit, GIL build, and not conda / Anaconda / Miniconda.

Why not conda: a conda Python makes Windows look for DLLs in its own folders (the install
root, Library\bin) before the PySide6 package folder, so a same-named DLL of another
version gets loaded and `import PySide6.QtCore` fails with "DLL load failed while importing
QtCore: The specified procedure could not be found". PyInstaller would also copy those
DLLs into the packaged app. (--check inside a venv judges the Python the venv was made from.)

Candidates, best first: %QPDF2MK_PYTHON%; installs registered with Windows (PEP 514, done by
the python.org installers and the Python install manager); the default python.org install
folders; python on PATH. Among the installs, 3.13 > 3.12 > 3.11 > 3.10 > newer releases,
whose binary wheels (onnxruntime, OpenCV) can lag behind. Versions are never requested through
the py launcher, which may offer to download one that is missing.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import struct
import subprocess
import sys
import sysconfig

PREFERRED = ("3.13", "3.12", "3.11", "3.10")


def problem() -> str | None:
    """Why the running interpreter cannot be used, or None."""
    if sys.version_info < (3, 10):
        return f"Python {sys.version.split()[0]} 太舊（需要 3.10 以上）"
    if struct.calcsize("P") != 8:
        return "32 位元 Python（需要 64 位元）"
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        return "free-threaded Python（PySide6 不支援）"
    if os.path.isdir(os.path.join(sys.base_prefix, "conda-meta")):
        return f"conda／Anaconda Python（{sys.base_prefix}）"
    return None


def _version_of(text: str) -> str:
    m = re.search(r"3\.?(\d+)", text)
    return f"3.{m.group(1)}" if m else ""


def _rank(version: str) -> tuple:
    if version in PREFERRED:
        return (0, PREFERRED.index(version))
    minor = int(version.split(".")[1]) if version else 0
    return (1, -minor)


def registered() -> list[tuple[str, str]]:
    """(version, python.exe) for every PEP 514 registration, both per-user and per-machine."""
    try:
        import winreg
    except ImportError:
        return []
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            root = winreg.OpenKey(hive, r"Software\Python", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        except OSError:
            continue
        with root:
            for company in _subkeys(winreg, root):
                if company == "PyLauncher":
                    continue
                with winreg.OpenKey(root, company) as ck:
                    for tag in _subkeys(winreg, ck):
                        try:
                            with winreg.OpenKey(ck, tag) as tk:
                                version = _value(winreg, tk, "SysVersion") or _version_of(tag)
                            with winreg.OpenKey(ck, tag + r"\InstallPath") as ip:
                                exe = _value(winreg, ip, "ExecutablePath")
                                if not exe:
                                    exe = os.path.join(_value(winreg, ip, "") or "", "python.exe")
                        except OSError:
                            continue
                        found.append((version, exe))
    return found


def _subkeys(winreg, key) -> list[str]:
    names, i = [], 0
    while True:
        try:
            names.append(winreg.EnumKey(key, i))
        except OSError:
            return names
        i += 1


def _value(winreg, key, name: str) -> str | None:
    try:
        value = winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None
    return value if isinstance(value, str) and value else None


def in_default_folders() -> list[tuple[str, str]]:
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    patterns = []
    if local:
        patterns += [os.path.join(local, "Programs", "Python", "Python3*", "python.exe"),  # python.org, per user
                     os.path.join(local, "Python", "pythoncore-3*", "python.exe")]  # Python install manager
    if program_files:
        patterns.append(os.path.join(program_files, "Python3*", "python.exe"))  # python.org, all users
    found = []
    for pattern in patterns:
        for exe in glob.glob(pattern):
            found.append((_version_of(os.path.basename(os.path.dirname(exe))), exe))
    return found


def candidates() -> list[str]:
    ordered = []
    override = os.environ.get("QPDF2MK_PYTHON", "").strip().strip('"')
    if override:
        ordered.append(override)
    installs = registered() + in_default_folders()
    installs.sort(key=lambda vi: _rank(vi[0]))
    ordered += [exe for _, exe in installs]
    ordered += [p for p in (shutil.which("python"), shutil.which("python3")) if p]
    seen, unique = set(), []
    for exe in ordered:
        key = os.path.normcase(os.path.abspath(exe))
        if key not in seen:
            seen.add(key)
            unique.append(exe)
    return unique


def check(exe: str) -> tuple[str | None, str]:
    """(path reported by the interpreter, '') if usable, else (None, reason)."""
    try:
        r = subprocess.run([exe, os.path.abspath(__file__), "--check"], capture_output=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=60,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except FileNotFoundError:
        return None, "檔案不存在"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"無法執行（{exc}）"
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().splitlines()[-1], ""
    return None, (r.stderr.strip().splitlines() or [f"結束代碼 {r.returncode}"])[-1]


def main() -> int:
    if sys.argv[1:] == ["--check"]:
        reason = problem()
        if reason:
            print(reason, file=sys.stderr)
            return 1
        print(sys.executable)
        return 0

    rejected = []
    for exe in candidates():
        path, reason = check(exe)
        if path:
            print(path)
            return 0
        rejected.append(f"  {exe}：{reason}")
    if rejected:
        print("[qPdf2MD] 找到但不能使用的 Python：", *rejected, sep="\n", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
