# Tiger-AI-RoomStyler

AI 房間整理與風格建議系統。使用者可上傳或拍攝房間照片，設定「是否允許購買」、「是否允許移動大型家具」、「必須保留的物品」等限制，由雲端多模態模型產生以照片證據為基礎的整理建議，並以證據框、視覺行動計畫與完成狀態協助執行。

> **重要：本專案目前沒有執行任何本機 AI 模型。** Web 與 Android 的 AI 推論皆透過雲端 API 完成。

## 目前狀態

| 模組 | 狀態 | 說明 |
|---|---|---|
| Web Phase 1A：房間照片分析 | **PASS** | 真實 NVIDIA GLM-5.3-Flash 分析、照片觀察、證據框與人工驗證通過 |
| Web Phase 1B：Visual Action Plan | **PASS** | 來源框、目的地箭頭、行動清單與完成狀態已完成並人工驗證 |
| Web Phase 2A：AI 整理預覽 | **IMPLEMENTED_NOT_LIVE_TESTED** | 功能已實作，但未執行 OpenAI 付費圖片編輯；UI 顯示「⚠ 此功能尚未實際測試」 |
| Android APK | **APK_READY_FOR_OWNER_RETEST** | APK 可建置、相機與相簿入口可用；NVIDIA 回應格式韌性已修正，等待最新版本實機複驗 |

已知重要提交：

- Phase 1B：`e27be005b1387011583e548f677d4ebdfdfa8892`
- Phase 2A：`6711ea7b54ecfac805b5f84360928e1aba32917f`

## 核心功能

- 單張 JPEG / PNG / WebP 房間照片輸入
- Web 上傳、Android Photo Picker 與「直接拍照」
- EXIF 方向校正、影像限制檢查、等比例縮放
- 主目標：整理 / 美觀 / 兩者兼顧
- 風格：簡潔乾淨 / 溫暖自然 / 保留目前風格
- 是否允許購買新物品
- 是否允許移動大型家具
- 必須保留的物品或家具
- 其他實際限制
- NVIDIA NIM `z-ai/glm-5.3-flash` 房間照片分析
- 嚴格 Schema + 語意驗證
- 照片觀察證據與近似 Bounding Boxes
- 優先建議與 Visual Action Plan
- `未處理 / 已完成 / 暫不處理` 狀態與進度
- OpenAI Image Edit「AI 整理預覽」功能骨架（尚未 live test）
- Android 模型下拉選單與 API_KEY 輸入欄位

## 系統架構

```text
                           ┌────────────────────────────┐
                           │        Cloud AI APIs       │
                           │                            │
                           │ NVIDIA NIM                 │
                           │ z-ai/glm-5.3-flash         │
                           │        │                   │
                           │        └─ 房間照片分析     │
                           │                            │
                           │ OpenAI Image API           │
                           │ gpt-image-2.5-sunburst     │
                           │        └─ AI 整理預覽      │
                           └────────────▲───────────────┘
                                        │ HTTPS
                  ┌─────────────────────┴─────────────────────┐
                  │                                           │
        ┌─────────┴──────────┐                     ┌──────────┴──────────┐
        │ Web Application    │                     │ Android Application  │
        │ FastAPI + JS/CSS   │                     │ Kotlin + Compose      │
        │                    │                     │                       │
        │ Browser            │                     │ Photo Picker / Camera │
        │   ↓                │                     │   ↓                   │
        │ Image Service      │                     │ Image Pipeline        │
        │   ↓                │                     │   ↓                   │
        │ Analysis Service   │                     │ NVIDIA Client         │
        │   ↓                │                     │   ↓                   │
        │ Validation         │                     │ Validation            │
        │   ↓                │                     │   ↓                   │
        │ Visual Action Plan │                     │ Visual Action Plan    │
        └────────────────────┘                     └───────────────────────┘
```

## AI Provider

### NVIDIA NIM — 房間分析

- 模型：`z-ai/glm-5.3-flash`
- Endpoint：`https://integrate.api.nvidia.com/v1/chat/completions`
- 用途：多模態房間理解、照片觀察、整理建議、Bounding Boxes、Visual Action Plan
- 推理設定：`reasoning_effort="low"`
- Chat template：`clear_thinking=true`
- Android 目前 timeout：connect 10s / write 30s / read 300s / total 360s
- 不使用自動重試

### OpenAI Image API — AI 整理預覽

- 設定模型：`gpt-image-2.5-sunburst`
- 用途：根據原始房間照片 + 已核准 Phase 1B 建議產生「AI 整理預覽」
- 狀態：**已實作但未 live test**
- Web / Android 皆必須明確顯示：`⚠ 此功能尚未實際測試`
- 開發期間 OpenAI 遠端請求：`0`
- 開發期間 OpenAI API 成本：`$0`

## 圖片處理規則

Web Phase 1A 原始規則：

