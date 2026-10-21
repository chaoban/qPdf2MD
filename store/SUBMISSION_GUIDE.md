# qPdf2MD Microsoft Store 上架填寫指南

適用版本：qPdf2MD 1.0.0（MSIX 套件、免費上架、AGPL-3.0 開源）
整理日期：2026-10-21。Partner Center 介面與政策會改版，送出前以畫面上的說明為準。

Partner Center 有中文和英文介面，下面的欄位名稱寫成「中文（English）」，方便對照。

---

## 0. 送審前檢查清單

依序完成，前一項沒好，後面的步驟會卡住。

| # | 項目 | 做法 | 狀態 |
|---|---|---|---|
| 1 | 開發者帳戶完成身分驗證 | Partner Center →「帳戶設定」，個人帳戶需完成證件＋自拍驗證 | ☐ |
| 2 | ~~付款與稅務設定~~ | **免費上架不需要**。只有日後改成收費或加入 App 內購買時，才要到「帳戶設定 → 付款與稅務（Payout and tax）」填寫 | — |
| 3 | 保留名稱 `qPdf2MD` | 「Apps 與遊戲 →新產品 → MSIX 或 PWA 應用程式」→ 輸入 qPdf2MD →「檢查可用性」→ 保留 | ☐ |
| 4 | 填 `packaging/msix/store_identity.json` | 見第 2 節 | ☐ |
| 5 | **公開原始碼** | 儲存庫：https://github.com/chaoban/qPdf2MD（`SOURCE_URL` 已填好）。在 GitHub 建立空的公開儲存庫後，雙擊 `push_to_github.bat` | ☐ |
| 6 | 確認隱私權政策網址打得開 | https://github.com/chaoban/qPdf2MD/blob/main/PRIVACY.md（`PRIVACY_URL` 已填好，推上 GitHub 後即生效） | ☐ |
| 7 | 製作 MSIX | 雙擊 `build_msix.bat` | ☐ |
| 8 | 本機安裝測試 | `Add-AppxPackage -Register`（見 README〈上架 Microsoft Store〉），測：開啟、拖入 PDF、AI 版面分析、OCR（**拔掉網路測一次**）、密碼 PDF、輸出到桌面與 OneDrive 資料夾、淺色／深色、關於 → 授權資訊、解除安裝 | ☐ |
| 9 | 乾淨環境測試 | 在「Windows 沙箱」或沒裝過 Python 的電腦安裝一次，確認不缺 DLL | ☐ |
| 10 | Windows App Cert Kit | 開始功能表 →「Windows App Cert Kit」→ 驗證應用程式套件 → 選 .msix | ☐ |
| 11 | 螢幕擷取畫面 4–6 張 | 見 3.5 節 | ☐ |

**建議一併處理（非必要）**：主視窗最小尺寸是 1120×720。1366×768 筆電在 125% 縮放下可用區域只有約 1093×580，視窗會超出螢幕。認證不一定因此退件，但會影響評價，建議把最小尺寸降到約 960×600，並確認三欄版面在該尺寸仍可使用。

---

## 1. AGPL 開源：上架前必做

qPdf2MD 內含 PyMuPDF、pymupdf4llm、PyMuPDF Layout（AGPL-3.0），所以整個程式依 AGPL-3.0 發布。**免費上架同樣適用**：AGPL 的義務來自「散佈」，與是否收費無關。要做到：

1. **原始碼公開**：把整個專案（含 `build_*.bat`、`qPdf2MD.spec`、`packaging/`、`installer/`、`licenses/`）推到公開的 Git 儲存庫，例如 GitHub。
2. **版本對應**：每次送審前，在儲存庫打標籤，例如 `v1.0.0`，確保使用者拿得到「與 Store 版相同版本」的原始碼。打包前執行 `push_to_github.bat --tag` 即可，會依 `APP_VERSION` 自動建立並推送標籤。
3. **填網址**：`qpdf2mk/__init__.py` 的 `SOURCE_URL` 填儲存庫網址。沒填時 `build_msix.bat` 會停止，「關於」視窗也會顯示紅字「（尚未公開）」。
4. **商店授權條款**：「其他授權條款」欄填 AGPL 聲明，見 3.5 節。Microsoft Store 的〈標準應用程式授權條款〉寫明：App 附有自己的條款時，以該條款為準，因此不會出現「禁止複製、禁止反向工程」這類與 AGPL 衝突的限制。
5. **上游原始碼**（建議）：AGPL 元件的原始碼由上游公開（PyMuPDF、pymupdf4llm、PyMuPDF Layout 的 GitHub）。保險起見，可在儲存庫的 Release 附上這些套件對應版本的原始碼封存檔。

