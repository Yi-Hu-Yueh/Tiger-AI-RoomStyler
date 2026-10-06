# Tiger AI Room Styler — Phase 1B + Phase 2A

這是一個本機 FastAPI 網頁工具：驗證並校正一張室內照片，在取得明確同意後把實際處理過的圖片位元傳給 NVIDIA 雲端 NIM 的 Z.ai GLM-5.3-Flash，再以繁體中文顯示具照片證據的整理與美學建議。Phase 1B 會在原始照片上標示有證據的行動來源，且僅在目的地也有照片觀察與邊界框時繪製箭頭；同時提供依優先度排序的本機行動清單與完成狀態。

Phase 1B 狀態：**PASS**。Live NVIDIA API 與屋主真實照片人工驗證均已通過；完整自動測試為 **94 passed**。測試期間發現的程序環境金鑰覆蓋 HTTP 403，以及 NVIDIA 回應讀取上限不足所致 HTTP 504，皆已解決。

Phase 2A 狀態：**IMPLEMENTED_NOT_LIVE_TESTED**。成功的 Phase 1B 分析完成後，可選擇將同一張處理後照片、該次核准建議及限制送至 OpenAI Image API 的 `gpt-image-2.5-sunburst` 圖片編輯端點，產生單一「AI 整理預覽」。目前只完成程式與模擬測試（現有完整測試套件 **108 passed**），未呼叫 OpenAI、未花費額度，也不宣稱真實生成效果可用。預覽是生成式模擬，不代表實際整理結果。

## Phase 2A AI 整理預覽

- 僅在 Phase 1B 分析成功且設定 `OPENAI_API_KEY` 後開放按鈕；缺少金鑰不影響應用程式啟動或 Phase 1A/1B 分析。
- 每次請求以雜湊綁定目前處理後照片、完整分析與限制；照片或限制改變後必須重新分析，舊預覽回應不會套到新照片。
- 編輯提示要求保持同一房間、視角、固定結構、目前風格與不確定物品；禁止移動大型家具時保持其位置，禁止購買時不得加入新家具、收納用品、裝飾或其他新物品。
- 每次操作只送一個圖片編輯請求，不重試、不產生多個版本、不切換供應商。網頁會直接顯示「⚠ 此功能尚未實際測試」及生成式結果免責說明。

## Visual Action Plan

- 每項建議會連結到編號行動、建議卡及照片上的來源標記。
- 目的地必須引用本次回應中具有邊界框的照片觀察；無法驗證時不畫箭頭，改以文字列出屋主須確認的事項。
- 行動清單依高、中、低優先度排序，可在「未處理／已完成／暫不處理」之間切換並顯示完成進度；狀態只存在目前頁面記憶體，不使用帳號或資料庫。
- 禁止購買時，不得要求取得新材料；提及束帶、固定夾、收納盒等用品時，必須明確限定使用者已擁有，並提供完全不使用該材料的替代方案。

## 已驗證環境與啟動

- 專案：`D:\0TIGER\6months\PythonAPIDevelopment\Tiger-AI-RoomStyler`
- Python：`D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe`
- 預設網址：<http://127.0.0.1:18083>

沒有 `.env` 時才複製 `.env.example` 為 `.env`。Phase 1A/1B 分析需要 `NVIDIA_API_KEY` 與 `ROOMSTYLER_VISION_MODEL=z-ai/glm-5.3-flash`；Phase 2A 預覽另需 `OPENAI_API_KEY` 與 `ROOMSTYLER_IMAGE_MODEL=gpt-image-2.5-sunburst`。作業系統環境變數優先於 `.env`。金鑰只存伺服器，請勿放入前端程式。未設定 OpenAI 金鑰仍能啟動並使用已設定的 Phase 1A/1B 功能。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

此為單次程序範圍，不會修改系統執行原則。也可直接啟動：

```powershell
D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18083
```

若 18083 已被其他程式占用，不要終止來源不明的程序；可在目前 PowerShell 工作階段設定 `$env:ROOMSTYLER_PORT='18084'` 後執行啟動腳本，並改開啟 <http://127.0.0.1:18084>。

## 設定

