@echo off
setlocal
chcp 65001 >nul
rem qPdf2MD exe builder: packages the app with PyInstaller into a folder that runs without Python.
rem Everything it creates (build environment, temp files, output) lives in %USERPROFILE%\.qpdf2mk,
rem outside OneDrive, so hundreds of MB are not synced.
rem
rem   build_exe.bat                 output: %USERPROFILE%\.qpdf2mk\dist\qPdf2MD\qPdf2MD.exe
rem   build_exe.bat <folder>        output: <folder>\qPdf2MD\qPdf2MD.exe

set "APP_DIR=%~dp0"
set "BUILD_ROOT=%USERPROFILE%\.qpdf2mk"
set "VENV=%BUILD_ROOT%\build-venv"
set "WORK=%BUILD_ROOT%\build"
set "DIST=%BUILD_ROOT%\dist"
if not "%~1"=="" set "DIST=%~f1"
rem PyInstaller's cache defaults to %LOCALAPPDATA%, which Microsoft Store Python redirects.
set "PYINSTALLER_CONFIG_DIR=%BUILD_ROOT%\pyinstaller-cache"

rem Keep the window open at the end when started by double-click.
set "PAUSE_AT_END="
set "CMDLINE=%CMDCMDLINE:"=%"
echo(%CMDLINE%| findstr /i /c:"%~nx0" >nul && set "PAUSE_AT_END=1"

rem The build environment must not come from conda/Anaconda Python: PySide6 cannot load there
rem ("DLL load failed while importing QtCore"), see packaging\find_python.py. Rebuild such an environment.
if exist "%VENV%\Scripts\python.exe" (
    "%VENV%\Scripts\python.exe" "%APP_DIR%packaging\find_python.py" --check >nul || call :remove_venv || goto :fail
)
if not exist "%VENV%\Scripts\python.exe" (
    call "%APP_DIR%packaging\find_python.bat" || goto :fail
    call :create_venv || goto :fail
)

echo [qPdf2MD] 正在安裝／檢查套件...
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%APP_DIR%requirements.txt" -r "%APP_DIR%packaging\requirements-build.txt" || goto :fail
rem Stop here with a short message rather than deep inside PyInstaller.
"%VENV%\Scripts\python.exe" -c "import PySide6.QtCore" || goto :qt_fail

echo [qPdf2MD] 正在打包，約需 1-3 分鐘...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --log-level WARN --workpath "%WORK%" --distpath "%DIST%" "%APP_DIR%qPdf2MD.spec" || goto :fail

if not exist "%DIST%\qPdf2MD\qPdf2MD.exe" goto :fail
echo.
echo [qPdf2MD] 打包完成：%DIST%\qPdf2MD\qPdf2MD.exe
echo 整個 %DIST%\qPdf2MD 資料夾就是可攜版程式，可以壓縮成 zip 或複製到其他電腦，雙擊 qPdf2MD.exe 即可執行。
if defined PAUSE_AT_END pause
exit /b 0

:qt_fail
echo [qPdf2MD] 打包環境無法載入 PySide6（錯誤見上方）。可以刪除 %VENV% 資料夾後再執行一次。

:fail
echo [qPdf2MD] 打包失敗，請檢查上方的錯誤訊息。
if defined PAUSE_AT_END pause
exit /b 1

:remove_venv
echo [qPdf2MD] 現有的打包環境不適用（原因見上一行），刪除後重新建立：%VENV%
rmdir /s /q "%VENV%"
if not exist "%VENV%" exit /b 0
echo [qPdf2MD] 無法刪除 %VENV%，請關閉正在使用它的程式，或手動刪除這個資料夾後再試。
exit /b 1

:create_venv
echo [qPdf2MD] 正在建立打包用的 Python 環境：%VENV%
echo           使用 %BASE_PY%
"%BASE_PY%" -m venv "%VENV%" || exit /b 1
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
exit /b 0
