# YOLO26 即時 AI 視覺展示

[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md)

這是一套用 USB 攝影機做即時物件辨識的攤位展示程式。前端是瀏覽器全螢幕儀表板,後端用 FastAPI,AI 全部在本機執行(Ultralytics YOLO26/YOLOE 加上 Ollama 視覺語言模型),不需要連網。
目前在 Windows 筆電(RTX 4060 8GB)上開發,之後會移植到 NVIDIA GB10。

## 功能

| 功能 | 說明 | 快捷鍵 |
|---|---|---|
| 物件偵測 | YOLO26 偵測 80 類物品,附追蹤 ID、軌跡、中英文標籤 | `1` |
| 實例分割 | 物件輪廓半透明遮罩 | `2` |
| 人體姿態 | 17 點骨架 | `3` |
| 多模型同時運行 | 分割加姿態兩個模型同時跑 | `4` |
| 自由辨識(開放詞彙) | 輸入「紅色杯子、眼鏡」等任意文字,由 LLM 翻成英文後交給 YOLOE,不需要重新訓練 | `5` |
| AI 問答 | 本機 VLM 看著當下畫面回答,逐字串流顯示;中文回答即時轉換字形與用語:繁體用 OpenCC `s2twp`(台灣用語),簡體用 `tw2sp`(大陸用語) | `D`(描述畫面) |
| 物品挑戰 | 30 秒內把指定的 5 樣物品拿到鏡頭前,有計分和排行榜 | `G` |
| 效能對比 | 同一張畫面分別用 CPU 和 GPU 推論 | `B` |
| 人臉模糊 | 對所有人臉打馬賽克,包含遠處和背對鏡頭的人 | `P` |
| 語言切換 | 繁體中文/簡體中文/英文;介面、影像上的標籤、AI 回答語言一起切換 | `L` |
| 待機吸引畫面 | 一段時間沒偵測到人就顯示招呼字幕 | 自動 |
| 隱藏側欄 / 全螢幕 / 截圖 | 截圖會存到 `snapshots/` | `H` / `F` / `S` |

## 快速開始(Windows)

```powershell
python -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
# 需要一個支援影像的 Ollama 模型;預設設定使用 ornith-1.5:9b(Apache 2.0)
# 也可以改用其他視覺模型,例如 `ollama pull qwen2.5vl:7b`,再修改 ollama.vlm_model
.venv\Scripts\python run.py
```

接著用瀏覽器開 <http://localhost:8000>,按 `F` 進入全螢幕。
展場使用時改執行 `start_demo.bat`,程式當掉會自動重啟。

- 第一次執行會自動下載 YOLO 模型。**展前請在有網路的環境把五種模式都切過一次。**
- 換攝影機:修改 `config.yaml` 的 `camera.index`。
- 預設語言:修改 `config.yaml` 的 `ui.language`(`zh-TW`、`zh-CN` 或 `en`)。

## 人臉模糊

- 用姿態模型的臉部關鍵點(鼻、眼、耳)定位頭部,不需要額外的人臉模型。
- 偵測到「人」但找不到臉部關鍵點時(遠處、背對、側臉),改用人框頂部當作頭部位置,寧可多模糊。
- 會保留最近幾個影格的位置一起模糊,避免漏偵測時人臉閃現。
- `privacy.blur_vlm: true` 時,送給 VLM 的畫面也會先模糊。
- 限制:非常小或被遮住的人如果完全沒被偵測到,就不會被模糊。

## 架構

```
攝影機執行緒 ─最新影格─▶ 推論執行緒(YOLO track + 找人臉)─▶ 繪圖執行緒(模糊→繪圖→JPEG)─▶ /stream
                                                                       └─ 統計 / 遊戲判定 ─▶ /api/stats
瀏覽器 ── /api/ask ──▶ Ollama VLM(串流)
       ── /api/vocab ─▶ Ollama 翻譯 → YOLOE.set_classes()
```

推論和繪圖在不同執行緒平行進行,GPU 不必等待 CPU 繪圖與編碼。

| 檔案 | 用途 |
|---|---|
| `config.yaml` | 所有可調參數 |
| `config.gb10.yaml` | GB10 平台設定(疊加在 config.yaml 上) |
| `tools/` | 環境檢查、預先下載模型、TensorRT 匯出 |
| `setup_gb10.sh` / `start_demo.sh` / `deploy/` / `docker/` | Linux 安裝、啟動、開機自動啟動、Docker 備案 |
| `app/camera.py` | 執行緒化讀取,斷線自動重連 |
| `app/engine.py` | 模型管理、推論、繪圖管線、統計、CPU/GPU 對比 |
| `app/privacy.py` | 人臉模糊 |
| `app/render.py` | 霓虹角框、遮罩、骨架、軌跡、中文字 |
| `app/llm.py` | Ollama 用戶端(中英文提示詞) |
| `app/zhconv.py` | 串流繁簡轉換(OpenCC `s2twp`/`tw2sp`,例:視頻↔影片、軟件↔軟體) |
| `app/game.py` | 物品挑戰與排行榜 |
| `app/server.py` | FastAPI 路由(`/api/debug/threads` 可在畫面卡住時查看各執行緒狀態) |
| `static/` | 前端(純 HTML/JS,不依賴 CDN,可離線) |

