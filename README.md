# qPdf2MD — PDF → Markdown 轉換器

以 **Qt（PySide6）** 打造的桌面程式，把 PDF 轉成乾淨、結構化的 Markdown（`.md`）。
AI 版面分析會自動辨識標題層級、清單、表格、圖片與閱讀順序，並略過頁首、頁尾與頁碼。
掃描版 PDF 也能轉換：內建 OCR 會辨識頁面上的繁體中文、簡體中文、英文與日文。

## 快速開始

在資料夾中**雙擊 `run.bat`**。

- 第一次執行會自動建立 Python 環境並安裝套件（約 1–3 分鐘）。環境放在 `%USERPROFILE%\.qpdf2mk\venv`，不會佔用 OneDrive 空間。
- 之後每次雙擊都會直接開啟程式；`requirements.txt` 有變動時（例如新增功能需要的套件），會先自動更新套件。
- 也可以把 PDF 或資料夾直接拖到 `run.bat` 上，程式開啟時就會載入這些檔案。

需求：Windows 10/11、python.org 版 Python 3.10 以上（建議 3.13）。Anaconda／Miniconda 的 Python 不能用，見〈疑難排解〉。

不想安裝 Python？用 `build_exe.bat` 打包一次，之後直接雙擊 `qPdf2MD.exe` 即可（見下方〈打包成 exe〉）。要安裝到其他電腦，可以用 `build_installer.bat` 做成安裝程式（見〈製作安裝程式〉）；要上架 Microsoft Store，用 `build_msix.bat` 製作 MSIX 套件（見〈上架 Microsoft Store〉）。

## 操作流程

視窗頂端的步驟列會隨時標示目前進度：

1. **加入檔案**：把 PDF 拖進視窗，或按 `Ctrl+O`。可以一次拖入多個檔案或整個資料夾（會遞迴搜尋子資料夾）。
2. **調整設定**：在右側面板選擇辨識模式、文字辨識（OCR）、頁面範圍、圖片處理方式與輸出位置。設定會自動記住。
3. **轉換**：按「開始轉換」或 `Ctrl+Enter`。檔案佇列會逐頁顯示進度，按 `Esc` 可隨時停止。
4. **檢視成果**：轉換完成後，預覽區會自動切到排版好的 Markdown。也可以切換到原始碼、和原始 PDF 對照，或直接複製、開啟、另存。

## 功能

| 項目 | 說明 |
|---|---|
| 辨識模式 | **AI 版面分析**（ONNX 模型，品質最佳，每頁約 1–2 秒）／**快速模式**（依字型推斷結構，速度極快） |
| 文字辨識（OCR） | **自動**（預設）：只辨識掃描頁或沒有文字層的頁面，一般 PDF 不受影響／**全部頁面**：每頁都辨識，連圖片中的文字也轉出，並取代原有的 OCR 文字層／**關閉**。使用 RapidOCR（PP-OCRv6 模型），支援繁中、簡中、英文、日文，完全離線執行；掃描頁每頁約 1–3 秒 |
| 頁面範圍 | 全部頁面，或指定範圍，例如 `1-5, 8, 12-`（也接受全形逗號） |
| 圖片 | 存成檔案（放在 `檔名_images/`，用相對路徑引用）／內嵌 Base64／不輸出；可選 PNG 或 JPG 與 72–300 DPI |
| 內容處理 | 移除頁首頁尾與頁碼、自動整理格式（合併斷行、修正清單縮排、清除多餘空行）、頁面分隔標記、YAML 前置資料 |
| 輸出 | 與 PDF 相同資料夾或指定資料夾；檔名重複時自動改名（`檔名 (1).md`）或覆寫 |
| 受密碼保護的 PDF | 在檔案上點兩下，或開始轉換時輸入密碼 |
| 預覽 | 原始 PDF（延遲渲染，大檔案也流暢）、渲染後的 Markdown、語法上色的原始碼 |
| 介面 | 淺色／深色／跟隨系統主題（Windows 標題列也會跟著變色）、通知提示、拖放提示、右鍵選單 |

## 快捷鍵