`NVIDIA_API_KEY`（分析時必要）、`ROOMSTYLER_VISION_MODEL`（預設 `z-ai/glm-5.3-flash`）、`OPENAI_API_KEY`（只在產生預覽時必要）、`ROOMSTYLER_IMAGE_MODEL`（預設 `gpt-image-2.5-sunburst`）、`ROOMSTYLER_HOST`、`ROOMSTYLER_PORT`、`ROOMSTYLER_PROVIDER_TIMEOUT_SECONDS`、`ROOMSTYLER_PROVIDER_MAX_OUTPUT_TOKENS`，以及三個圖片限制變數都列在 `.env.example`。

照片及使用者限制會傳送至 NVIDIA 雲端服務，可能產生 API 費用，並適用 NVIDIA 服務條款與資料處理政策；不保證零留存。`/health` 只檢查設定有無，不發送付費請求，也不證明金鑰或模型權限有效。

## NVIDIA API 契約（2026-10-06 核對）

- [Hosted 模型與範例](https://build.nvidia.com/z-ai/glm-5-3-flash)：模型 ID `z-ai/glm-5.3-flash`；端點 `POST https://integrate.api.nvidia.com/v1/chat/completions`。
- [模型 API 參考](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-flash-infer)：認證為 `Authorization: Bearer <NVIDIA_API_KEY>`；使用 `messages`、`max_tokens`、`stream=false`，讀取 `choices[0].message.content` 與 `finish_reason`。
- [GLM 圖片範例](https://docs.nvidia.com/nim/vision-language-models/latest/get-started/advanced/get-started-glm-5-3-flash.html) 使用 `content` 陣列與 `image_url.url`；[NVIDIA 多模態資料文件](https://docs.nvidia.com/nemo-helix/v0.7.0/documentation/guardrail-models/tutorials/multimodal-data/) 記載 `data:image/jpeg;base64,...`。本程式在同一請求中傳送處理後的 JPEG 位元，沒有檔案上傳 API、重試或備援路徑。
- 文件落差：GLM hosted 參考的訊息 schema 仍只列字串，模型卡與模型專用 NIM 指南則明確支援圖片；本專案已以屋主核准的真實照片驗證 Base64 圖片在 hosted GLM-5.3-Flash 可用，但仍以實際服務行為與錯誤回應為準。
- hosted 參考未列 `response_format`／強制 JSON Schema 支援，因此不假設支援、不送猜測欄位。提示只附精簡輸出契約，收到後仍執行完整 Pydantic 與既有語意驗證；格式錯誤直接回報，不做第二次修復請求。
- [模型限制](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-flash)：上下文最多 1,048,576 tokens、最多 8 張圖片；本程式只允許一張。官方 hosted 參考只列 `max_tokens >= 1`；未找到此模型明確的單張位元組上限、RPM 或最大輸出 token 值，不把其他模型的限制套用為已確認值。413、429 或截斷回應會清楚報錯。

支援 JPEG、PNG、WebP；上傳上限 10 MiB、解碼上限 25,000,000 像素、供應商圖片最長邊 2048 像素。系統拒絕損毀、動態或偽裝格式的圖片。

## 測試

```powershell
D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe -m pytest -q
```

自動測試使用模擬 NVIDIA 回應；hosted API 相容性與真實照片理解另由已通過的屋主人工驗證確認。完整人工驗證紀錄見 `docs/MANUAL_TEST.md`。共用 Python 3.11.3 與現有套件，未新增或升降級相依套件。

## 已知限制

邊界框是模型提供的近似證據標註，不是精確物件偵測；單張照片無法證明尺寸、承重、隱藏空間或動線全貌。模型可能誤判可見物件，所有建議都必須由屋主對照照片與現場確認。先前的截斷問題已透過將輸出預算由 4096 調高為 16384 並精簡輸出契約解決；程式仍拒絕不完整回應、不自動重送，且只記錄 finish reason、字元數等去識別化診斷資料。Phase 1A 與 Phase 1B 的真實 NVIDIA 分析及屋主人工驗證均已通過。線材整理措辭仍可能在禁止購買時隱含假設現場已有固定材料，屬非阻斷限制，執行前應由屋主確認。完成狀態僅存於目前頁面，重新載入後不保留。
