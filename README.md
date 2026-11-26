# YOLO26 Real-time AI Vision Booth Demo

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

This is a trade-show booth demo that runs real-time object recognition from a USB camera. The front end is a full-screen browser dashboard and the back end is FastAPI. All AI runs on the device (Ultralytics YOLO26/YOLOE plus an Ollama vision-language model), so no internet connection is needed.
It is developed on a Windows laptop (RTX 4060 8GB) and will be ported to NVIDIA GB10.

## Features

| Feature | Description | Key |
|---|---|---|
| Object detection | YOLO26 detects 80 classes, with track IDs, motion trails and bilingual labels | `1` |
| Instance segmentation | Translucent object masks | `2` |
| Human pose | 17-keypoint skeleton | `3` |
| Multi-model | Segmentation and pose models run together | `4` |
| Open vocabulary | Type anything ("red cup, glasses", in English or Chinese). An LLM translates it and YOLOE finds it, with no retraining | `5` |
| Ask AI | An on-device VLM looks at the live frame and streams its answer. Chinese answers are converted on the fly with OpenCC: `s2twp` for Traditional (Taiwan), `tw2sp` for Simplified (Mainland) | `D` (describe) |
| Item challenge | Show 5 requested items to the camera within 30 s, with score and leaderboard | `G` |
| CPU vs GPU | Runs the same frame on CPU and on GPU | `B` |
| Face blur | Pixelates every face, including people far away or facing away | `P` |
| Language toggle | Traditional Chinese / Simplified Chinese / English. Switches the UI, the on-video labels and the AI answer language together | `L` |
| Idle attract screen | Shows a greeting when nobody has been seen for a while | auto |
| Hide panel / Fullscreen / Snapshot | Snapshots are saved to `snapshots/` | `H` / `F` / `S` |

## Quick start (Windows)

```powershell
python -m venv .venv
.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install -r requirements.txt
# A vision-capable Ollama model; the default config uses ornith-1.5:9b (Apache 2.0).
# Any other vision model works too, e.g. `ollama pull qwen2.5vl:7b`, then edit ollama.vlm_model.
.venv\Scripts\python run.py
```

Then open <http://localhost:8000> and press `F` for fullscreen.
At the booth, run `start_demo.bat` instead. It restarts the app automatically if it crashes.

- YOLO weights download on first use. **Before the show, switch through all five modes once while online.**
- To change the camera, edit `camera.index` in `config.yaml`.
- To change the default language, edit `ui.language` in `config.yaml` (`zh-TW`, `zh-CN` or `en`).

## Face blur

- Heads are located from the pose model's face keypoints (nose, eyes, ears), so no extra face model is needed.
- If a person is detected but no face keypoints are found (far away, facing away, in profile), the top of the person box is blurred instead. The design errs on the side of blurring more.
- Face positions from the last few frames are blurred too, so a face does not flash through when a single frame misses it.
- With `privacy.blur_vlm: true`, the frame sent to the VLM is blurred as well.
- Limitation: a person who is not detected at all (very small, or heavily occluded) is not blurred.

## Architecture

```
camera thread ─latest frame─▶ inference thread (YOLO track + face finding) ─▶ render thread (blur → draw → JPEG) ─▶ /stream
                                                                                  └─ stats / game logic ─▶ /api/stats
browser ── /api/ask ──▶ Ollama VLM (streaming)
        ── /api/vocab ─▶ Ollama translation → YOLOE.set_classes()
```

Inference and rendering run in separate threads, so the GPU never waits for the CPU to draw or encode.