| 按鍵 | 功能 |
|---|---|
| `Ctrl+O` | 加入 PDF |
| `Ctrl+Enter` | 開始轉換 |
| `Esc` | 停止轉換 |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` | 切換檢視：原始 PDF／預覽／Markdown |
| `Ctrl+Shift+C` | 複製目前檔案的 Markdown |
| `Delete` | 從佇列移除選取的檔案 |
| `F1` | 關於（含授權資訊） |

## 專案結構

```
main.py                     程式進入點
run.bat                     一鍵安裝並啟動
build_exe.bat               打包成免安裝 Python 的 exe
build_installer.bat         再包成安裝程式 qPdf2MD-Setup-版本.exe
build_msix.bat              再包成 Microsoft Store 用的 MSIX 套件
push_to_github.bat          提交並推送原始碼到 GitHub（--tag 另建版本標籤）
qPdf2MD.spec                PyInstaller 打包設定
LICENSE                     本程式授權（GNU AGPL v3 全文）
PRIVACY.md                  隱私權政策（Microsoft Store 上架必填網址）
licenses/                   AGPL / LGPL / GPL 授權全文，打包時隨程式附上
store/SUBMISSION_GUIDE.md   Microsoft Store（Partner Center）上架填寫指南
installer/
  qPdf2MD.iss               Inno Setup 安裝程式腳本
  ChineseTraditional.isl    安裝精靈的繁體中文語系檔
packaging/
  make_icon.py              由 app_icon() 產生 exe 圖示（.ico）
  make_msix.py              產生 MSIX 圖示、AppxManifest.xml、resources.pri 並封裝 .msix
  msix/AppxManifest.xml.in  MSIX 套件資訊清單範本
  msix/store_identity.json  Partner Center 的套件身分識別（打包前必填）
  find_python.bat / .py     替 run.bat、build_exe.bat 挑選可用的 Python（排除 Anaconda）
  requirements-build.txt    打包工具版本（PyInstaller）
qpdf2mk/
  engine.py                 PDF → Markdown 轉換核心（不依賴 Qt，可單獨使用）
  tidy.py                   Markdown 後處理整理
  jobs.py                   工作模型、背景轉換佇列、PDF 頁面渲染服務
  theme.py                  設計 token、淺色/深色配色、樣式表
  icons.py                  SVG 線條圖示（隨主題換色）
  brand.py                  SAISAI 標誌（向量繪製，深色主題自動反白）
  legal.py                  授權全文與第三方授權聲明（打包時依實際安裝的套件自動產生）
  main_window.py            主視窗：串接整個操作流程
  widgets/                  自訂元件：分段選擇器、開關、步驟列、檔案卡片、預覽、通知…
