"""啟動展示:python run.py [--profile config.gb10.yaml]
然後用瀏覽器開 http://localhost:8000(F 鍵全螢幕)。"""
import argparse
import logging
import os

import uvicorn

from app.config import load_config, set_profile

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="YOLO26 booth demo")
    ap.add_argument("--profile", help="疊加在 config.yaml 上的平台設定檔,例如 config.gb10.yaml")
    args = ap.parse_args()
    if args.profile:
        set_profile(args.profile)
        os.environ["DEMO_PROFILE"] = args.profile   # 讓 uvicorn 載入的 app 也用同一份設定
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    cfg = load_config()
    if cfg.get("_profile"):
        logging.info("使用平台設定檔:%s", cfg["_profile"])
    srv = cfg["server"]
    uvicorn.run("app.server:app", host=srv.get("host", "0.0.0.0"),
                port=srv.get("port", 8000), log_level="warning")
