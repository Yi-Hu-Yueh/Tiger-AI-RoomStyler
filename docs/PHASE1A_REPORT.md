# Phase 1A-R NVIDIA 遷移驗證報告

| 閘門 | 狀態 | 證據／備註 |
|---|---|---|
| Implementation | PASS | 活動路徑改為 NVIDIA NIM；實際 JPEG Base64 隨單次請求傳送。保留 Pydantic、語意限制、圖片前處理、UI、證據標註及舊結果保護；無自動備援或重試。 |
| Automated tests | PASS | 2026-10-06 完整套件 82 passed、0 failed、0 skipped。新增長度截斷拒絕及 UI 計時器／spinner／按鈕收尾測試；供應商皆使用模擬回應。 |
| Runtime smoke | PASS | 2026-10-06：18083 已被其他程序占用，改用 18084；`/health`、首頁、主 JS、新增狀態 JS、主 CSS、新增狀態 CSS 皆 HTTP 200。驗證後只停止本次 uvicorn。 |
| Browser smoke | NOT_RUN | 本次遷移只做 HTTP UI／靜態資源驗證；前一版的瀏覽器結果不作為本版的新驗證。 |
| Live NVIDIA vision API | PASS | 屋主使用真實房間照片完成 NVIDIA GLM-5.3-Flash 分析；請求成功，照片觀察基本正確，證據邊界框對齊正確。 |
| Owner manual validation | PASS | 屋主已完成並通過 `MANUAL_TEST.md` 的 Phase 1A 人工驗證。 |

整體狀態：**PASS**。Phase 1A 實作、自動測試、本機 runtime、真實 NVIDIA API 與屋主人工驗證皆已通過。先前的不完整／截斷回應問題已透過提高輸出預算與精簡輸出契約解決，屋主重測未再發生。

## 設定與實際命令

- 指定 Python：`D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe`。
- 測試：`D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe -m pytest -q`。
- 啟動：`D:\0TIGER\6months\PythonAPIDevelopment\venv_multi_query\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18084`。
- 驗證網址：<http://127.0.0.1:18084>；測試服務已停止，屋主須重新啟動。
- 有效模型：`z-ai/glm-5.3-flash`；端點：`https://integrate.api.nvidia.com/v1/chat/completions`；認證：Bearer；金鑰不出現在報告或前端。

## 官方契約核對與未驗證範圍

2026-10-06 核對 [NVIDIA hosted 模型頁](https://build.nvidia.com/z-ai/glm-5-3-flash)、[模型卡](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-flash)、[API 參考及其嵌入 OpenAPI](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5-3-flash-infer)、[模型專用圖片指南](https://docs.nvidia.com/nim/vision-language-models/latest/get-started/advanced/get-started-glm-5-3-flash.html) 與 [NVIDIA Base64 範例](https://docs.nvidia.com/nemo-helix/v0.7.0/documentation/guardrail-models/tutorials/multimodal-data/)。

模型 ID、hosted endpoint、Bearer、`max_tokens` 與回應欄位已核對。圖片採指南的 `image_url.url` 搭配 NVIDIA 文件記載的 Base64 data URI。hosted GLM 參考的 messages schema 仍只列字串，和圖片指南存在落差；尚未以此 hosted 模型的真實請求證實相容性。

此模型 hosted 參考未記載強制 JSON／`response_format`；本版以精簡欄位契約要求純 JSON，並在 Python 維持完整 Pydantic 與語意驗證，不宣稱伺服器保證 JSON。格式錯誤、截斷、拒絕、HTTP 與網路失敗均回報錯誤，不顯示假建議，也不再次付費修復。

模型卡列最多 8 張圖片與 1,048,576 token 上下文；本版維持一張圖片、10 MiB 上傳、25,000,000 像素及最長邊 2048。hosted API 參考記載 `max_tokens` 為大於等於 1 的整數，達到該值就停止生成，但未列模型最大輸出值；程式將輸出預算由 4096 調高為既有設定上限 16384。後續真實 Phase 1B 分析兩次超過原本 90 秒的讀取上限，因此將有界 NVIDIA 回應讀取 timeout 調整為 180 秒；未增加重試或輸出 token。

測試涵蓋實際請求圖片位元、endpoint／model／認證、單次呼叫、缺少金鑰、JSON／schema 錯誤、認證／權限／配額／限流／逾時／網路／服務錯誤、拒絕與截斷、忽略 reasoning_content、限制違反、無假備援，以及 API 回應預覽與送出的處理後 JPEG 完全一致。所有這些是離線模擬證據，不能證明模型正確理解照片。

未新增套件、未更動共享 Python 環境、未啟用下一階段功能、未 commit 或 push。

## 非阻斷限制

當「允許購買」關閉時，線材整理建議的措辭可能隱含假設現場已有束帶、固定夾等材料。這不影響本次 Phase 1A 驗證結果，但屋主執行前仍須確認現有材料；該措辭不得視為購買授權。
