"""執行緒化攝影機讀取:永遠只保留最新影格,斷線自動重連。"""
import logging
import platform
import threading
import time

import cv2

log = logging.getLogger("camera")

_BACKENDS = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "v4l2": cv2.CAP_V4L2,
    "gstreamer": cv2.CAP_GSTREAMER,
}


class Camera:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.index = cfg.get("index", 0)
        self._cap = None
        self._frame = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._running = False
        self.connected = False
        self.actual_size = (0, 0)

    # ---------- 開啟 ----------
    def _backend(self):
        name = self.cfg.get("backend", "auto")
        if name != "auto":
            return _BACKENDS[name]
        # Windows 用 MSMF:實測 DSHOW 不吃 MJPG 設定,720p 走 YUY2 只有 10fps,MSMF 可達 30fps
        return cv2.CAP_MSMF if platform.system() == "Windows" else cv2.CAP_V4L2

    def _open(self):
        cap = cv2.VideoCapture(self.index, self._backend())
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.get("width", 1280))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.get("height", 720))
        cap.set(cv2.CAP_PROP_FPS, self.cfg.get("fps", 30))
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, _ = cap.read()
        if not ok:
            cap.release()
            return None
        self.actual_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        log.info("攝影機 %s 已開啟,解析度 %sx%s", self.index, *self.actual_size)
        return cap

    # ---------- 執行緒 ----------
    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="camera").start()

    def stop(self):
        self._running = False

    def switch(self, index: int):
        self.index = index
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _loop(self):
        while self._running:
            if self._cap is None:
                self._cap = self._open()
                if self._cap is None:
                    self.connected = False
                    log.warning("攝影機 %s 無法開啟,2 秒後重試", self.index)
                    time.sleep(2)
                    continue
            cap = self._cap
            ok, frame = cap.read()
            if not ok:
                log.warning("攝影機讀取失敗,重新連線")
                self.connected = False
                cap.release()
                self._cap = None
                time.sleep(0.5)
                continue
            if self.cfg.get("mirror", True):
                frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame = frame
                self._frame_id += 1
            self.connected = True

    def read(self):
        """回傳 (frame_id, frame);尚無影格時 frame 為 None。"""
        with self._lock:
            return self._frame_id, self._frame
