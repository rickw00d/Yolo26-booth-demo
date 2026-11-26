"""執行緒化影像來源:永遠只保留最新影格,斷線自動重連。

來源可以是:
  - 攝影機編號(0、1…)或裝置路徑(/dev/video0):走 MSMF / V4L2
  - 串流網址或影片檔:走 FFmpeg
      rtsp://…(IP 攝影機)、http(s)://….m3u8 / .mp4 / .mjpg、本機影片檔(播完自動重播)
      YouTube 或內嵌 YouTube 的網頁:先用 yt-dlp 解析出真正的串流網址
串流會先緩衝幾秒再以固定速率播放:HLS(YouTube)是一段一段送來的,
直接顯示會「快轉 → 停住」交替。
"""
import logging
import os
import platform
import threading
import time
from collections import deque
from urllib.parse import urlparse

import cv2

log = logging.getLogger("camera")

_BACKENDS = {
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "v4l2": cv2.CAP_V4L2,
    "gstreamer": cv2.CAP_GSTREAMER,
}

# 這些副檔名是 FFmpeg 能直接開的媒體網址,不必經過 yt-dlp
_MEDIA_EXT = (".m3u8", ".mpd", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".ts", ".flv",
              ".mjpg", ".mjpeg", ".cgi")


def _prepare_ffmpeg_env():
    # OpenCV 內建的 FFmpeg 找不到系統憑證,https 串流會憑證驗證失敗;改用 certifi 的憑證檔
    if "SSL_CERT_FILE" not in os.environ:
        try:
            import certifi
            os.environ["SSL_CERT_FILE"] = certifi.where()
        except ImportError:
            pass
    # RTSP 走 TCP:展場 Wi-Fi / 交換器掉 UDP 封包時畫面才不會花掉
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


_prepare_ffmpeg_env()


def is_stream(src) -> bool:
    """攝影機編號 / /dev/videoN 以外的來源(網址、影片檔)都當成串流。"""
    if isinstance(src, int):
        return False
    s = str(src).strip()
    return not (s.isdigit() or s.startswith("/dev/video"))


def _redact(url: str) -> str:
    """日誌與畫面上不顯示帳號密碼與查詢參數(串流網址常帶 token)。"""
    p = urlparse(url)
    if not p.scheme or not p.hostname:
        return url
    host = p.hostname + (f":{p.port}" if p.port else "")
    return f"{p.scheme}://{host}{p.path}"


