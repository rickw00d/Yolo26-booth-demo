# YOLO26 实时 AI 视觉展示

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

这是一套用 USB 摄像头做实时物体识别的展位演示程序。前端是浏览器全屏仪表盘,后端用 FastAPI,AI 全部在本机运行(Ultralytics YOLO26/YOLOE 加上 Ollama 视觉语言模型),不需要联网。
目前在 Windows 笔记本(RTX 4060 8GB)上开发,之后会移植到 NVIDIA GB10。

## 功能

| 功能 | 说明 | 快捷键 |
|---|---|---|
| 目标检测 | YOLO26 检测 80 类物品,附追踪 ID、轨迹、中英文标签 | `1` |
| 实例分割 | 物体轮廓半透明遮罩 | `2` |
| 人体姿态 | 17 点骨架 | `3` |
| 多模型同时运行 | 分割加姿态两个模型同时跑 | `4` |
| 自由识别(开放词汇) | 输入「红色杯子、眼镜」等任意文本,由 LLM 翻成英文后交给 YOLOE,不需要重新训练 | `5` |
| AI 问答 | 本机 VLM 看着当下画面回答,逐字流式显示;中文回答实时转换字形与用语:繁体用 OpenCC `s2twp`(台湾用语),简体用 `tw2sp`(大陆用语) | `D`(描述画面) |
| 物品挑战 | 30 秒内把指定的 5 样物品拿到镜头前,有计分和排行榜 | `G` |
| 性能对比 | 同一张画面分别用 CPU 和 GPU 推理 | `B` |
| 人脸模糊 | 对所有人脸打马赛克,包含远处和背对镜头的人 | `P` |
| 语言切换 | 繁体中文/简体中文/英文;界面、画面上的标签、AI 回答语言一起切换 | `L` |
| 待机吸引画面 | 一段时间没检测到人就显示招呼字幕 | 自动 |
| 隐藏侧栏 / 全屏 / 截图 | 截图会保存到 `snapshots/` | `H` / `F` / `S` |

## 快速开始(Windows)

```powershell
python -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
# 需要一个支持影像的 Ollama 模型;默认设置使用 ornith-1.5:9b(Apache 2.0)
# 也可以改用其他视觉模型,例如 `ollama pull qwen2.5vl:7b`,再修改 ollama.vlm_model
.venv\Scripts\python run.py
```

接着用浏览器开 <http://localhost:8000>,按 `F` 进入全屏。
展会现场使用时改运行 `start_demo.bat`,程序崩溃会自动重启。

- 第一次运行会自动下载 YOLO 模型。**展前请在有网络的环境把五种模式都切过一次。**
- 换摄像头:修改 `config.yaml` 的 `camera.index`。
- 默认语言:修改 `config.yaml` 的 `ui.language`(`zh-TW`、`zh-CN` 或 `en`)。

## 人脸模糊

- 用姿态模型的脸部关键点(鼻、眼、耳)定位头部,不需要额外的人脸模型。
- 检测到「人」但找不到脸部关键点时(远处、背对、侧脸),改用人框顶部当作头部位置,宁可多模糊。
- 会保留最近几个帧的位置一起模糊,避免漏检测时人脸闪现。
- `privacy.blur_vlm: true` 时,送给 VLM 的画面也会先模糊。
- 限制:非常小或被遮住的人如果完全没被检测到,就不会被模糊。

## 架构

```
摄像头线程 ─最新帧─▶ 推理线程(YOLO track + 找人脸)─▶ 绘图线程(模糊→绘图→JPEG)─▶ /stream
                                                                       └─ 统计 / 游戏判定 ─▶ /api/stats
浏览器 ── /api/ask ──▶ Ollama VLM(流式)
       ── /api/vocab ─▶ Ollama 翻译 → YOLOE.set_classes()
```

推理和绘图在不同线程并行,GPU 不必等待 CPU 绘图与编码。

