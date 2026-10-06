# Phase 1B Visual Action Plan 驗證報告

整體狀態：**PASS**。

Phase 1A 保持 PASS。Phase 1B 在原始照片上加入有證據的來源框與編號，只有目的地引用有效照片觀察且具有邊界框時才畫箭頭；否則保留文字建議並顯示屋主須確認的事項。行動清單依優先度排序，完成狀態僅存在瀏覽器目前頁面，不使用帳號或資料庫。

結構化回應新增可選的視覺行動、目的地觀察與無購買替代欄位。伺服器會拒絕未知目的地、沒有邊界框的目的地、沒有來源框卻宣稱可視覺化的行動，以及在禁止購買時要求取得新物品或未提供替代方案的材料建議。

## 驗證結果

- Automated tests：**PASS**，完整套件 `94 passed`，包含 Phase 1A 回歸、NVIDIA timeout 設定與錯誤收尾測試。
- Runtime smoke：**PASS**。18083、18084、18085 已被其他程序占用且未終止；改用 18086。`/health`、首頁、主 JS、Visual Action Plan JS、主 CSS 與 Phase 1B CSS 均為 HTTP 200，驗證後只停止本次 uvicorn。
- Browser smoke：**PASS**。本機頁面正確顯示 Phase 1B、NVIDIA GLM-5.3-Flash 狀態、上傳／限制表單與空白工作區；Visual Action Plan DOM、清單、進度及所有新增靜態資源均載入，瀏覽器 console 無 error 或 warning。
- Live NVIDIA API：**PASS**。屋主已使用核准的真實房間照片完成 GLM-5.3-Flash Phase 1B 分析；來源證據、可驗證目的地箭頭、建議連結、響應式對齊、排序、三種處理狀態、完成進度、禁止購買語意及 Phase 1A 回歸結果均通過人工核對。
- Owner manual validation：**PASS**。屋主已完成並通過 `MANUAL_TEST.md` 的 Phase 1B 人工閘門。
- NVIDIA 403：**RESOLVED**。問題是程序環境中的無效金鑰覆蓋專案 `.env`；改以不繼承該變數的啟動程序載入專案憑證後，最小文字驗證取得 HTTP 200。
- NVIDIA 504：**RESOLVED**。原本 90 秒的回應讀取上限對約 85 秒以上的影像推論餘裕不足；已調整為有界 180 秒 read timeout，連線／寫入／連線池仍採較短上限，且沒有新增重試或提高輸出 token。

本階段未加入生成式改造圖、圖片生成、3D、購物、帳號、資料庫、RAG、agents 或 Phase 2 功能。Phase 1B 已完成並關閉；後續階段尚未開始。
