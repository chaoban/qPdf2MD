@echo off
rem Sets BASE_PY to a Python that can create qPdf2MD's environments: 3.10+, 64-bit, not conda/Anaconda.
rem packaging\find_python.py does the search and explains why Anaconda is refused. Usage:
rem
rem   call "%APP_DIR%packaging\find_python.bat" || goto :fail
rem
rem To force a particular interpreter: set QPDF2MK_PYTHON=C:\path\to\python.exe
rem No setlocal here: BASE_PY has to reach the caller.

set "BASE_PY="
set "_QP_OUT=%TEMP%\qpdf2mk-python-%RANDOM%.txt"
set "_QP_ENC=%PYTHONIOENCODING%"
rem The path is read back with set /p under code page 65001, so have Python write UTF-8.
set "PYTHONIOENCODING=utf-8"

rem Any working Python can run the search, including one the search then rejects (e.g. Anaconda).
set "_QP_BOOT="
python -c "" >nul 2>nul && set "_QP_BOOT=python"
if not defined _QP_BOOT py -c "" <nul >nul 2>nul && set "_QP_BOOT=py"
if defined _QP_BOOT %_QP_BOOT% "%~dp0find_python.py" <nul >"%_QP_OUT%" && set /p BASE_PY=<"%_QP_OUT%"

del "%_QP_OUT%" >nul 2>nul
set "PYTHONIOENCODING=%_QP_ENC%"
set "_QP_ENC="
set "_QP_OUT="
set "_QP_BOOT="
if defined BASE_PY exit /b 0

echo [qPdf2MD] 找不到可用的 Python：需要 python.org 版的 Python 3.10 以上（64 位元）。
echo   Anaconda／Miniconda 的 Python 不能用，PySide6 在它底下會載入失敗（DLL load failed while importing QtCore）。
echo   安裝 python.org 版：winget install --id Python.Python.3.13 --scope user
echo   或到 https://www.python.org/downloads/ 下載，裝好後重新執行。
echo   已經裝在其他位置的話，先執行 set QPDF2MK_PYTHON=完整路徑\python.exe 再重新執行。
exit /b 1