## 筆電實測(RTX 4060 Laptop 8GB,1280×720,2026-11-26)

| 項目 | 結果 |
|---|---|
| 物件偵測 yolo26s(無人臉模糊) | 約 30 FPS,推論 13~17 ms |
| 開啟人臉模糊、畫面有人 | 約 15~24 FPS |
| CPU vs GPU | 82 ms vs 13.8 ms,約 5.9 倍 |
| 中文詞彙翻譯 | 約 1.2~1.5 秒 |

### 8GB 顯示記憶體的 VLM 比較(與 YOLO 同時運行,同一張畫面)

| 模型 | 記憶體 | 生成速度 | 熱啟動回答 | 品質觀察 |
|---|---|---|---|---|
| qwen2.5vl:7b | 5.2 GB | 32 tok/s | 1~2.5 秒 | 把紙箱上的「msi」誤讀成「i2m」;偶爾出現「這裏」這類非台灣用字 |
| qwen3.5:2b | 2.3 GB | 64 tok/s | 約 0.8 秒 | 最快;描述簡短,同樣誤讀成「i2m」 |
| **ornith-1.5:9b(預設,Qwen3.5 架構,Apache 2.0)** | 5.5 GB | 35~40 tok/s | 約 2 秒 | 最準確:正確讀出「msi」、物品最完整,也注意到背景人物;第一次讀圖較慢(約 10 秒) |

已知限制:
- 8GB 同時放 VLM 和 YOLO 已接近上限(約 7.5GB),所以翻譯共用 VLM,不另外載入 LLM。
- Windows 上必須用 MSMF 後端;DSHOW 在 720p 只有 10fps。

## 移植到 GB10

GB10(DGX Spark、MSI EdgeXpert 等)是 ARM64 架構,作業系統是 DGX OS(Ubuntu)。程式本身跨平台,差異都集中在 [config.gb10.yaml](config.gb10.yaml)(只寫跟 `config.yaml` 不同的欄位,啟動時疊加上去)和安裝腳本。

### 步驟

```bash
git clone https://github.com/rickw00d/Yolo26-booth-demo.git && cd Yolo26-booth-demo
./setup_gb10.sh                                              # 系統套件、venv、PyTorch cu130、模型下載、環境檢查
.venv/bin/python tools/export_trt.py --profile config.gb10.yaml   # 匯出 TensorRT(必須在 GB10 本機執行)
./start_demo.sh                                              # 啟動,瀏覽器開 http://localhost:8000
./deploy/install_autostart.sh                                # 選用:開機自動啟動 + 全螢幕瀏覽器
```

- **Ollama**:需要先依[官方說明](https://ollama.com/download/linux)安裝。`ornith-1.5:9b` 如果不在 Ollama 線上模型庫,要從筆電匯出後再匯入(未確認)。
- **環境檢查**:`tools/check_env.py` 會實際跑 GPU 運算、量攝影機 FPS、檢查字型、Ollama 模型和權重檔,並列出需要處理的項目。
- **Docker 備案**:原生安裝 PyTorch 或 TensorRT 有問題時,改用 `./docker/run_docker.sh`(Ultralytics 官方 ARM64 映像檔,內含 TensorRT)。

### GB10 設定和筆電的差異

| 項目 | 筆電 | GB10 |
|---|---|---|
| YOLO 模型 | s 版,用到才載入 | x 版,啟動時全部載入 |
| 推論引擎 | PyTorch FP16 | TensorRT FP16(找不到 `.engine` 自動退回 `.pt`) |
| 人臉模糊 | nano 模型,每 2 個影格偵測一次 | s 模型,每個影格都偵測 |
| 翻譯模型 | 共用 VLM(顯示記憶體不夠) | 獨立的 qwen3.5:2b |
| 攝影機後端 | MSMF | V4L2 |

### 已知風險(未在 GB10 實機驗證)

- PyTorch cu130 aarch64 wheel 依社群與 Ultralytics 文件可用;Ultralytics 文件也提醒 pip 版可能未完全最佳化,有問題就改用 Docker。
- 開放詞彙(YOLOE)要能隨時換類別,不轉 TensorRT,速度會比其他模式慢。
- `nvidia-smi` 的記憶體在統一記憶體架構下可能是 N/A,儀表板會自動改顯示系統記憶體。
- 參考:[Ultralytics DGX Spark 指南](https://docs.ultralytics.com/guides/nvidia-dgx-spark)

## 展前檢查清單

- [ ] 五種模式都切換過,模型已下載
- [ ] 現場燈光下實測辨識效果與人臉模糊
- [ ] 拔掉網路線再完整操作一次,確認可以離線
- [ ] 連續運行 8 小時以上的壓力測試
- [ ] 張貼「本展示不儲存影像,人臉自動模糊」告示
- [ ] 排行榜歸零:`POST /api/game/reset_board`