tests/test_engine.py        轉換核心的單元測試
```

## 開發

```bash
python -m unittest discover -s tests
```

轉換核心也可以在程式碼中直接呼叫：

```python
from qpdf2mk.engine import ConvertOptions, convert_pdf
result = convert_pdf("report.pdf", ConvertOptions(mode="layout", ocr="auto", images="folder"))
print(result.output_path, result.pages, result.words, result.ocr_pages)
```

OCR 測試需要安裝 `rapidocr`（已列在 `requirements.txt`）；沒有安裝時會自動略過。

## 打包成 exe

把程式打包成不需要安裝 Python 的 Windows 版本（只有負責打包的電腦需要 Python）：

1. 在資料夾中**雙擊 `build_exe.bat`**。第一次會建立打包環境並下載套件，約需 3–5 分鐘；之後重新打包約 1–2 分鐘。
2. 完成後輸出在 `%USERPROFILE%\.qpdf2mk\dist\qPdf2MD\`。
3. 雙擊其中的 **`qPdf2MD.exe`** 即可使用，也可以把 PDF 拖到 `qPdf2MD.exe` 上開啟。

整個 `qPdf2MD` 資料夾（約 360 MB，其中 OCR 相關元件約 130 MB）就是完整的程式：exe 必須和旁邊的 `_internal` 資料夾放在一起。可以把整個資料夾壓縮成 zip，拿到其他 Windows 10/11 電腦解壓縮後直接執行。

想改輸出位置，可以在命令列執行 `build_exe.bat D:\release`，產生 `D:\release\qPdf2MD\qPdf2MD.exe`。

打包產生的檔案全部放在 OneDrive 之外：

| 位置 | 內容 |
|---|---|
| `%USERPROFILE%\.qpdf2mk\build-venv` | 打包專用的 Python 環境（依 `requirements.txt` 與 `packaging\requirements-build.txt` 安裝）；若發現是用 Anaconda 的 Python 建立的，會自動刪除重建 |
| `%USERPROFILE%\.qpdf2mk\build` | PyInstaller 暫存檔、產生的圖示 |
| `%USERPROFILE%\.qpdf2mk\dist` | 輸出的程式 |

> **不要把輸出指定到專案資料夾裡。** OneDrive 不理會 `.gitignore`，會把數百 MB 的檔案全部同步。`.gitignore` 裡排除了 `build/`、`dist/`，只對 Git 有效。

技術說明：

- `qPdf2MD.spec` 採 onedir（資料夾）模式，啟動比單一檔案快；不顯示主控台視窗。
- 明確收入轉換引擎在執行時才載入的檔案：`pymupdf.layout` 的 ONNX 版面／表格模型與 YAML 設定、`pymupdf4llm` 的 OCR 判斷模型、RapidOCR 的 OCR 模型與設定檔、MuPDF（`mupdfcpp64.dll`）與 onnxruntime 的 DLL。
- 排除用不到的大型檔案：Qt 的軟體 OpenGL（`opengl32sw.dll`）、OpenCV 的影片模組（`opencv_videoio_ffmpeg*.dll`），以及 RapidOCR 的 PaddlePaddle／PyTorch／OpenVINO 等推論後端（只使用 onnxruntime）。
- exe 圖示在打包時由 `qpdf2mk/icons.py` 的 `app_icon()` 產生（`packaging/make_icon.py`），與視窗圖示一致；檔案內容中的版本號取自 `qpdf2mk/__init__.py` 的 `APP_VERSION`。
- 打包版沒有主控台，未預期的錯誤會記錄在 `%LOCALAPPDATA%\SAISAI\qPdf2MD\error.log`。
- 授權資訊：打包時由 `qpdf2mk/legal.py` 依打包環境實際安裝的套件產生 `THIRD_PARTY_NOTICES.txt`，連同 `licenses/` 的 AGPL／LGPL／GPL 全文放進 `_internal\licenses`，「關於 → 授權資訊」直接讀取。
- 散佈打包好的程式時，必須同時公開對應版本的完整原始碼（本程式依 AGPL-3.0 發布，見〈授權〉）。

## 製作安裝程式（部署到其他電腦）

把 exe 再包成單一個 **`qPdf2MD-Setup-1.0.0.exe`**（約 140 MB）。其他電腦只要雙擊就能安裝，不需要 Python，也不需要系統管理員權限。

### 製作

1. 負責打包的電腦先安裝 [Inno Setup 6](https://jrsoftware.org/isinfo.php)（只需要一次）：

   ```bash
   winget install --id JRSoftware.InnoSetup --scope user
   ```

2. **雙擊 `build_installer.bat`**。它會先執行 `build_exe.bat` 重新打包，再製作安裝程式，約需 5 分鐘。
   如果剛打包過 exe，可以用 `build_installer.bat --skip-exe` 直接製作安裝程式，約 1 分鐘。
3. 完成後，安裝程式在 `%USERPROFILE%\.qpdf2mk\installer\qPdf2MD-Setup-1.0.0.exe`（不在 OneDrive 裡）。

### 在其他電腦安裝

把 Setup.exe 複製過去（隨身碟、網路磁碟、雲端硬碟都可以），然後雙擊：

1. 選擇「**僅為我安裝**」（建議，不需要管理員權限，裝在 `%LOCALAPPDATA%\Programs\qPdf2MD`）或「為所有使用者安裝」（需要管理員權限，裝在 `C:\Program Files\qPdf2MD`）。
2. 確認安裝位置，選擇附加工作：「建立桌面圖示」（預設勾選）、「在 PDF 檔案與資料夾的右鍵選單加入『用 qPdf2MD 轉換成 Markdown』」（預設不勾選）。
3. 按「安裝」，約 10 秒完成。之後可以從「開始」功能表或桌面圖示開啟。

安裝精靈在繁體中文 Windows 顯示中文、英文 Windows 顯示英文，其他語言會先讓使用者選擇。需要 Windows 10/11 64 位元與約 370 MB 磁碟空間。
解除安裝：「設定 → 應用程式 → 已安裝的應用程式 → qPdf2MD → 解除安裝」。程式的設定（登錄 `HKCU\Software\SAISAI\qPdf2MD`）會保留，重新安裝後沿用。

### 更新版本

1. 修改 `qpdf2mk/__init__.py` 的 `APP_VERSION`，例如改成 `"1.1.0"`。
2. 重新執行 `build_installer.bat`，產生 `qPdf2MD-Setup-1.1.0.exe`。
3. 在已安裝的電腦上直接執行新的 Setup，就會原地升級：保留設定、圖示與右鍵選單，並替換整個程式執行環境（`_internal`），不會殘留舊版檔案。如果程式正在執行，安裝程式會先提示關閉。

### 大量部署（靜默安裝）

IT 人員可以用命令列不經精靈直接安裝，適合登入指令碼、群組原則或派送工具：

| 用途 | 指令 |
|---|---|
| 為目前使用者安裝 | `qPdf2MD-Setup-1.0.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER` |
| 為所有使用者安裝（管理員） | `qPdf2MD-Setup-1.0.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /ALLUSERS` |
| 指定附加工作 | 加上 `/TASKS="desktopicon,contextmenu"`（兩者都要）；不要桌面圖示用 `/MERGETASKS="!desktopicon"` |
| 指定安裝位置、記錄檔 | 加上 `/DIR="D:\Apps\qPdf2MD"`、`/LOG="C:\Temp\qpdf2mk-install.log"` |
| 靜默解除安裝 | `"%LOCALAPPDATA%\Programs\qPdf2MD\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES`（所有使用者版在 `C:\Program Files\qPdf2MD\`） |

