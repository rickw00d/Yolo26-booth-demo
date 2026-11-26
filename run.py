"""啟動展示:python run.py  然後用瀏覽器開 http://localhost:8000 (F11 全螢幕)"""
import logging

import uvicorn

from app.config import load_config

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    cfg = load_config()["server"]
    uvicorn.run("app.server:app", host=cfg.get("host", "0.0.0.0"),
                port=cfg.get("port", 8000), log_level="warning")
