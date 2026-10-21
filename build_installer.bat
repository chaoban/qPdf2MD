@echo off
setlocal
chcp 65001 >nul
rem qPdf2MD installer builder: packages the app (build_exe.bat), then wraps it in a single
rem Setup.exe with Inno Setup 6. Output goes to %USERPROFILE%\.qpdf2mk\installer, outside OneDrive.
rem
rem   build_installer.bat               rebuild the exe, then the installer
rem   build_installer.bat --skip-exe    reuse the existing %USERPROFILE%\.qpdf2mk\dist\qPdf2MD

set "APP_DIR=%~dp0"
set "BUILD_ROOT=%USERPROFILE%\.qpdf2mk"
set "DIST=%BUILD_ROOT%\dist\qPdf2MD"
set "ICON=%BUILD_ROOT%\build\qPdf2MD\qPdf2MD.ico"
set "OUT=%BUILD_ROOT%\installer"

rem Keep the window open at the end when started by double-click.
set "PAUSE_AT_END="
set "CMDLINE=%CMDCMDLINE:"=%"
echo(%CMDLINE%| findstr /i /c:"%~nx0" >nul && set "PAUSE_AT_END=1"

set "ISCC="
for %%d in ("%LOCALAPPDATA%\Programs\Inno Setup 6" "%ProgramFiles(x86)%\Inno Setup 6" "%ProgramFiles%\Inno Setup 6") do (
    if not defined ISCC if exist "%%~d\ISCC.exe" set "ISCC=%%~d\ISCC.exe"
)
if not defined ISCC (
    echo 找不到 Inno Setup 6。請先安裝：winget install --id JRSoftware.InnoSetup --scope user
    echo 或從 https://jrsoftware.org/isdl.php 下載。
    goto :fail
)

if /i not "%~1"=="--skip-exe" (
    call "%APP_DIR%build_exe.bat" || goto :fail
)
if not exist "%DIST%\qPdf2MD.exe" (
    echo 找不到 %DIST%\qPdf2MD.exe，請先執行 build_exe.bat。
    goto :fail
)

echo [qPdf2MD] 正在製作安裝程式，約需 2-5 分鐘...
"%ISCC%" /Q "/DSourceDir=%DIST%" "/DIconFile=%ICON%" "/O%OUT%" "%APP_DIR%installer\qPdf2MD.iss" || goto :fail

echo.
echo [qPdf2MD] 安裝程式完成：
for %%f in ("%OUT%\qPdf2MD-Setup-*.exe") do echo   %%~ff  (%%~zf bytes)
echo 把這個 Setup.exe 複製到其他電腦，雙擊即可安裝。
if defined PAUSE_AT_END pause
exit /b 0

:fail
echo [qPdf2MD] 製作安裝程式失敗，請檢查上方的錯誤訊息。
if defined PAUSE_AT_END pause
exit /b 1
