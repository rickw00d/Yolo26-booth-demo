# YOLO26 实时 AI 视觉展示

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

这是一套用 USB 摄像头做实时物体识别的展位演示程序。前端是浏览器全屏仪表盘,后端用 FastAPI,AI 全部在本机运行(Ultralytics YOLO26/YOLOE 加上 Ollama 视觉语言模型),不需要联网。
在 Windows 笔记本(RTX 4060 8GB)上开发,已移植到 NVIDIA GB10 并实机测试。

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
| 摄像头 / 视频流 | 在 USB 摄像头和直播视频流(例如 YouTube 直播)之间切换 | `C` |
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
- 换摄像头:修改 `config.yaml` 的 `camera.index`。改用串流或视频文件请见[串流与视频文件](#串流与视频文件)。
- 默认语言:修改 `config.yaml` 的 `ui.language`(`zh-TW`、`zh-CN` 或 `en`)。

## 串流与视频文件

视频来源除了 USB 摄像头,也可以是网络串流或视频文件。在 `config.yaml` 设置 `camera.stream`,然后按 `C` 或点击侧边栏的“视频来源”按钮,就能在摄像头(`camera.index`)和视频流之间切换。`camera.stream` 留空时不显示按钮;设置 `start_with_stream: true` 则启动时先显示视频流。

| 来源 | 示例 |
|---|---|
| IP 摄像头(RTSP,走 TCP) | `rtsp://用户名:密码@192.168.1.10:554/stream1` |
| YouTube 直播,或内嵌 YouTube 的网页(用 yt-dlp 解析) | `https://www.youtube.com/watch?v=…`、`https://guideme24.com/products/e369` |
| 直接的媒体网址 | `https://…/live.m3u8`、`http://…/video.mjpg` |
| 本地视频文件(循环播放) | `videos/booth_loop.mp4` |

`camera.stream` 默认是时代广场直播。切到视频流约 2 秒、切回摄像头约 6.5 秒(USB 摄像头本身打开较慢),中间会显示“连接中…”。

API:`POST /api/camera/toggle` 等同按 `C`。`POST /api/camera` 内容 `{"index": "<网址或文件>"}` 可切到任何来源,`{"index": 0}` 切回摄像头。

- YouTube 直播每隔几秒才送一段视频,所以串流会先缓冲 `stream_buffer_s`(6 秒)再以固定速率播放。已在 GB10 上用上面的时代广场直播测试:连续 60 秒保持 30 fps、没有卡顿,整个程序约 33 FPS。
- 串流不做镜像(`stream_mirror: false`)。网址中的用户名、密码与 token 不会出现在日志和仪表盘上。
- 串流需要网络,展位就不再是完全离线。yt-dlp 依赖 YouTube 网站,可能无预警失效,请保留 USB 摄像头作为备用。
- **播放授权**:请先确认可以公开播放该串流。YouTube 条款限制在官方播放器以外访问,展位屏幕也算公开播放。用自己的 IP 摄像头就没有这两个问题。
- 物品挑战和问 AI 是为站在镜头前的来宾设计的,用在街景不太合适。远景中的人很小,可把 `imgsz` 调高(例如 1280)提升检测。

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
| `config.gb10.yaml` | GB10 平台配置(叠加在 config.yaml 上) |
| `tools/` | 环境检查、预先下载模型、TensorRT 导出 |
| `setup_gb10.sh` / `start_demo.sh` / `deploy/` / `docker/` | Linux 安装、启动、开机自启、Docker 备选方案 |
| `app/camera.py` | 多线程读取(USB 摄像头、串流或视频文件),断线自动重连、串流缓冲 |
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

GB10(DGX Spark、MSI EdgeXpert 等)是 ARM64 架构,操作系统是 DGX OS(Ubuntu)。程序本身跨平台,差异都集中在 [config.gb10.yaml](config.gb10.yaml)(只写跟 `config.yaml` 不同的字段,启动时叠加上去)和安装脚本。

### 步骤

```bash
git clone https://github.com/rickw00d/Yolo26-booth-demo.git && cd Yolo26-booth-demo
./setup_gb10.sh                                              # 系统包、venv、PyTorch cu130、模型下载、环境检查
.venv/bin/python tools/export_trt.py --profile config.gb10.yaml   # 导出 TensorRT(必须在 GB10 本机执行)
./start_demo.sh                                              # 启动,浏览器打开 http://localhost:8000
./deploy/install_autostart.sh                                # 可选:开机自启 + 全屏浏览器
```

- **Ollama**:需要先按[官方说明](https://ollama.com/download/linux)安装。`ornith-1.5:9b` 如果不在 Ollama 在线模型库,要从笔记本导出后再导入(未确认)。
- **环境检查**:`tools/check_env.py` 会实际跑 GPU 运算、测摄像头 FPS、检查字体、Ollama 模型和权重文件,并列出需要处理的项目。
- **Docker 备选方案**:原生安装 PyTorch 或 TensorRT 有问题时,改用 `./docker/run_docker.sh`(Ultralytics 官方 ARM64 镜像,内含 TensorRT)。

### GB10 配置与笔记本的差异

| 项目 | 笔记本 | GB10 |
|---|---|---|
| YOLO 模型 | s 版,用到才加载 | x 版,启动时全部加载 |
| 推理引擎 | PyTorch FP16 | TensorRT FP16(找不到 `.engine` 自动回退到 `.pt`) |
| 人脸模糊 | nano 模型,每 2 帧检测一次 | s 模型,每帧都检测 |
| 翻译模型 | 共用 VLM(显存不够) | 独立的 qwen3.5:2b |
| 摄像头后端 | MSMF | V4L2 |

### GB10 实机验证(DGX OS / Ubuntu 24.04 aarch64,2026-11-26)

| 项目 | 结果 |
|---|---|
| PyTorch | 2.14.1+cu130 aarch64 wheel 可直接安装,GB10 上 CUDA 正常(compute capability 12.1) |
| GPU 测试(`tools/check_env.py`) | FP16 矩阵乘法约 78 TFLOPS |
| Ultralytics | 8.4.219;x 版权重、`yolo26s-pose`、`yoloe-26l-seg` 与 MobileCLIP 文本编码器均可下载 |
| OpenCV | 有 V4L2 与 GStreamer 摄像头后端 |
| 摄像头 | USB 摄像头通过 V4L2 以 1280×720 打开(`camera.index: 0`) |
| Ollama | 0.40.18;已安装 `ornith-1.5:9b`(VLM)与 `qwen3.5:2b`(翻译);程序调用 Ollama 正常 |
| 字体 | 找得到 Noto Sans CJK TC / SC |
| 驱动 | 580.178.04,CUDA 13.0 |

不需要用到 Docker。`setup_gb10.sh` 的 apt 步骤需要 `sudo`,其他步骤普通用户即可执行。

### 备注

- 开放词汇(YOLOE)要能随时换类别,不转 TensorRT,速度会比其他模式慢。
- `nvidia-smi` 的内存在统一内存架构下可能是 N/A,仪表盘会自动改为显示系统内存。
- 参考:[Ultralytics DGX Spark 指南](https://docs.ultralytics.com/guides/nvidia-dgx-spark)

## 展前检查清单

- [ ] 五种模式都切换过,模型已下载
- [ ] 现场灯光下实测识别效果与人脸模糊
- [ ] 拔掉网线再完整操作一次,确认可以离线
- [ ] 连续运行 8 小时以上的压力测试
- [ ] 张贴「本展示不保存图像,人脸自动模糊」告示
- [ ] 排行榜归零:`POST /api/game/reset_board`
