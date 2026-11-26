"""FastAPI 伺服器:影像串流、統計、模式切換、VLM 問答、小遊戲。"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ROOT, load_config
from .engine import MODES, Engine
from .llm import Ollama

log = logging.getLogger("server")
cfg = load_config()
engine = Engine(cfg)
ollama = Ollama(cfg.get("ollama", {}))
SNAP_DIR = ROOT / "snapshots"


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.start()
    if cfg.get("preload"):
        await asyncio.to_thread(engine.preload)
    asyncio.create_task(ollama.warmup())
    yield


app = FastAPI(title="YOLO26 Demo", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/stream")
def stream():
    def gen():
        seq = -1
        while True:
            seq, jpg = engine.wait_jpeg(seq)
            if jpg is None:
                time.sleep(0.05)
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                   + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/config")
def get_config():
    return {"ui": cfg.get("ui", {}), "modes": MODES,
            "game": {"duration": cfg["game"]["duration"]}}


@app.get("/api/stats")
def stats():
    return {"lang": engine.lang, "stats": engine.stats, "system": engine.system_stats(),
            "game": engine.game.state(), "benchmark": engine.benchmark,
            "vocab": [{"en": e, "zh": z} for e, z in engine.vocab]}


@app.get("/api/health")
async def health():
    return {"ollama": await ollama.health(), "system": engine.system_stats()}


class ModeReq(BaseModel):
    mode: str


@app.post("/api/mode")
def set_mode(req: ModeReq):
    if req.mode not in MODES:
        raise HTTPException(400, f"unknown mode {req.mode}")
    engine.set_mode(req.mode)
    return {"mode": req.mode}


class CamReq(BaseModel):
    index: int


@app.post("/api/camera")
def set_camera(req: CamReq):
    engine.camera.switch(req.index)
    return {"index": req.index}


@app.get("/api/debug/threads")
def debug_threads():
    """除錯用:列出所有執行緒目前的呼叫堆疊(畫面卡住時查原因)。"""
    import sys
    import threading
    import traceback
    names = {t.ident: t.name for t in threading.enumerate()}
    return {names.get(tid, str(tid)): traceback.format_stack(f)[-6:]
            for tid, f in sys._current_frames().items()
            if names.get(tid) in ("engine", "render", "camera")}


class LangReq(BaseModel):
    lang: str


@app.post("/api/lang")
def set_lang(req: LangReq):
    try:
        engine.set_lang(req.lang)
    except ValueError:
        raise HTTPException(400, "lang must be zh-TW, zh-CN or en")
    return {"lang": engine.lang}


class PrivacyReq(BaseModel):
    face_blur: bool


@app.post("/api/privacy")
def set_privacy(req: PrivacyReq):
    engine.set_face_blur(req.face_blur)
    return {"face_blur": req.face_blur}


class VocabReq(BaseModel):
    text: str


@app.post("/api/vocab")
async def set_vocab(req: VocabReq):
    pairs = await ollama.translate_vocab(req.text)
    if not pairs:
        raise HTTPException(400, "empty vocabulary")
    await asyncio.to_thread(engine.set_vocab, pairs[:12])
    engine.set_mode("openvocab")
    return {"vocab": [{"en": e, "zh": z} for e, z in pairs[:12]]}


DEFAULT_QUESTION = {"zh-TW": "請描述你現在看到的畫面", "zh-CN": "请描述你现在看到的画面",
                    "en": "Describe what you see."}


class AskReq(BaseModel):
    question: str = ""


@app.post("/api/ask")
async def ask(req: AskReq):
    raw = engine.latest_raw()
    if raw is None:
        raise HTTPException(503, "camera not ready")
    import cv2
    h, w = raw.shape[:2]
    scale = 960 / max(h, w)  # 縮圖可大幅降低 VLM 延遲
    small = cv2.resize(raw, (int(w * scale), int(h * scale))) if scale < 1 else raw
    jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
    counts = engine.stats.get("counts", {})
    lang = engine.lang
    ctx = (", " if lang == "en" else "、").join(f"{k}×{v}" for k, v in counts.items())
    question = req.question.strip()[:200] or DEFAULT_QUESTION[lang]

    async def gen():
        try:
            async for piece in ollama.ask_stream(question, jpg, ctx, lang):
                yield piece
        except Exception as e:
            log.exception("VLM 失敗")
            yield f"\n[VLM error: {e}]"
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


class GameReq(BaseModel):
    player: str = ""


@app.post("/api/game/start")
def game_start(req: GameReq):
    engine.game.start(req.player)
    return engine.game.state()


@app.post("/api/game/stop")
def game_stop():
    engine.game.stop()
    return engine.game.state()


@app.post("/api/game/reset_board")
def game_reset():
    engine.game.reset_board()
    return engine.game.state()


@app.post("/api/benchmark")
def benchmark():
    engine.run_benchmark()
    return engine.benchmark


@app.get("/api/snapshot")
def snapshot():
    jpg = engine.latest_jpeg()
    if jpg is None:
        raise HTTPException(503, "no frame yet")
    SNAP_DIR.mkdir(exist_ok=True)
    name = time.strftime("snap_%Y%m%d_%H%M%S.jpg")
    (SNAP_DIR / name).write_bytes(jpg)
    return Response(jpg, media_type="image/jpeg",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
