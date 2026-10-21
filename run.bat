@echo off
setlocal
chcp 65001 >nul
rem qPdf2MD launcher: creates the Python environment on first run, then starts the app.
rem The environment lives outside OneDrive so hundreds of MB of packages are not synced.

set "APP_DIR=%~dp0"
set "VENV=%USERPROFILE%\.qpdf2mk\venv"
rem Copy of the requirements last installed; a difference means packages must be updated.
set "STAMP=%VENV%\requirements.installed.txt"

rem find_python.bat picks a python.org-style Python: conda/Anaconda ones cannot load PySide6.
if not exist "%VENV%\Scripts\pythonw.exe" (
    echo [qPdf2MD] 第一次執行：正在建立 Python 環境並安裝套件，約需 1-3 分鐘...
    call "%APP_DIR%packaging\find_python.bat" || goto :no_python
    call :create_venv || goto :fail
)

fc /b "%APP_DIR%requirements.txt" "%STAMP%" >nul 2>nul
if errorlevel 1 (
    echo [qPdf2MD] 正在安裝／更新套件...
    "%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%APP_DIR%requirements.txt" || goto :fail
    copy /y "%APP_DIR%requirements.txt" "%STAMP%" >nul
    echo [qPdf2MD] 安裝完成，正在啟動...
)

start "" "%VENV%\Scripts\pythonw.exe" "%APP_DIR%main.py" %*
exit /b 0

:fail
echo [qPdf2MD] 安裝失敗，請確認網路連線後再執行一次 run.bat。
pause
exit /b 1

:no_python
pause
exit /b 1

:create_venv
"%BASE_PY%" -m venv "%VENV%" || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
exit /b 0
