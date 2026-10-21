@echo off
setlocal
chcp 65001 >nul
rem qPdf2MD Microsoft Store package builder: packages the app (build_exe.bat), then wraps it in an
rem MSIX for Partner Center. Output goes to %USERPROFILE%\.qpdf2mk\msix, outside OneDrive.
rem
rem   build_msix.bat               rebuild the exe, then the MSIX
rem   build_msix.bat --skip-exe    reuse the existing %USERPROFILE%\.qpdf2mk\dist\qPdf2MD
rem
rem Needs the Windows SDK for MakeAppx.exe / MakePri.exe (only once):
rem   winget install --id Microsoft.WindowsSDK.10.0.26100 --exact
rem and the Store identity in packaging\msix\store_identity.json plus SOURCE_URL in qpdf2mk\__init__.py.

set "APP_DIR=%~dp0"
set "BUILD_ROOT=%USERPROFILE%\.qpdf2mk"
set "VENV=%BUILD_ROOT%\build-venv"
set "DIST=%BUILD_ROOT%\dist\qPdf2MD"
set "OUT=%BUILD_ROOT%\msix"

rem Keep the window open at the end when started by double-click.
set "PAUSE_AT_END="
set "CMDLINE=%CMDCMDLINE:"=%"
echo(%CMDLINE%| findstr /i /c:"%~nx0" >nul && set "PAUSE_AT_END=1"

if /i not "%~1"=="--skip-exe" (
    call "%APP_DIR%build_exe.bat" || goto :fail
)
if not exist "%DIST%\qPdf2MD.exe" (
    echo 找不到 %DIST%\qPdf2MD.exe，請先執行 build_exe.bat。
    goto :fail
)
if not exist "%VENV%\Scripts\python.exe" (
    echo 找不到打包環境 %VENV%，請先執行 build_exe.bat。
    goto :fail
)

echo [qPdf2MD] 正在製作 MSIX 套件...
"%VENV%\Scripts\python.exe" "%APP_DIR%packaging\make_msix.py" --dist "%DIST%" --out "%OUT%" || goto :fail
if defined PAUSE_AT_END pause
exit /b 0

:fail
echo [qPdf2MD] 製作 MSIX 失敗，請檢查上方的錯誤訊息。
if defined PAUSE_AT_END pause
exit /b 1