- 最大上傳：10 MiB
- 最大解碼像素：25,000,000 pixels
- Provider 圖片長邊：最大 2048 px
- EXIF Orientation 校正
- 保留長寬比
- Provider 圖片移除 metadata
- 不預設永久保存房間照片

Android 使用相同方向校正、驗證與縮放概念；相機拍攝使用 App 私有快取，不主動存入手機相簿。

## 回應契約與安全驗證

模型回應包含：

- `input_suitability`
- `room_summary`
- `observations[]`
- `recommendations[]`
- `uncertainties[]`
- `limitations[]`

主要驗證：

- Observation / Recommendation ID 不可重複
- 建議引用的 Observation 必須存在
- Bounding box 必須符合標準化座標規則
- 最多 5 個主要建議
- 禁止購買時，不得要求新購物品或材料
- 禁止移動大型家具時，不得要求大型家具搬動
- 目的地不可憑空捏造
- 房間牆面、門、窗與固定結構不得更動
- 無尺寸證據時不得宣稱物品「一定放得下」
- `limitations` / `uncertainties` 缺席或 `null` 時可正規化為空陣列；核心語意欄位仍嚴格必填

## Web 啟動

專案路徑：

```text
D:\0TIGER\6months\PythonAPIDevelopment\Tiger-AI-RoomStyler
```

Python：

```text
D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe
```

啟動範例：

```powershell
Set-Location 'D:\0TIGER\6months\PythonAPIDevelopment\Tiger-AI-RoomStyler'
& 'D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 18089
```

實際 Port 可依環境調整；不要終止無關程序來搶 Port。

## Web 環境變數

```env
NVIDIA_API_KEY=...
ROOMSTYLER_VISION_MODEL=z-ai/glm-5.3-flash

# AI 整理預覽（可選；尚未 live test）
OPENAI_API_KEY=...
ROOMSTYLER_IMAGE_MODEL=gpt-image-2.5-sunburst
```

作業系統環境變數優先於專案 `.env`。若 shell 內存在舊的 `NVIDIA_API_KEY`，可能覆蓋專案 `.env` 中有效的 Key。

## Android

Android 專案位於：

```text
android/
```

技術：

- Kotlin
- Jetpack Compose
- Android Photo Picker
- `ActivityResultContracts.TakePicture`
- `FileProvider`
- App 私有快取
- 直接 HTTPS 呼叫雲端 AI API

Android App 不依賴 Windows FastAPI Server，也沒有嵌入 Python。

### Android API Key

- 使用者在 App 內輸入
- 遮罩顯示
- 切換模型時清除
- 僅保存在記憶體
- 不寫入 APK、resources、Gradle 或 BuildConfig

### 最新 Android 驗證狀態

最新版本：`0.1.6-optional-lists`（`versionCode=7`）

- Camera：已能顯示「直接拍照」並回傳預覽
- Photo Picker：可用
- NVIDIA 連線：已成功取得模型回應
- 目前最新修正：`limitations` / `uncertainties` 缺失時正規化為 `[]`
- 最新 APK 等待屋主實機重測，因此 **Android NVIDIA Analysis 尚未正式標 PASS**

> 若後續已完成新版實機驗證，請同步更新本 README 的 Android 狀態。

## Android APK

預設輸出：

```text
D:\0TIGER\6months\PythonAPIDevelopment\Tiger-AI-RoomStyler\dist\Tiger-AI-RoomStyler-debug.apk
```

Package：

```text
com.tigerai.roomstyler
```

## 隱私與安全

- 本專案沒有本機 AI 推論模型
- NVIDIA / OpenAI 分析會將圖片送至對應雲端服務
- API Key 不應寫入 Git 或 APK
- 不記錄 Authorization header、API Key、圖片 base64 或完整私人模型回應
- Room photo 不預設永久保存
- Android 相機照片使用私有快取並清理暫存檔
- AI 整理預覽必須標示為生成式模擬，不得描述成確定的實際整理成果

## 已知限制

1. 單張照片無法證明房間尺寸、承重、隱藏空間與完整動線。
2. Bounding boxes 為模型提供的近似視覺證據，不是精密物件偵測標註。
3. NVIDIA 雲端推論延遲可能受模型排隊、網路與推理時間影響。
4. Android 最新 NVIDIA Schema 修正仍待屋主最新版本實機複驗。
5. OpenAI AI 整理預覽功能尚未真實呼叫，模型相容性、生成品質與保留房間幾何能力未驗證。
6. Visual Action Plan 的完成狀態目前主要為本機 UI 狀態，未設計帳號或跨裝置同步。

## 專案原則

> **專案成功是唯一標準。**

- 只修真正阻礙成功的問題
- 不做無關重構
- 不因測試通過就宣稱未驗證功能已成功
- 不以 mock 測試取代真實視覺驗證
- 未實測功能必須在 UI 與文件中明確標記
- 不必要的付費 API 呼叫不執行