**你仍保有的權利**：著作權仍屬於 SAISAI；SAISAI 名稱與標誌可主張商標，別人可以散佈程式，但不能用你的名稱與標誌上架冒充。

---

## 2. 產品身分識別（Product identity）→ `store_identity.json`

位置：Partner Center → qPdf2MD →「產品管理（Product management）」→「產品身分識別（Product identity）」。

| Partner Center 顯示 | 貼到 `store_identity.json` 的欄位 | 範例格式 |
|---|---|---|
| Package/Identity/Name | `Name` | `12345SAISAI.qPdf2MD` |
| Package/Identity/Publisher | `Publisher` | `CN=1A2B3C4D-....` |
| Package/Properties/PublisherDisplayName | `PublisherDisplayName` | `SAISAI` |

三個值必須**一字不差**，否則上傳套件時會顯示身分不符。發行者顯示名稱（PublisherDisplayName）就是商店頁顯示的開發者名稱，在「帳戶設定」中設定。

---

## 3. 建立提交（Submission）

在 qPdf2MD 的「應用程式概觀」按「開始提交」，依序完成以下六個區塊。

### 3.1 定價與可用性（Pricing and availability）

| 欄位 | 建議填法 | 說明 |
|---|---|---|
| 市場（Markets） | **台灣、香港、澳門**；可加新加坡、馬來西亞 | 介面只有繁體中文。免費 App 開放全部市場也可以，但看不懂中文的使用者容易下載後給低評價；要全開的話，請一併新增英文商店清單（3.5 節最後），描述開頭寫明介面為繁體中文 |
| 對象（Audience） | 公開（Public audience） | |
| 可探索性（Discoverability） | 在 Microsoft Store 中提供並可搜尋到 | |
| 排程（Schedule） | 通過認證後立即發行 | 想自己決定上架時間，改在 3.6「發行保留選項」設定 |
| 基本價格（Base price） | **免費（Free）** | |
| 免費試用（Free trial） | 不適用 | 價格設為免費時不需設定 |
| 促銷價格（Sale pricing） | 不適用 | |
| 組織授權（Organizational licensing） | 保留預設 | |

**費用**：免費 App 上架不需支付任何費用，也不需設定付款與稅務資料。日後若要改成收費，可在新的提交中修改價格，屆時再完成付款與稅務設定。

### 3.2 屬性（Properties）

| 欄位 | 建議填法 |
|---|---|
| 類別（Category） | **生產力（Productivity）** |
| 子類別 | 無則留空 |
| 次要類別（Secondary category） | 公用程式與工具（Utilities & tools） |
| 隱私權政策網址（Privacy policy URL） | **必填**：https://github.com/chaoban/qPdf2MD/blob/main/PRIVACY.md。政策 10.5.1 規定 Win32／Desktop Bridge 類 App 一律要有隱私權政策，即使完全離線 |
| 網站（Website） | https://github.com/chaoban/qPdf2MD |
| 支援連絡資訊（Support contact info） | `aisais.dev@gmail.com` |
| 聯絡人詳細資料（Contact details） | 公司帳戶才需要 |
| 顯示模式（Display mode） | **全部不勾**。這是 Windows Mixed Reality／HoloLens 的選項，勾了可能導致提交出錯 |
| 產品宣告（Product declarations） | 見下表 |
| 系統需求（System requirements） | 見下表 |

產品宣告（依畫面實際項目勾選）：

| 宣告 | 勾選 | 理由 |
|---|---|---|
| 允許使用者購買，但不使用 Microsoft Store 商務系統 | 不勾 | 沒有 App 內購買 |
| 已測試符合協助工具（無障礙）指導方針 | 不勾 | 實際用朗讀程式和 Accessibility Insights 測過才勾 |
| 客戶可將此 App 安裝到其他磁碟機或卸除式存放裝置 | 保留勾選 | |
| Windows 可將此 App 的資料納入自動備份至 OneDrive | 保留勾選 | 只有設定值 |
| 此 App 依賴非 Microsoft 的驅動程式或 NT 服務 | 不勾 | |

系統需求：

