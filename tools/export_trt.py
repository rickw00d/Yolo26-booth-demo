"""把設定中的 YOLO 模型匯出成 TensorRT 引擎(.engine),放在 .pt 旁邊。

TensorRT 引擎綁定 GPU 型號與 TensorRT 版本,**必須在要展示的那台機器上執行**,
不能從筆電複製到 GB10。開放詞彙(YOLOE)要能隨時換類別,所以不匯出。

    python tools/export_trt.py --profile config.gb10.yaml
    python tools/export_trt.py --profile config.gb10.yaml --int8   # INT8 更快,但需校正資料、精度略降(未確認)
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    ap.add_argument("--int8", action="store_true")
    ap.add_argument("--force", action="store_true", help="已有 .engine 也重新匯出")
    args = ap.parse_args()
    from app.config import load_config, set_profile
    if args.profile:
        set_profile(args.profile)
    cfg = load_config()
    from ultralytics import YOLO

    names = cfg["models"]
    weights = dict.fromkeys([names["detect"], names["segment"], names["pose"],
                             cfg.get("privacy", {}).get("model", names["pose"])])
    imgsz = cfg.get("imgsz", 640)
    for w in weights:
        engine = ROOT / (w[:-3] + ".engine")
        if engine.exists() and not args.force:
            print(f"略過 {w}:{engine.name} 已存在(--force 重新匯出)")
            continue
        print(f"\n匯出 {w} → {engine.name}(imgsz={imgsz},{'INT8' if args.int8 else 'FP16'})")
        t = time.time()
        out = YOLO(w).export(format="engine", imgsz=imgsz, device=0,
                             **({"int8": True} if args.int8 else {"half": True}))
        if Path(out).resolve() != engine.resolve():
            shutil.move(out, engine)
        print(f"完成,{time.time() - t:.0f} 秒")
    print("\n全部完成。確認 config 的 tensorrt: true,重新啟動後儀表板底部會顯示使用的檔案。")


if __name__ == "__main__":
    main()
