@echo off
setlocal EnableExtensions
chcp 65001 >nul
rem qPdf2MD source publisher: commits this folder and pushes it to https://github.com/chaoban/qPdf2MD.
rem The AGPL requires the complete source of every released version to be public.
rem
rem   push_to_github.bat                commit all changes and push to main
rem   push_to_github.bat --tag          same, then tag the current APP_VERSION (e.g. v1.0.0) for a Store release
rem   push_to_github.bat "message"      commit with your own message
rem
rem Before the first run, create an EMPTY public repository named qPdf2MD at https://github.com/new
rem (no README, .gitignore or license). The first push opens a browser window to sign in to GitHub.
rem The Git database lives in %USERPROFILE%\.qpdf2mk\git\qPdf2MD.git, outside OneDrive;
rem this folder only gets a small ".git" pointer file.

set "APP_DIR=%~dp0"
set "REMOTE=https://github.com/chaoban/qPdf2MD.git"
set "GIT_PARENT=%USERPROFILE%\.qpdf2mk\git"
set "GIT_STORE=%GIT_PARENT%\qPdf2MD.git"
set "DO_TAG="
set "MSG="
if /i "%~1"=="--tag" (set "DO_TAG=1") else set "MSG=%~1"

rem Keep the window open at the end when started by double-click.
set "PAUSE_AT_END="
set "CMDLINE=%CMDCMDLINE:"=%"
echo(%CMDLINE%| findstr /i /c:"%~nx0" >nul && set "PAUSE_AT_END=1"

where git >nul 2>nul
if errorlevel 1 (
    echo 找不到 Git。請先安裝 Git for Windows，裝好後重新開啟這個視窗再執行：
    echo   winget install --id Git.Git -e
    goto :fail
)
cd /d "%APP_DIR%" || goto :fail

set "VER="
for /f "tokens=2 delims==" %%v in ('findstr /b /c:"APP_VERSION" "qpdf2mk\__init__.py"') do set "VER=%%v"
if not defined VER (
    echo 讀不到 qpdf2mk\__init__.py 的 APP_VERSION。
    goto :fail
)
set "VER=%VER: =%"
set "VER=%VER:"=%"

rem A ".git" pointer whose database is missing (deleted, or this folder synced from another PC) is recreated.
if exist ".git" (
    git rev-parse --git-dir >nul 2>nul || del /a /f /q ".git" >nul 2>nul
)
if not exist ".git" (
    echo [qPdf2MD] 建立 Git 儲存庫：%GIT_STORE%
    rem git init does not create the parent folders of --separate-git-dir itself.
    if not exist "%GIT_PARENT%" mkdir "%GIT_PARENT%" || goto :fail
    git init -q -b main --separate-git-dir "%GIT_STORE%" || goto :fail
)
rem Commits are public: use GitHub's no-reply address instead of a personal e-mail.
git config user.name "chaoban"
git config user.email "17902233+chaoban@users.noreply.github.com"
git config core.autocrlf false
git remote get-url origin >nul 2>nul || git remote add origin "%REMOTE%"

git add -A || goto :fail
git diff --cached --quiet
if not errorlevel 1 (
    echo [qPdf2MD] 沒有新的變更需要提交。
    goto :push
)
git rev-parse -q --verify HEAD >nul 2>nul
if not errorlevel 1 goto :commit
set "MSGFILE=%TEMP%\qpdf2md-commit.txt"
> "%MSGFILE%" (
    echo qPdf2MD %VER%：Microsoft Store 版原始碼
    echo.
    echo PDF 轉 Markdown 桌面程式（PySide6、PyMuPDF、RapidOCR），依 GNU AGPL v3 發布。
    echo.
    echo Co-Authored-By: Claude Opus 5.5 ^<noreply@anthropic.com^>
    echo Claude-Session: https://claude.ai/code/session_017LE7s8epshetXVeDCYigoD
)
git commit -q -F "%MSGFILE%" || goto :fail
del "%MSGFILE%" >nul 2>nul
goto :push

:commit
if not defined MSG set "MSG=更新原始碼：qPdf2MD %VER%"
git commit -q -m "%MSG%" || goto :fail

:push
echo [qPdf2MD] 推送到 %REMOTE% ...
git push -u origin main
if errorlevel 1 (
    echo.
    echo [qPdf2MD] 推送失敗，請確認：
    echo   1. 已在 https://github.com/new 建立名為 qPdf2MD 的「公開」空白儲存庫，沒有勾選 README、.gitignore 或授權
    echo   2. 跳出的 GitHub 登入視窗已用 chaoban 帳號登入
    goto :fail
)

if not defined DO_TAG goto :done
git rev-parse -q --verify "refs/tags/v%VER%" >nul 2>nul
if not errorlevel 1 (
    echo [qPdf2MD] 標籤 v%VER% 已經存在。發行新版本前，請先修改 qpdf2mk\__init__.py 的 APP_VERSION。
    goto :fail
)
git tag -a "v%VER%" -m "qPdf2MD %VER%" || goto :fail
git push origin "v%VER%" || goto :fail
echo [qPdf2MD] 已建立並推送標籤 v%VER%

:done
echo.
echo [qPdf2MD] 完成：https://github.com/chaoban/qPdf2MD
if defined PAUSE_AT_END pause
exit /b 0

:fail
echo [qPdf2MD] 未完成，請檢查上方的錯誤訊息。
if defined PAUSE_AT_END pause
exit /b 1