| 項目 | 最低 | 建議 |
|---|---|---|
| 記憶體 | 4 GB | 8 GB |
| 其他系統需求（每項 ≤200 字元） | Windows 10 版本 1809 以上（64 位元）；約 400 MB 可用磁碟空間 | 掃描版 PDF 文字辨識建議 4 核心以上 CPU |

### 3.3 年齡分級（Age ratings）

填 IARC 問卷。qPdf2MD 是生產力工具，依實際狀況回答：

| 問題類型 | 回答 |
|---|---|
| App 類別 | 選工具／生產力類（非遊戲、非社群、非影音串流） |
| 暴力、恐怖、性、粗話、毒品酒精、賭博內容 | 否 |
| 使用者之間可以互動或交換內容 | 否 |
| 分享使用者位置 | 否 |
| App 內購買數位商品 | 否 |
| 不受限制的網路存取（內建瀏覽器或搜尋） | 否 |
| 收集個人資料 | 否 |

預期結果是最低年齡級別（各地「3+／普遍級」）。

### 3.4 套件（Packages）

1. 把 `%USERPROFILE%\.qpdf2mk\msix\qPdf2MD_1.0.0.0_x64.msix` 拖進上傳區。
2. 驗證完成後確認：版本 `1.0.0.0`、架構 `x64`、語言 `zh-TW`。
3. 裝置系列（Device family availability）：只勾 **Windows 10/11 桌上型電腦**，Xbox、HoloLens 等不勾。

上傳時可能出現的訊息：

- **「runFullTrust 為受限功能，需要核准」**：正常，所有 Win32 桌面 App 都會有。到 3.6「受限制的功能」填理由即可。
- **身分不符（Name／Publisher）**：`store_identity.json` 與 Partner Center 不一致，修正後重新執行 `build_msix.bat --skip-exe`。
- **版本號**：第四碼必須是 0；之後每次提交都要比上一版大。

### 3.5 商店清單（Store listings）

「新增語言」→ 選 **中文（台灣）**。下列文字可直接複製；英文清單為選填，放在本節最後。

**產品名稱（Product name）**：`qPdf2MD`（從保留名稱選）。政策 10.1.1 規定名稱不可夾帶說明文字，所以不要寫成「qPdf2MD – PDF 轉 Markdown」。

**描述（Description，≤10,000 字元，純文字，不放網址）**：

```
qPdf2MD 把 PDF 轉換成乾淨、結構化的 Markdown（.md），方便貼進筆記軟體、知識庫、文件網站，或交給 AI 工具處理。

AI 版面分析會自動辨識標題層級、段落、清單、表格、圖片與閱讀順序，並略過頁首、頁尾與頁碼。掃描版 PDF 也能轉換：內建 OCR 文字辨識支援繁體中文、簡體中文、英文與日文。

所有處理都在你的電腦上完成，完全離線執行，不需要帳號，也不會上傳任何檔案。

主要功能
• 兩種辨識模式：AI 版面分析（品質最佳，每頁約 1–2 秒）與快速模式（依字型判斷結構，速度極快）
• OCR 文字辨識：自動只處理掃描頁，或每頁都辨識；繁中、簡中、英文、日文
• 批次轉換：一次拖入多個 PDF 或整個資料夾（含子資料夾）
• 指定頁面範圍，例如 1-5, 8, 12-
• 圖片可存成檔案、內嵌 Base64 或不輸出；PNG／JPG、72–300 DPI
• 自動整理格式：合併斷行、修正清單縮排、清除多餘空行；可加頁面分隔標記與 YAML 前置資料
• 即時預覽：原始 PDF、排版後的 Markdown、語法上色的原始碼，三種檢視切換對照
• 支援受密碼保護的 PDF
• 淺色、深色與跟隨系統主題

使用須知
• 介面語言為繁體中文。
• 需要 Windows 10 版本 1809 以上（64 位元）。
• OCR 準確度取決於掃描品質；字太小、模糊或歪斜的頁面可能出現錯字，重要文件請對照原稿校對。
• 本程式只讀取 PDF、產生 Markdown，不會修改原始 PDF。

開放原始碼
qPdf2MD 是自由軟體，依 GNU Affero 通用公眾授權條款第 3 版（AGPL-3.0）發布，完整原始碼公開，取得方式見「其他授權條款」。轉換核心使用 PyMuPDF，介面使用 Qt。
```

**這一版的新功能（What's new）**：首次上架留空。

**產品功能（Product features，最多 20 項，每項 ≤200 字元）**：