class Camera:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        idx = cfg.get("index", 0)
        self.device_index = int(idx) if str(idx).strip().isdigit() else idx   # 按 C 切回的攝影機
        self.stream = (cfg.get("stream") or "").strip()                       # 按 C 切過去的串流
        use_stream = cfg.get("start_with_stream") and self.stream
        self.index = self.stream if use_stream else self.device_index         # 目前使用中的來源
        self._frame = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._gen = 0              # 每次切換來源 +1,舊的讀取迴圈看到就結束
        self._running = False
        self.connected = False
        self.actual_size = (0, 0)
        self.buffering = False

    @property
    def label(self) -> str:
        if not is_stream(self.index):
            return f"#{self.index}"
        s = str(self.index)
        return urlparse(s).hostname or os.path.basename(s)

    # ---------- 執行緒 ----------
    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True, name="camera").start()

    def stop(self):
        self._running = False

    def switch(self, source):
        if isinstance(source, str):
            source = source.strip()
            if source.isdigit():
                source = int(source)
        if is_stream(source):
            self.stream = source         # 記住最後用的串流,下次按 C 切回它
        else:
            self.device_index = source
        self.index = source
        self.connected = False     # 新來源開好之前,畫面顯示「連線中」而不是停在舊畫面
        self._gen += 1

    def toggle(self):
        """攝影機 ⇄ 串流。沒有設定串流時維持攝影機。"""
        if is_stream(self.index):
            self.switch(self.device_index)
        elif self.stream:
            self.switch(self.stream)

    def read(self):
        """回傳 (frame_id, frame);尚無影格時 frame 為 None。"""
        with self._lock:
            return self._frame_id, self._frame

    def _publish(self, frame, mirror: bool, gen: int):
        if self._gen != gen:       # 已切換來源,舊來源的影格不要再送出
            return
        if mirror:
            frame = cv2.flip(frame, 1)
        with self._lock:
            self._frame = frame
            self._frame_id += 1
        self.connected = True

    def _alive(self, gen) -> bool:
        return self._running and self._gen == gen

    def _wait(self, gen, seconds: float):
        """等待重試,但一切換來源就立刻結束。"""
        end = time.monotonic() + seconds
        while self._alive(gen) and time.monotonic() < end:
            time.sleep(0.1)

    def _loop(self):
        while self._running:
            gen, src = self._gen, self.index
            try:
                if is_stream(src):
                    self._run_stream(src, gen)
                else:
                    self._run_device(src, gen)
            except Exception:
                log.exception("影像來源發生錯誤,2 秒後重試")
                self.connected = False
                time.sleep(2)

    # ---------- USB 攝影機 ----------
    def _backend(self):
        name = self.cfg.get("backend", "auto")
        if name != "auto":
            return _BACKENDS[name]
        # Windows 用 MSMF:實測 DSHOW 不吃 MJPG 設定,720p 走 YUY2 只有 10fps,MSMF 可達 30fps
        return cv2.CAP_MSMF if platform.system() == "Windows" else cv2.CAP_V4L2

    def _open_device(self, index):
        cap = cv2.VideoCapture(index, self._backend())
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
        log.info("攝影機 %s 已開啟,解析度 %sx%s", index, *self.actual_size)
        return cap

    def _run_device(self, index, gen):
        cap = self._open_device(index)
        if cap is None:
            self.connected = False
            log.warning("攝影機 %s 無法開啟,2 秒後重試", index)
            self._wait(gen, 2)
            return
        mirror = self.cfg.get("mirror", True)
        try:
            while self._alive(gen):
                ok, frame = cap.read()
                if not ok:
                    log.warning("攝影機讀取失敗,重新連線")
                    self.connected = False
                    self._wait(gen, 0.5)
                    return
                self._publish(frame, mirror, gen)
        finally:
            cap.release()

    # ---------- 串流 / 影片檔 ----------
    def _resolve(self, src: str) -> str:
        """YouTube 或內嵌影片的網頁 → 用 yt-dlp 取出真正的串流網址(網址數小時後會失效,每次重連都重新解析)。"""
        p = urlparse(src)
        if p.scheme not in ("http", "https") or p.path.lower().endswith(_MEDIA_EXT):
            return src
        try:
            from yt_dlp import YoutubeDL
        except ImportError:
            log.warning("未安裝 yt-dlp,直接把網址交給 FFmpeg(YouTube 需要:pip install yt-dlp)")
            return src
        h = self.cfg.get("height", 720)
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            # 優先 H.264(解碼最穩),高度不超過設定值
            "format": f"bestvideo[height<={h}][vcodec^=avc1]/bestvideo[height<={h}]/best[height<={h}]/best",
        }
        try:
            info = YoutubeDL(opts).extract_info(src, download=False)
        except Exception as e:
            log.warning("yt-dlp 無法解析 %s,直接交給 FFmpeg:%s", _redact(src), str(e).splitlines()[0])
            return src
        if info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]
        url = info.get("url") or (info.get("requested_formats") or [{}])[0].get("url")
        if not url:
            return src
        log.info("yt-dlp 解析完成:%s %sp%s", info.get("extractor"), info.get("height"),
                 "(直播)" if info.get("is_live") else "")
        return url

    def _run_stream(self, src, gen):
        src = str(src)
        is_file = os.path.isfile(src)
        url = self._resolve(src)
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000,
                                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 15000])
        if not cap.isOpened():
            cap.release()
            self.connected = False
            log.warning("串流 %s 無法開啟,5 秒後重試", _redact(src))
            self._wait(gen, 5)
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not 1 <= fps <= 120:
            fps = self.cfg.get("fps", 30)
        # 直播:緩衝 stream_buffer_s 秒以撐過分段傳送的空檔;影片檔:讀檔很快,不需預先緩衝
        prebuffer = 1 if is_file else max(1, int(fps * self.cfg.get("stream_buffer_s", 6)))
        cap_frames = prebuffer * 2 + int(fps)
        buf, cond, done = deque(), threading.Condition(), threading.Event()

        def reader():
            try:
                while self._alive(gen):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    with cond:
                        if is_file:      # 影片檔:緩衝滿就等,不丟影格
                            while len(buf) >= cap_frames and self._alive(gen):
                                cond.wait(0.5)
                        elif len(buf) >= cap_frames:   # 直播:落後太多就丟最舊的,維持延遲
                            buf.popleft()
                        buf.append(frame)
                        cond.notify_all()
            finally:
                cap.release()
                done.set()
                with cond:
                    cond.notify_all()

        threading.Thread(target=reader, daemon=True, name="camera-reader").start()

        mirror = self.cfg.get("stream_mirror", False)
        period = 1.0 / fps
        self.buffering, opened, next_t = True, False, 0.0
        while self._alive(gen):
            with cond:
                if self.buffering:
                    if len(buf) >= prebuffer or (done.is_set() and buf):
                        self.buffering = False
                        next_t = time.monotonic()
                    elif done.is_set():
                        break
                    else:
                        cond.wait(0.2)
                        continue
                if not buf:
                    if done.is_set():
                        break
                    if not is_file:
                        log.info("串流資料不足,重新緩衝")
                    self.buffering = True
                    continue
                frame = buf.popleft()
                cond.notify_all()
            if not opened:
                opened = True
                self.actual_size = (frame.shape[1], frame.shape[0])
                log.info("串流 %s 已開啟,解析度 %sx%s,%.0f fps", _redact(src), *self.actual_size, fps)
            self._publish(frame, mirror, gen)
            next_t += period
            delay = next_t - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            elif delay < -1:           # 落後超過 1 秒就重設時鐘,不要追趕快轉
                next_t = time.monotonic()

        self.buffering = False
        if self._alive(gen):
            if is_file:
                log.info("影片播完,從頭重播")
            else:
                log.warning("串流中斷,2 秒後重新連線")
                self.connected = False
                self._wait(gen, 2)
