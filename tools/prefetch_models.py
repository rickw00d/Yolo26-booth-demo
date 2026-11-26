"""預先下載設定中所有 YOLO 權重與 YOLOE 文字編碼器(需要網路,展前在有網路的地方執行一次)。

    python tools/prefetch_models.py --profile config.gb10.yaml
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # Ultralytics 會把權重下載到目前目錄


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile")
    args = ap.parse_args()
    from app.config import load_config, set_profile
    if args.profile:
        set_profile(args.profile)
    cfg = load_config()
    from ultralytics import YOLO, YOLOE

    names = cfg["models"]
    weights = [names["detect"], names["segment"], names["pose"],
               cfg.get("privacy", {}).get("model", names["pose"])]
    for w in dict.fromkeys(weights):
        print(f"下載 / 確認 {w}")
        YOLO(w)
    for w in (names.get("openvocab"), names.get("openvocab_fallback")):
        if not w:
            continue
        try:
            print(f"下載 / 確認 {w}(含文字編碼器)")
            m = YOLOE(w)
            m.set_classes(["person"], m.get_text_pe(["person"]))   # 觸發 MobileCLIP 下載
            break
        except Exception as e:
            print(f"  {w} 失敗:{e}")
    print("完成。")


if __name__ == "__main__":
    main()
