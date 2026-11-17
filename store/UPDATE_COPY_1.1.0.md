# qPdf2MD 1.1.0 更新版上架文案

整理日期：2026-11-17。依〈qPdf2MD_release_update_steps.md〉第 6 節，更新提交只需改下列內容，其餘沿用 1.0.0。

## 版本號

`qpdf2mk/__init__.py`：`APP_VERSION = "1.1.0"`（MSIX 版本 `1.1.0.0`，GitHub 標籤 `v1.1.0`）。三處必須一致。

## 商店清單 → 這一版的新功能（What's new）

### 中文（台灣）

```
1.1.0 更新
• 一次批次轉換大量 PDF 時，記憶體用量更低
• 拖入含大量子資料夾的目錄時，視窗不再暫時卡住
• 覆寫既有檔案重新轉換時，自動清除上次留下的舊圖片
• 完善錯誤記錄，方便診斷問題
```

### English (United States)

```
Version 1.1.0
• Lower memory use when converting many PDFs in one batch
• Dragging in a folder with many subfolders no longer freezes the window
• When overwriting existing files, images left over from the previous run are now removed
• More complete error logging to help diagnose problems
```

## GitHub Release（標籤 v1.1.0）

與上面相同的兩份文字，中英文並列即可。

## 不需要改的項目

- 描述、產品功能、短描述、搜尋字詞：沿用。
- 認證備註、runFullTrust 理由：沿用。
- 隱私權政策／PRIVACY.md：已寫明「錯誤訊息寫入本機記錄檔、不離開電腦」，與新版行為一致，不用改。商店描述的「完全離線」仍成立。
- 年齡分級、定價、屬性：不動。
- 螢幕擷取畫面：介面沒有改變，沿用；若有改介面再換（英文清單用英文介面）。
- 英文翻譯：本版沒有新增 `tr()` 文字，`en.py` 不用補。

## 提交步驟

1. 改 `APP_VERSION` → 跑測試與 `run.bat` 實測 → `build_msix.bat`。
2. Partner Center → 更新 → 套件：上傳 `qPdf2MD_1.1.0.0_x64.msix` 並移除 1.0.0.0。
3. 商店清單兩種語言貼上「這一版的新功能」→ 提交至 Store。
4. 測試通過、不再改檔後，執行 `push_to_github.bat --tag`，自動建立 `v1.1.0` 標籤。