```
AI 版面分析，辨識標題、清單、表格與閱讀順序
掃描版 PDF 的 OCR 文字辨識（繁中、簡中、英文、日文）
完全離線，檔案不會離開你的電腦
批次轉換多個 PDF 或整個資料夾
自訂頁面範圍
圖片另存檔案、內嵌或略過
自動移除頁首、頁尾與頁碼
原始 PDF、Markdown 預覽與原始碼三種檢視
支援受密碼保護的 PDF
淺色／深色主題
```

**螢幕擷取畫面（Screenshots）**：至少 1 張，建議 4–6 張；PNG、單檔 ≤50 MB、**1366×768 以上**（建議 1920×1080），最多 10 張。畫面必須是程式實際的樣子（政策 10.1）。建議內容：

1. 開始畫面（拖放區）
2. 批次轉換中的檔案佇列與進度
3. Markdown 預覽與原始 PDF 對照
4. 掃描版 PDF 經 OCR 轉出的結果
5. 右側設定面板
6. 深色主題

擷取時把視窗調整到螢幕大小，使用沒有個資與版權疑慮的範例 PDF。

**商店標誌（Store logos）**：「1:1 應用程式磚圖示（300×300）」上傳 `build_msix.bat` 產生的 `%USERPROFILE%\.qpdf2mk\msix\store-listing\AppTileIcon_300x300.png`。2:3 海報圖與 1:1 盒裝圖是遊戲用的，可略過。

**預告片（Trailers）**：選填，可略過。

**短描述（Short description，建議 ≤270 字元）**：

```
把 PDF 轉成結構化 Markdown：AI 版面分析辨識標題、清單、表格與圖片，內建繁中／簡中／英文／日文 OCR，完全離線執行。
```

**搜尋字詞（Search terms／Keywords）**：政策 10.1.3 規定最多 7 個、要與功能相關、不可含價格字眼。

```
PDF
Markdown
PDF 轉 Markdown
OCR
文字辨識
文件轉換
MD
```

**著作權與商標資訊（Copyright and trademark info）**：

```
© 2026 SAISAI
```

**其他授權條款（Additional license terms）**：

```
qPdf2MD 是自由軟體：您可以依照自由軟體基金會發布的 GNU Affero 通用公眾授權條款第 3 版（AGPL-3.0）散佈及／或修改本程式。本程式不提供任何擔保，亦無適售性或特定目的適用性之默示擔保。

完整原始碼（含打包腳本）：https://github.com/chaoban/qPdf2MD
授權條款全文：https://www.gnu.org/licenses/agpl-3.0.html

本程式隨附的第三方元件依其各自授權條款使用，包括 Qt（GNU LGPL v3）、PyMuPDF／pymupdf4llm／PyMuPDF Layout（GNU AGPL v3）、RapidOCR 與 PP-OCR 模型（Apache 2.0）等；完整清單與授權全文請見程式內「關於 → 授權資訊」。

qPdf2MD is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3 (AGPL-3.0) as published by the Free Software Foundation. It is distributed WITHOUT ANY WARRANTY, without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
Complete source code (including build scripts): https://github.com/chaoban/qPdf2MD
Third-party components are used under their own licenses; see "About > License information" in the app.
```

**開發者（Developed by）**：`SAISAI`

**其他系統需求**：與 3.2 相同，可再寫一次。

#### 英文清單（選填）

想讓非中文區使用者也看得懂，可再「新增語言 → English (United States)」。描述開頭要先說明介面是繁體中文，避免政策 10.7 的語言一致性問題：

```
qPdf2MD converts PDF files into clean, structured Markdown. Note: the user interface is in Traditional Chinese.

AI layout analysis detects headings, lists, tables, images and reading order, and skips page headers, footers and page numbers. Scanned PDFs are supported through built-in OCR for Traditional Chinese, Simplified Chinese, English and Japanese.

Everything runs offline on your PC. No account, no uploads.

• Two modes: AI layout analysis (best quality) and fast mode
• OCR for scanned pages
• Batch conversion of files and whole folders
• Page ranges, image export (files, embedded Base64 or none), automatic clean-up
• Side-by-side preview: original PDF, rendered Markdown and source
• Password-protected PDFs, light and dark themes

Requires Windows 10 version 1809 or later (64-bit). OCR accuracy depends on scan quality.

qPdf2MD is free software licensed under the GNU AGPL v3; see the additional license terms for the source code.
```