| File | Purpose |
|---|---|
| `config.yaml` | All tunable settings |
| `config.gb10.yaml` | GB10 profile (merged on top of config.yaml) |
| `tools/` | Environment check, model prefetch, TensorRT export |
| `setup_gb10.sh` / `start_demo.sh` / `deploy/` / `docker/` | Linux setup, start, autostart, Docker fallback |
| `app/camera.py` | Threaded capture with auto-reconnect |
| `app/engine.py` | Model management, inference, render pipeline, stats, CPU/GPU benchmark |
| `app/privacy.py` | Face blur |
| `app/render.py` | Neon corner boxes, masks, skeletons, trails, CJK text |
| `app/llm.py` | Ollama client (bilingual prompts) |
| `app/zhconv.py` | Streaming Traditional ↔ Simplified conversion (OpenCC `s2twp` / `tw2sp`) |
| `app/game.py` | Item challenge and leaderboard |
| `app/server.py` | FastAPI routes (`/api/debug/threads` shows each thread's stack if the video freezes) |
| `static/` | Front end (plain HTML/JS, no CDN, works offline) |

## Laptop measurements (RTX 4060 Laptop 8GB, 1280×720, 2026-11-26)

| Item | Result |
|---|---|
| Detection, yolo26s (face blur off) | ~30 FPS, 13–17 ms inference |
| Face blur on, people in frame | ~15–24 FPS |
| CPU vs GPU | 82 ms vs 13.8 ms (~5.9×) |
| Chinese → English vocabulary translation | ~1.2–1.5 s |

### VLM comparison on 8GB VRAM (running alongside YOLO, same frame)

| Model | Memory | Generation | Warm answer | Notes |
|---|---|---|---|---|
| qwen2.5vl:7b | 5.2 GB | 32 tok/s | 1–2.5 s | Misread "msi" on a box as "i2m". Occasionally uses non-Taiwanese characters |
| qwen3.5:2b | 2.3 GB | 64 tok/s | ~0.8 s | Fastest. Short answers, also misread "i2m" |
| **ornith-1.5:9b (default, Qwen3.5 architecture, Apache 2.0)** | 5.5 GB | 35–40 tok/s | ~2 s | Most accurate: read "msi" correctly, listed the most items, noticed a background person. Slow first image (~10 s) |

Known limitations:
- 8GB is nearly full with the VLM and YOLO loaded together (~7.5GB), so translation reuses the VLM instead of loading a second LLM.
- On Windows the MSMF backend is required. DSHOW only reaches 10 FPS at 720p.

## Porting to GB10

GB10 (DGX Spark, MSI EdgeXpert, etc.) is ARM64 and runs DGX OS (Ubuntu). The code is cross-platform. Everything that differs lives in [config.gb10.yaml](config.gb10.yaml), which lists only the fields that differ from `config.yaml` and is merged on top at startup, and in the setup scripts.

### Steps

```bash
git clone https://github.com/rickw00d/Yolo26-booth-demo.git && cd Yolo26-booth-demo
./setup_gb10.sh                                              # apt packages, venv, PyTorch cu130, model download, env check
.venv/bin/python tools/export_trt.py --profile config.gb10.yaml   # TensorRT export (must run on the GB10 itself)
./start_demo.sh                                              # start, then open http://localhost:8000
./deploy/install_autostart.sh                                # optional: start on boot + fullscreen kiosk browser
```

- **Ollama**: install it first by following the [official instructions](https://ollama.com/download/linux). If `ornith-1.5:9b` is not in the online Ollama library, export it from the laptop and import it on the GB10 (unverified).
- **Environment check**: `tools/check_env.py` runs a real GPU workload, measures camera FPS, and checks fonts, Ollama models and weight files. It then lists anything that needs fixing.
- **Docker fallback**: if the native PyTorch or TensorRT install gives trouble, use `./docker/run_docker.sh`. It uses the official Ultralytics ARM64 image, which includes TensorRT.

### GB10 vs laptop settings

| Item | Laptop | GB10 |
|---|---|---|
| YOLO models | s size, loaded on demand | x size, all preloaded |
| Inference engine | PyTorch FP16 | TensorRT FP16 (falls back to `.pt` if no `.engine`) |
| Face blur | nano model, every 2nd frame | s model, every frame |
| Translation model | Shares the VLM (not enough VRAM) | Separate qwen3.5:2b |
| Camera backend | MSMF | V4L2 |

### Known risks (not yet verified on GB10 hardware)

- The PyTorch cu130 aarch64 wheels work according to community reports and the Ultralytics docs. The Ultralytics docs also warn that pip builds may not be fully optimized; if anything breaks, switch to Docker.
- Open vocabulary (YOLOE) has to change classes at any time, so it is not converted to TensorRT and runs slower than the other modes.
- On unified memory, `nvidia-smi` may report memory as N/A. The dashboard then shows system memory instead.
- Reference: [Ultralytics DGX Spark guide](https://docs.ultralytics.com/guides/nvidia-dgx-spark)

## Pre-show checklist

- [ ] All five modes switched through once and weights downloaded
- [ ] Detection and face blur tested under the booth lighting
- [ ] Full run with the network cable unplugged, to confirm offline operation
- [ ] Soak test of 8 hours or more
- [ ] Notice posted: "No images are stored; faces are blurred automatically"
- [ ] Leaderboard reset with `POST /api/game/reset_board`
