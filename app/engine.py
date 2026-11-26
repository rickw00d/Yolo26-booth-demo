"""推論引擎:讀取最新影格 → 依模式推論 + 追蹤 → 繪圖 → 編碼 JPEG → 更新統計。"""
import logging
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque

import cv2
import numpy as np
import psutil
import torch

from . import render
from .camera import Camera
from .config import ROOT
from .game import Game
from .labels import label, norm_lang
from .zhconv import convert
from .privacy import FaceBlur

log = logging.getLogger("engine")

MODES = ["detect", "segment", "pose", "multi", "openvocab"]
TASKS = {"detect": "detect", "segment": "segment", "pose": "pose"}
MODE_ZH = {"detect": "物件偵測", "segment": "實例分割", "pose": "人體姿態",
           "multi": "多模型同時運行", "openvocab": "開放詞彙(自由輸入)"}

DEFAULT_VOCAB = [("person", "人"), ("glasses", "眼鏡"), ("watch", "手錶"),  # 中文為繁體;簡體介面顯示時會轉換
                 ("lanyard", "識別證吊繩"), ("bottle", "瓶子")]


def pick_device(pref: str) -> str:
    if pref == "auto":
        return "cuda:0" if torch.cuda.is_available() else "cpu"
    return pref


class GpuMonitor:
    """每秒用 nvidia-smi 查詢 GPU 狀態;GB10 統一記憶體可能回報 N/A,改用系統記憶體。"""

    def __init__(self):
        self.stats = {"gpu_util": None, "gpu_mem_used": None, "gpu_mem_total": None,
                      "gpu_temp": None, "gpu_name": None}
        self._smi = shutil.which("nvidia-smi")
        threading.Thread(target=self._loop, daemon=True, name="gpumon").start()

    @staticmethod
    def _num(s):
        try:
            return float(s)
        except ValueError:
            return None

    def _loop(self):
        while True:
            if self._smi:
                try:
                    out = subprocess.run(
                        [self._smi, "--query-gpu=name,utilization.gpu,memory.used,"
                         "memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=3,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    ).stdout.strip().splitlines()[0].split(",")
                    name, util, used, total, temp = [x.strip() for x in out]
                    self.stats = {"gpu_name": name, "gpu_util": self._num(util),
                                  "gpu_mem_used": self._num(used),
                                  "gpu_mem_total": self._num(total),
                                  "gpu_temp": self._num(temp)}
                except Exception:
                    pass
            time.sleep(1)


class Engine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.device = pick_device(cfg.get("device", "auto"))
        self.half = bool(cfg.get("half", True)) and self.device.startswith("cuda")
        # Ultralytics 8.4 起以 quantize 取代 half
        self._prec = {"quantize": 16} if self.half else {}
        self.camera = Camera(cfg["camera"])
        self.game = Game(cfg.get("game", {}))
        self.gpu = GpuMonitor()
        pcfg = cfg.get("privacy", {})
        self.face_blur = FaceBlur(pcfg)
        self.blur_vlm = bool(pcfg.get("blur_vlm", True))
        self.face_every_n = max(1, int(pcfg.get("every_n", 2)))

        self.mode = cfg.get("default_mode", "detect")
        self._models: dict[str, object] = {}
        self._model_lock = threading.Lock()   # 載入 / 換類別 / 推論互斥
        self.vocab = list(DEFAULT_VOCAB)      # [(英文, 中文)]
        self.openvocab_model_name = None
        self.model_files: dict[str, str] = {}   # 設定的權重 → 實際載入的檔案(.pt / .engine)

        self._jpeg = None
        self._raw = None
        self._jpeg_cond = threading.Condition()
        self._jpeg_seq = 0

        self._trails = defaultdict(lambda: deque(maxlen=cfg.get("trail_length", 30)))
        self._track_colors = {}
        self._seen = defaultdict(set)          # 類別 → 看過的追蹤 id(累計人次)
        self.started_at = time.time()
        self.last_person_at = time.time()
        self.stats = {}
        self.benchmark = {"running": False, "result": None}
        self.status = "starting"   # 狀態碼,前端依語言翻譯
        self.lang = norm_lang(cfg.get("ui", {}).get("language", "zh-TW"))
        self._running = False
        # 推論執行緒 → 繪圖執行緒 的交接區(只保留最新一筆,繪圖跟不上就丟舊的)
        self._job = None
        self._job_cond = threading.Condition()

    # ---------- 模型 ----------
    def _load(self, mode: str):
        if mode in self._models:
            return self._models[mode]
        from ultralytics import YOLO, YOLOE
        names = self.cfg["models"]
        self.status = f"loading:{mode}"
        log.info("載入模型:%s", mode)
        if mode == "openvocab":
            model = None
            for w in (names["openvocab"], names.get("openvocab_fallback")):
                if not w:
                    continue
                try:
                    model = YOLOE(w)
                    self.openvocab_model_name = w
                    break
                except Exception as e:
                    log.warning("YOLOE 模型 %s 載入失敗:%s", w, e)
            if model is None:
                raise RuntimeError("開放詞彙模型都無法載入")
            self._apply_vocab(model)
        elif mode == "face":  # 人臉模糊專用的姿態模型(獨立實例,不干擾姿態模式的追蹤)
            model = YOLO(self._weights(self.cfg.get("privacy", {}).get("model", names["pose"])),
                         task="pose")
        else:
            model = YOLO(self._weights(names[mode]), task=TASKS[mode])
        # 暖機,避免第一次推論卡頓
        dummy = np.zeros((480, 640, 3), np.uint8)
        model.predict(dummy, device=self.device, **self._prec,
                      imgsz=self.cfg.get("imgsz", 640), verbose=False)
        self._models[mode] = model
        self.status = "running"
        return model

    def _weights(self, name: str) -> str:
        """tensorrt: true 且同名 .engine 存在時改用 TensorRT 引擎(先用 tools/export_trt.py 匯出)。"""
        if self.cfg.get("tensorrt") and name.endswith(".pt"):
            engine = ROOT / (name[:-3] + ".engine")
            if engine.exists():
                self.model_files[name] = engine.name
                return str(engine)
            log.warning("找不到 %s,改用 %s(請在本機執行 tools/export_trt.py)", engine.name, name)
        self.model_files[name] = name
        return name

    def _apply_vocab(self, model):
        en = [e for e, _ in self.vocab]
        try:
            model.set_classes(en, model.get_text_pe(en))
        except (AttributeError, TypeError):
            model.set_classes(en)
        # set_classes 後追蹤器的類別對應會變,清掉舊狀態
        if getattr(model, "predictor", None) is not None:
            model.predictor = None

    def set_vocab(self, pairs: list[tuple[str, str]]):
        with self._model_lock:
            self.vocab = pairs
            if "openvocab" in self._models:
                self._apply_vocab(self._models["openvocab"])

    def set_lang(self, lang: str):
        self.lang = norm_lang(lang)

    def set_mode(self, mode: str):
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        self._trails.clear()

    def _locate_faces(self, frame, r_pose, r_main=None):
        """人臉位置 = 姿態關鍵點找到的臉 + 主模型偵測到「人」但沒找到臉時的人框頂部。"""
        if not self.face_blur.enabled:
            return []
        faces = list(self._faces_from_pose(frame, r_pose))
        if r_main is not None and r_main.boxes is not None and len(r_main.boxes):
            names = r_main.names
            for (x1, y1, x2, y2), c in zip(r_main.boxes.xyxy.cpu().numpy(),
                                           r_main.boxes.cls.cpu().numpy()):
                if names[int(c)] != "person":
                    continue
                if any(x1 <= f[0] <= x2 and y1 <= f[1] <= y2 for f in faces):
                    continue
                faces.extend(self.face_blur.locate_from_box((x1, y1, x2, y2)))
        return faces

    def _faces_from_pose(self, frame, r_pose):
        if r_pose is None:
            # 每 every_n 個影格才偵測一次,中間沿用上次位置(FaceBlur 的 hold_frames 會補上)
            self._face_tick = getattr(self, "_face_tick", 0) + 1
            if self._face_tick % self.face_every_n and hasattr(self, "_last_faces"):
                return self._last_faces
            r_pose = self._load("face").predict(
                frame, device=self.device, **self._prec, conf=0.25,
                imgsz=self.cfg.get("imgsz", 640), verbose=False)[0]
        if r_pose.keypoints is None or not len(r_pose.keypoints):
            self._last_faces = []
            return []
        boxes = r_pose.boxes.xyxy.cpu().numpy() if r_pose.boxes is not None else None
        self._last_faces = self.face_blur.locate(r_pose.keypoints.data.cpu().numpy(), boxes)
        return self._last_faces

    def set_face_blur(self, on: bool):
        self.face_blur.enabled = on
        self.face_blur.reset()

    def preload(self):
        for m in ("detect", "segment", "pose", "openvocab", "face"):
            with self._model_lock:
                self._load(m)

    # ---------- 主迴圈 ----------
    def start(self):
        self.camera.start()
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="engine").start()
        threading.Thread(target=self._render_loop, daemon=True, name="render").start()

    def _infer(self, model, frame):
        kw = dict(device=self.device, **self._prec, conf=self.cfg.get("conf", 0.4),
                  imgsz=self.cfg.get("imgsz", 640), verbose=False)
        try:
            return model.track(frame, persist=True,
                               tracker=self.cfg.get("tracker", "bytetrack.yaml"), **kw)[0]
        except Exception as e:  # 追蹤失敗時退回單純推論
            log.debug("track 失敗,改用 predict:%s", e)
            return model.predict(frame, **kw)[0]

    def _loop(self):
        last_id = -1
        while self._running:
            fid, frame = self.camera.read()
            if frame is None or fid == last_id:
                time.sleep(0.003)
                continue
            last_id = fid
            mode = "detect" if self.game.active else self.mode
            try:
                with self._model_lock:
                    t0 = time.perf_counter()
                    if mode == "multi":
                        r_main = self._infer(self._load("segment"), frame)
                        r_pose = self._infer(self._load("pose"), frame)
                        models_running = 2
                    else:
                        r_main = self._infer(self._load(mode), frame)
                        r_pose = r_main if mode == "pose" else None
                        models_running = 1
                    faces = self._locate_faces(frame, r_pose, r_main)
                    infer_ms = (time.perf_counter() - t0) * 1000
            except Exception as e:
                log.exception("推論失敗")
                self.status = f"error:{e}"
                time.sleep(0.5)
                continue

            with self._job_cond:
                self._job = (frame, r_main, r_pose, mode, faces, infer_ms, models_running)
                self._job_cond.notify()

    def _render_loop(self):
        """繪圖、JPEG 編碼、統計放在獨立執行緒,與 GPU 推論平行進行。"""
        fps_ema = None
        t_prev = time.perf_counter()
        while self._running:
            with self._job_cond:
                while self._job is None:
                    self._job_cond.wait()
                job = self._job
                self._job = None
            try:
                fps_ema, t_prev = self._render_one(job, fps_ema, t_prev)
            except Exception:
                # 任何錯誤都不能讓繪圖執行緒停掉,否則畫面會凍結
                log.exception("繪圖失敗")

    def _render_one(self, job, fps_ema, t_prev):
        frame, r_main, r_pose, mode, faces, infer_ms, models_running = job
        base = frame
        if self.face_blur.enabled:
            base = frame.copy()
            self.face_blur.apply(base, faces)
        out, summary = self._draw(base, r_main, r_pose, mode)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY,
                                             self.cfg["server"].get("jpeg_quality", 80)])
        if ok:
            with self._jpeg_cond:
                self._jpeg = buf.tobytes()
                # VLM 看到的畫面是否也要模糊(blur_vlm)
                self._raw = base if self.blur_vlm else frame
                self._jpeg_seq += 1
                self._jpeg_cond.notify_all()

        now = time.perf_counter()
        inst = 1.0 / max(1e-6, now - t_prev)
        t_prev = now
        fps_ema = inst if fps_ema is None else fps_ema * 0.9 + inst * 0.1
        self.game.update(summary["present"])
        if "person" in summary["present"]:
            self.last_person_at = time.time()
        self.stats = {
            "fps": round(fps_ema, 1),
            "infer_ms": round(infer_ms, 1),
            "mode": mode,
            "models_running": models_running,
            "counts": summary["counts"],
            "objects": summary["objects"],
            "unique_people": len(self._seen.get("person", ())),
            "unique_total": sum(len(v) for v in self._seen.values()),
            "face_blur": self.face_blur.enabled,
            "faces": len(faces),
        }
        return fps_ema, t_prev

    # ---------- 繪圖 ----------
    def _draw(self, frame, r, r_pose, mode):
        img = frame.copy()
        names = r.names
        extra_zh = None
        if mode == "openvocab":
            extra_zh = dict(self.vocab)
            if self.lang == "zh-CN":
                extra_zh = {k: convert(v, "zh-CN") for k, v in extra_zh.items()}
        counts, present, objects = defaultdict(int), set(), []
        labels = []
        boxes = r.boxes
        if boxes is not None and len(boxes):
            xyxy = boxes.xyxy.cpu().numpy().astype(int)
            cls = boxes.cls.cpu().numpy().astype(int)
            conf = boxes.conf.cpu().numpy()
            # 轉成 Python int,否則 numpy 整數無法序列化成 JSON
            ids = (boxes.id.int().cpu().tolist() if boxes.id is not None
                   else [None] * len(cls))
            colors = []
            for (x1, y1, x2, y2), c, p, tid in zip(xyxy, cls, conf, ids):
                name = names[int(c)]
                zname = render_name = label(name, self.lang, extra_zh)
                key = tid if tid is not None else int(c) + 1000
                col = self._track_colors.setdefault(key, render.color_for(int(key)))
                colors.append(col)
                p = float(p)
                counts[zname] += 1
                present.add(name)
                if tid is not None:
                    self._seen[name].add(int(tid))
                    self._trails[tid].append(((x1 + x2) // 2, (y1 + y2) // 2))
                if mode != "pose":
                    render.corner_box(img, x1, y1, x2, y2, col)
                tag = f"{render_name} {p:.0%}" + (f"  #{tid}" if tid is not None else "")
                labels.append((x1, y1, tag, col))
                objects.append({"name": zname, "conf": round(float(p), 2), "id": tid})
            if r.masks is not None:
                render.draw_masks(img, r.masks.xy, colors)
            render.draw_trails(img, self._trails, self._track_colors)
        if r_pose is not None and r_pose.keypoints is not None and len(r_pose.keypoints):
            render.draw_pose(img, r_pose.keypoints.data.cpu().numpy())
        img = render.draw_labels(img, labels, self.lang)
        # 清掉已消失的軌跡,避免記憶體成長
        if len(self._trails) > 200:
            self._trails.clear()
        return img, {"counts": dict(counts), "present": present, "objects": objects[:30]}

    # ---------- 對外介面 ----------
    def wait_jpeg(self, last_seq: int, timeout=1.0):
        with self._jpeg_cond:
            if self._jpeg_seq == last_seq:
                self._jpeg_cond.wait(timeout)
            return self._jpeg_seq, self._jpeg

    def latest_raw(self):
        return self._raw

    def latest_jpeg(self):
        return self._jpeg

    def system_stats(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            **self.gpu.stats,
            "cpu": psutil.cpu_percent(),
            "ram_used_gb": round(vm.used / 2**30, 1),
            "ram_total_gb": round(vm.total / 2**30, 1),
            "device": self.device,
            "half": self.half,
            "camera_ok": self.camera.connected,
            "camera_index": self.camera.index,
            "camera_size": self.camera.actual_size,
            "loaded_models": list(self._models.keys()),
            "model_files": self.model_files,
            "profile": self.cfg.get("_profile"),
            "openvocab_model": self.openvocab_model_name,
            "status": self.status,
            "uptime_s": int(time.time() - self.started_at),
            "idle_s": round(time.time() - self.last_person_at, 1),
        }

    def run_benchmark(self, gpu_runs=30, cpu_runs=5):
        """同一張影格分別用 GPU 與 CPU 跑物件偵測,給來賓看速度差距。"""
        if self.benchmark["running"]:
            return
        self.benchmark = {"running": True, "result": None}

        def job():
            from ultralytics import YOLO
            try:
                frame = self._raw if self._raw is not None else np.zeros((720, 1280, 3), np.uint8)
                weights = self.cfg["models"]["detect"]
                imgsz = self.cfg.get("imgsz", 640)
                res = {}
                if self.device.startswith("cuda"):
                    with self._model_lock:
                        m = self._load("detect")
                        for _ in range(5):  # 暖機,排除 CUDA 初始化時間
                            m.predict(frame, device=self.device, **self._prec,
                                      imgsz=imgsz, verbose=False)
                        torch.cuda.synchronize()
                        t = time.perf_counter()
                        for _ in range(gpu_runs):
                            m.predict(frame, device=self.device, **self._prec,
                                      imgsz=imgsz, verbose=False)
                        res["gpu_ms"] = round((time.perf_counter() - t) * 1000 / gpu_runs, 1)
                cpu_model = YOLO(weights)
                cpu_model.predict(frame, device="cpu", imgsz=imgsz, verbose=False)
                t = time.perf_counter()
                for _ in range(cpu_runs):
                    cpu_model.predict(frame, device="cpu", imgsz=imgsz, verbose=False)
                res["cpu_ms"] = round((time.perf_counter() - t) * 1000 / cpu_runs, 1)
                if "gpu_ms" in res:
                    res["speedup"] = round(res["cpu_ms"] / max(res["gpu_ms"], 0.01), 1)
                self.benchmark = {"running": False, "result": res}
            except Exception as e:
                log.exception("benchmark 失敗")
                self.benchmark = {"running": False, "result": {"error": str(e)}}

        threading.Thread(target=job, daemon=True, name="bench").start()