結束代碼 0 表示成功。

### 注意事項

- **Windows SmartScreen**：安裝程式沒有數位簽章，從網路下載後第一次執行會出現「Windows 已保護您的電腦」，按「其他資訊 → 仍要執行」即可。若要在組織內大量散佈，建議購買程式碼簽署憑證，並在 `installer/qPdf2MD.iss` 加上 Inno Setup 的 `SignTool` 設定替 Setup.exe 與解除安裝程式簽章。
- **固定的 AppId**：`installer/qPdf2MD.iss` 裡的 `AppId` 是升級時辨識同一套程式的依據，請不要更改。
- **語系檔**：`installer/ChineseTraditional.isl` 來自 Inno Setup 官方 GitHub（jrsoftware/issrc 的非官方翻譯），並補上 6.1 版之後新增的 23 則訊息翻譯。
- 散佈安裝程式同樣需要公開對應版本的原始碼（AGPL-3.0）。

## 疑難排解

### `DLL load failed while importing QtCore: 找不到指定的程序`

Python 環境是用 Anaconda／Miniconda 的 Python 建立的。conda 版 Python 找 DLL 時會先找自己的資料夾（安裝根目錄、`Library\bin`），載入到版本不同的同名 DLL，PySide6 就無法載入；PyInstaller 也會把這些 DLL 打包進程式。

- `run.bat`、`build_exe.bat` 會自動略過 conda 版 Python，依序尋找：環境變數 `QPDF2MK_PYTHON` → 向 Windows 登錄的 Python（python.org 安裝程式、Python install manager）→ python.org 預設安裝資料夾 → PATH 上的 `python`。版本優先順序為 3.13、3.12、3.11、3.10，再來才是更新的版本。
- `build_exe.bat` 發現既有的打包環境是用 conda 版 Python 建立的，會自動刪除後重建。`run.bat` 的執行環境若也是這樣建立的，請手動刪除 `%USERPROFILE%\.qpdf2mk\venv` 後再執行一次。
- 電腦上只有 Anaconda 時，先安裝 python.org 版 Python：`winget install --id Python.Python.3.13 --scope user`，或從 <https://www.python.org/downloads/> 下載。
- 要指定某一套 Python：先執行 `set QPDF2MK_PYTHON=C:\完整路徑\python.exe`，在同一個命令列視窗執行 `build_exe.bat` 或 `run.bat`。

## 說明與限制

- 掃描版 PDF 建議搭配「AI 版面分析」：標題、清單與閱讀順序的辨識比快速模式準確。快速模式會依 OCR 文字行高推測標題，結果較粗略。
- OCR 的準確度取決於掃描品質；字太小、模糊或歪斜的頁面可能出現錯字，重要文件請對照原稿校對。
- 掃描頁辨識出文字後，整頁掃描圖不會再另存成圖片。
- 轉換引擎使用 PyMuPDF / pymupdf4llm / PyMuPDF Layout（AGPL-3.0）；介面使用 Qt for Python（LGPL-3.0）；OCR 使用 RapidOCR 與 PP-OCR 模型（Apache-2.0）。

## 上架 Microsoft Store（MSIX）

Store 版以 MSIX 套件**免費上架**：Microsoft 免費負責代管、簽章與自動更新。另一種方式是直接上架 Inno Setup 的 Setup.exe（MSI／EXE 途徑），但必須自備受信任憑證機構簽發的程式碼簽署憑證（需付費）、自行提供安裝檔的下載網址並自行處理更新，所以採用 MSIX。

一次性準備：