| 文件 | 用途 |
|---|---|
| `config.yaml` | 所有可调参数 |
| `app/camera.py` | 多线程读取,断线自动重连 |
| `app/engine.py` | 模型管理、推理、绘图管线、统计、CPU/GPU 对比 |
| `app/privacy.py` | 人脸模糊 |
| `app/render.py` | 霓虹角框、遮罩、骨架、轨迹、中文字 |
| `app/llm.py` | Ollama 客户端(中英文提示词) |
| `app/zhconv.py` | 流式繁简转换(OpenCC `s2twp`/`tw2sp`,例:视频↔影片、软件↔软体) |
| `app/game.py` | 物品挑战与排行榜 |
| `app/server.py` | FastAPI 路由(`/api/debug/threads` 可在画面卡住时查看各线程状态) |
| `static/` | 前端(纯 HTML/JS,不依赖 CDN,可离线) |

## 笔记本实测(RTX 4060 Laptop 8GB,1280×720,2026-11-26)

| 项目 | 结果 |
|---|---|
| 目标检测 yolo26s(无人脸模糊) | 约 30 FPS,推理 13~17 ms |
| 打开人脸模糊、画面有人 | 约 15~24 FPS |
| CPU vs GPU | 82 ms vs 13.8 ms,约 5.9 倍 |
| 中文词汇翻译 | 约 1.2~1.5 秒 |

### 8GB 显存的 VLM 比较(与 YOLO 同时运行,同一张画面)

| 模型 | 显存占用 | 生成速度 | 热启动回答 | 质量观察 |
|---|---|---|---|---|
| qwen2.5vl:7b | 5.2 GB | 32 tok/s | 1~2.5 秒 | 把纸箱上的「msi」误读成「i2m」;偶尔出现「這裏」这类非台湾用字 |
| qwen3.5:2b | 2.3 GB | 64 tok/s | 约 0.8 秒 | 最快;描述简短,同样误读成「i2m」 |
| **ornith-1.5:9b(默认,Qwen3.5 架构,Apache 2.0)** | 5.5 GB | 35~40 tok/s | 约 2 秒 | 最准确:正确读出「msi」、物品最完整,也注意到背景人物;第一次读图较慢(约 10 秒) |

已知限制:
- 8GB 同时放 VLM 和 YOLO 已接近上限(约 7.5GB),所以翻译共用 VLM,不另外加载 LLM。
- Windows 上必须用 MSMF 后端;DSHOW 在 720p 只有 10fps。

## 移植到 GB10

GB10 是 ARM64 架构,操作系统是 DGX OS(Ubuntu)。程序本身跨平台,主要差异在环境安装。

1. **PyTorch**:建议使用 NVIDIA NGC 的 PyTorch 容器,或 aarch64 加 CUDA 13 的 wheel。版本对应**未确认**,请以 NVIDIA 官方文档为准。
2. **修改 `config.yaml`**:
   ```yaml
   camera: { backend: v4l2, index: 0 }
   models: { detect: yolo26x.pt, segment: yolo26x-seg.pt, pose: yolo26x-pose.pt, openvocab: yoloe-26l-seg.pt }
   preload: true
   privacy: { model: yolo26s-pose.pt, every_n: 1 }
   ollama: { vlm_model: <更大的 VLM>, llm_model: <独立的 LLM> }
   ui: { device_label: "NVIDIA GB10" }
   ```
3. **TensorRT(可选)**:`yolo export model=yolo26x.pt format=engine half=True`,再把模型路径改成 `.engine`。
4. **中文字体**:`sudo apt install fonts-noto-cjk`。繁体标签使用 TC 字形,简体标签使用 SC 字形。
5. **内存显示**:`nvidia-smi` 返回 N/A 时,仪表盘会自动改为显示统一内存。
6. **开机自动启动**:用 systemd 运行 `python run.py`,搭配 Chromium `--kiosk http://localhost:8000`。

## 展前检查清单

- [ ] 五种模式都切换过,模型已下载
- [ ] 现场灯光下实测识别效果与人脸模糊
- [ ] 拔掉网线再完整操作一次,确认可以离线
- [ ] 连续运行 8 小时以上的压力测试
- [ ] 张贴「本展示不保存图像,人脸自动模糊」告示
- [ ] 排行榜归零:`POST /api/game/reset_board`