### 3.6 提交選項（Submission options）

**發行保留選項（Publishing hold options）**：第一次上架建議選「**手動發行**」（通過認證後不自動上架），先在 Partner Center 預覽商店頁，確認沒問題再按「立即發行」。

**認證備註（Notes for certification，≤2,000 字元）**，可直接複製：

```
qPdf2MD is an offline desktop app (Python + Qt, packaged with PyInstaller as a full-trust MSIX) that converts PDF files to Markdown. The user interface is in Traditional Chinese.

No account, login, network connection or special hardware is required. Any PDF file can be used for testing.

How to test:
1. Start qPdf2MD from the Start menu.
2. Drag one or more PDF files (or a folder) onto the window, or press Ctrl+O (button「選擇 PDF 檔案」).
3. Press「開始轉換」(Ctrl+Enter). Progress is shown per page. The .md file is written next to the PDF by default (or to the folder chosen in the right-hand settings panel).
4. When finished, the preview switches to the rendered Markdown. Ctrl+1 / Ctrl+2 / Ctrl+3 switch between the original PDF, the preview and the Markdown source.
5. For a scanned PDF (image-only pages), OCR runs automatically.
6. F1 opens the About box; 「授權資訊…」shows the open-source licenses.

The first conversion may take a few seconds while the AI layout and OCR models load. All models are included in the package; the app never downloads code or data.

The app is open source under the GNU AGPL v3. Complete source: https://github.com/chaoban/qPdf2MD
```

**受限制的功能（Restricted capabilities）→ runFullTrust 的理由**：

```
qPdf2MD is a Win32 desktop application (Python runtime with Qt for Python) packaged as MSIX. runFullTrust is required to run its Win32 executable. It reads PDF files the user selects or drops onto the window and writes the converted Markdown and images to folders the user chooses. It does not install drivers or services, and it makes no network connections.
```

**提交通知對象**：保留預設。

按「提交至 Store」。

---

## 4. 送審後

- **認證時間**：通常數個工作天，期間可在提交頁面看到進度（前置處理 → 認證 → 發行）。
- **退件**：Partner Center 會列出違反的政策編號與說明，修正後建立新提交即可。這類 App 常見的退件原因：

| 原因 | 對應政策 | 預防 |
|---|---|---|
| 沒有隱私權政策網址或網址打不開 | 10.5.1 | 3.2 節必填，送審前用無痕視窗開一次 |
| 描述與實際功能不符、未說明限制 | 10.1.1 | 描述已寫明介面語言、系統需求與 OCR 限制 |
| 啟動當機、缺 DLL | 10.4 | 第 0 節第 8、9 項的實機與沙箱測試 |
| 截圖不是實際畫面 | 10.1 | 只用程式真實畫面 |
| 名稱含說明文字 | 10.1.1 | 名稱只寫 qPdf2MD |

- **發行後**：商店頁網址在「產品管理 → 產品身分識別」或「應用程式概觀」可找到，格式是 `https://apps.microsoft.com/detail/<Store ID>`。可放進 README 與原始碼儲存庫。

---

## 5. 之後更新版本

1. 修改 `qpdf2mk/__init__.py` 的 `APP_VERSION`，例如 `"1.1.0"`。
2. 原始碼推上儲存庫並打標籤 `v1.1.0`（AGPL：讓使用者拿得到這一版的原始碼）。
3. 雙擊 `build_msix.bat`，產生 `qPdf2MD_1.1.0.0_x64.msix`。
4. Partner Center → qPdf2MD →「更新」建立新提交 →「套件」上傳新檔並移除舊套件 →「商店清單」填「這一版的新功能」→ 提交。
5. 已安裝的使用者由 Windows 自動更新，設定值會保留。

---

## 參考資料

- [Microsoft Store 政策（版本 7.20）](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies)
- [MSIX App 提交檢查清單](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission)
- [商店清單欄位說明](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info)
- [螢幕擷取畫面與圖片規格](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images)
- [Win32 App 透過 Store 散佈：MSIX 與 MSI/EXE 比較](https://learn.microsoft.com/en-us/windows/apps/distribute-through-store/how-to-distribute-your-win32-app-through-microsoft-store)
- [手動建立 MSIX 套件（AppxManifest、MakePri）](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-manual-conversion)
- [Microsoft Store 標準應用程式授權條款](https://www.microsoft.com/store/standard-application-license-terms)