1. 安裝 Windows SDK（提供 MakeAppx、MakePri）：`winget install --id Microsoft.WindowsSDK.10.0.26100 --exact`
2. 在 Partner Center 保留名稱 qPdf2MD，到「產品管理 → 產品身分識別」，把三個值貼進 `packaging/msix/store_identity.json`。
3. 公開原始碼：在 <https://github.com/new> 建立名為 `qPdf2MD` 的**公開空白**儲存庫（不勾 README、.gitignore、授權），然後**雙擊 `push_to_github.bat`**。需要 Git for Windows（`winget install --id Git.Git -e`），第一次推送會開瀏覽器登入 GitHub。`SOURCE_URL`（<https://github.com/chaoban/qPdf2MD>）與 `PRIVACY_URL` 已填好。Git 資料庫放在 `%USERPROFILE%\.qpdf2mk\git\qPdf2MD.git`，不在 OneDrive 裡。

製作：**雙擊 `build_msix.bat`**（會先執行 `build_exe.bat`；剛打包過可用 `build_msix.bat --skip-exe`）。完成後在 `%USERPROFILE%\.qpdf2mk\msix\`：

| 檔案 | 用途 |
|---|---|
| `qPdf2MD_1.0.0.0_x64.msix` | 上傳到 Partner Center 的套件（不需自行簽章，Store 會簽） |
| `layout\` | 套件內容；本機測試用 |
| `store-listing\AppTileIcon_300x300.png` | 商店清單的「1:1 應用程式磚圖示」 |

本機測試（Windows「設定 → 系統 → 開發人員專用 → 開發人員模式」開啟）：

```powershell
Add-AppxPackage -Register "$env:USERPROFILE\.qpdf2mk\msix\layout\AppxManifest.xml"
# 從開始功能表開啟 qPdf2MD 測試；測完移除：
Get-AppxPackage *qPdf2MD* | Remove-AppxPackage
```

送審前建議用 Windows SDK 附的「Windows App Cert Kit」檢查一次 .msix。Store 版與 Inno Setup 安裝版的差異：裝在唯讀的 `WindowsApps` 資料夾；設定與錯誤記錄由 Windows 隔離存放、解除安裝時一併清除；沒有右鍵選單（MSIX 加資料夾右鍵需另寫 COM 殼層擴充），改用拖放加入檔案。

更新版本：修改 `APP_VERSION`（Store 版本號第四碼固定為 0，且每次都要比上一版大）→ 執行 `push_to_github.bat --tag`（推送原始碼並建立 `v版本` 標籤）→ 重新執行 `build_msix.bat` → 在 Partner Center 建立新的提交並上傳新套件。Partner Center 每個欄位怎麼填，見 [`store/SUBMISSION_GUIDE.md`](store/SUBMISSION_GUIDE.md)。

## 授權

qPdf2MD 是自由軟體，依 [GNU Affero 通用公眾授權條款第 3 版（AGPL-3.0）](LICENSE)發布，不提供任何擔保。因為轉換核心 PyMuPDF 系列採 AGPL-3.0，散佈本程式（包括在 Microsoft Store 免費上架）時，必須讓取得程式的人能拿到**對應版本的完整原始碼**（含打包腳本），且不得限制他們複製、修改與再散佈的權利。這些義務與是否收費無關。

實務做法：

- 原始碼放在公開的 Git 儲存庫，每個上架版本打一個標籤（例如 `v1.0.0`），`SOURCE_URL` 指向儲存庫。
- AGPL 元件（PyMuPDF、pymupdf4llm、PyMuPDF Layout）的原始碼由上游公開；保險起見，可在每個版本的 Release 附上這些套件對應版本的原始碼封存檔（`pip download --no-binary :all: --no-deps pymupdf==版本` 等）。
- 第三方元件的授權全文會自動收進程式（「關於 → 授權資訊」）。

## 版權與聯絡

© 2026 SAISAI，依 GNU AGPL v3 授權發布。

- 信箱：aisais.dev@gmail.com
- 隱私權政策：[PRIVACY.md](PRIVACY.md)

程式內的「關於」視窗（`F1` 或右上角 ⓘ）顯示 SAISAI 標誌、版權、AGPL 聲明與原始碼連結、Qt（LGPL v3）聲明，並提供「授權資訊」（第三方元件／GNU AGPL v3／GNU LGPL v3／GNU GPL v3 全文）與「關於 Qt」。這些文字集中在 `qpdf2mk/__init__.py`（`ORG_NAME`、`COPYRIGHT`、`CONTACT_EMAIL`、`LICENSE_NAME`、`SOURCE_URL`、`PRIVACY_URL`），修改一次即可同步到介面與 exe 檔案內容。安裝程式的發行者、版權與聯絡信箱另外寫在 `installer/qPdf2MD.iss`（`AppPublisher`、`AppCopyright`、`AppContact`），Store 版的發行者名稱寫在 `packaging/msix/store_identity.json`，需一併修改。
