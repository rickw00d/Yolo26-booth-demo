"""環境檢查:到新機器(例如 GB10)第一件事就是跑這支。

    python tools/check_env.py                         # 檢查 config.yaml
    python tools/check_env.py --profile config.gb10.yaml

會檢查 GPU / PyTorch / Ultralytics / TensorRT / 攝影機 / 字型 / OpenCC / Ollama / 模型檔,
最後列出需要處理的項目。有嚴重問題時結束碼為 1。
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "✔", "△", "✘"
problems: list[str] = []


def report(status: str, item: str, detail: str = ""):
    print(f"  {status} {item:<22} {detail}")
    if status == FAIL:
        problems.append(f"{item}:{detail}")


def section(title: str):
    print(f"\n== {title}")


def check_system():
    section("系統")
    report(OK, "作業系統", f"{platform.system()} {platform.release()} ({platform.machine()})")
    py = sys.version_info
    report(OK if py >= (3, 10) else FAIL, "Python", platform.python_version())


def check_torch(cfg):
    section("GPU / PyTorch")
    try:
        import torch
    except ImportError:
        report(FAIL, "PyTorch", "未安裝(GB10:pip install torch torchvision --index-url "
               "https://download.pytorch.org/whl/cu130)")
        return
    report(OK, "PyTorch", f"{torch.__version__}(CUDA {torch.version.cuda})")
    if not torch.cuda.is_available():
        report(FAIL, "CUDA", "torch.cuda.is_available() = False,可能裝到 CPU 版 PyTorch")
        return
    name = torch.cuda.get_device_name(0)
    cap = ".".join(map(str, torch.cuda.get_device_capability(0)))
    report(OK, "GPU", f"{name}(compute capability {cap})")
    try:  # 實際跑一次運算,確認不是「import 得了但跑不動」
        a = torch.randn(2048, 2048, device="cuda", dtype=torch.float16)
        for _ in range(5):      # 暖機:排除 cuBLAS 初始化時間
            a @ a
        torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(20):
            a @ a
        torch.cuda.synchronize()
        tflops = 20 * 2 * 2048 ** 3 / (time.perf_counter() - t) / 1e12
        report(OK, "GPU 運算測試", f"FP16 矩陣乘法約 {tflops:.1f} TFLOPS")
    except Exception as e:
        report(FAIL, "GPU 運算測試", str(e).splitlines()[0])


def check_libs():
    section("套件")
    try:
        import ultralytics
        report(OK, "Ultralytics", ultralytics.__version__)
    except ImportError:
        report(FAIL, "Ultralytics", "未安裝:pip install -r requirements.txt")
    try:
        import tensorrt
        report(OK, "TensorRT", tensorrt.__version__)
    except ImportError:
        report(WARN, "TensorRT", "未安裝(選用;沒有也能跑,只是比較慢)")
    try:
        from app.zhconv import convert
        ok = convert("视频", "zh-TW") == "影片"
        report(OK if ok else WARN, "OpenCC", "繁簡轉換正常" if ok else "已安裝但轉換結果不符預期")
    except Exception as e:
        report(WARN, "OpenCC", f"無法使用:{e}")
    import cv2
    from cv2 import videoio_registry as vr
    backends = [vr.getBackendName(b) for b in vr.getCameraBackends()]
    report(OK, "OpenCV", f"{cv2.__version__},攝影機後端:{', '.join(backends)}")


def check_fonts():
    section("字型")
    from app import render
    for lang in ("zh-TW", "zh-CN"):
        f = render.FONTS.get(lang)
        report(OK if f else FAIL, f"{lang} 字型",
               " ".join(f.getname()) if f else "找不到;Linux 請執行 sudo apt install fonts-noto-cjk")


def check_cameras(cfg):
    section("攝影機")
    import cv2
    from app.camera import Camera
    if platform.system() == "Linux" and shutil.which("v4l2-ctl"):
        out = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True).stdout
        for line in out.strip().splitlines():
            print(f"      {line}")
    cam_cfg = dict(cfg["camera"])
    want = cam_cfg.get("index", 0)
    found_want = False
    for idx in range(0, 6):
        cam_cfg["index"] = idx
        cam = Camera(cam_cfg)
        cap = cam._open()
        if cap is None:
            continue
        n, t = 0, time.perf_counter()
        while time.perf_counter() - t < 1.5:
            n += cap.read()[0]
        fps = n / (time.perf_counter() - t)
        cap.release()
        mark = "(設定使用中)" if idx == want else ""
        found_want |= idx == want
        report(OK if fps >= 20 else WARN, f"攝影機 #{idx}{mark}",
               f"{cam.actual_size[0]}×{cam.actual_size[1]},實測 {fps:.0f} FPS"
               + ("" if fps >= 20 else ";幀率偏低,檢查 MJPG 支援、USB 3 埠或光線"))
    if isinstance(want, int) and not found_want:
        report(FAIL, "設定的攝影機", f"camera.index = {want} 打不開")


def check_ollama(cfg):
    section("Ollama")
    o = cfg.get("ollama", {})
    url = o.get("url", "http://127.0.0.1:11434").rstrip("/")
    try:
        tags = json.loads(urllib.request.urlopen(f"{url}/api/tags", timeout=3).read())
    except Exception as e:
        report(FAIL, "Ollama 服務", f"{url} 連不上({e});請安裝並啟動 Ollama")
        return
    names = {m["name"] for m in tags.get("models", [])}
    report(OK, "Ollama 服務", f"{url},已有 {len(names)} 個模型")
    for key in ("vlm_model", "llm_model"):
        m = o.get(key)
        if m:
            report(OK if m in names else FAIL, key, m if m in names else f"{m} 尚未下載:ollama pull {m}")


def check_weights(cfg):
    section("YOLO 模型檔")
    names = dict(cfg["models"])
    names["face"] = cfg.get("privacy", {}).get("model", names["pose"])
    for key, w in names.items():
        if key == "openvocab_fallback" or not w:
            continue
        pt = ROOT / w
        engine = ROOT / (w[:-3] + ".engine") if w.endswith(".pt") else None
        if cfg.get("tensorrt") and engine is not None and key != "openvocab":
            if engine.exists():
                report(OK, key, f"{engine.name}(TensorRT)")
            else:
                report(WARN, key, f"沒有 {engine.name},會用 .pt;執行 tools/export_trt.py 可加速")
        if pt.exists():
            report(OK, key, f"{w}({pt.stat().st_size / 2**20:.0f} MB)")
        else:
            report(WARN, key, f"{w} 尚未下載;執行 tools/prefetch_models.py(需要網路)")


def check_smi():
    section("nvidia-smi")
    smi = shutil.which("nvidia-smi")
    if not smi:
        report(WARN, "nvidia-smi", "找不到;儀表板的 GPU 使用率會顯示 —")
        return
    q = "name,driver_version,utilization.gpu,memory.used,memory.total,temperature.gpu"
    out = subprocess.run([smi, f"--query-gpu={q}", "--format=csv,noheader"],
                         capture_output=True, text=True).stdout.strip()
    report(OK, "nvidia-smi", out)
    if "N/A" in out:
        print("      (記憶體為 N/A 屬正常:GB10 是統一記憶體,儀表板會改顯示系統記憶體)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--skip-camera", action="store_true", help="展示程式執行中時略過(鏡頭會被占用)")
    args = ap.parse_args()
    from app.config import load_config, set_profile
    if args.profile:
        set_profile(args.profile)
    cfg = load_config()
    print(f"設定檔:config.yaml" + (f" + {cfg['_profile']}" if cfg.get("_profile") else ""))
    check_system()
    check_torch(cfg)
    check_libs()
    check_fonts()
    if not args.skip_camera:
        check_cameras(cfg)
    check_ollama(cfg)
    check_weights(cfg)
    check_smi()
    print("\n== 結果")
    if problems:
        print("需要處理:")
        for p in problems:
            print(f"  ✘ {p}")
        sys.exit(1)
    print("  ✔ 沒有嚴重問題(△ 為建議項目)")


if __name__ == "__main__":
    main()
