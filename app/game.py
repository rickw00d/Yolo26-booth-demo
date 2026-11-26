"""物品挑戰小遊戲:限時內把指定物品拿到鏡頭前。"""
import json
import random
import threading
import time
from pathlib import Path

from .config import ROOT
from .labels import zh, zh_cn

BOARD_FILE = ROOT / "data" / "leaderboard.json"


class Game:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._lock = threading.Lock()
        self.active = False
        self.player = ""
        self.targets: list[str] = []
        self.found: dict[str, float] = {}
        self._streak: dict[str, int] = {}
        self.start_time = 0.0
        self.end_time = 0.0
        self.last_result = None
        self.board = self._load_board()

    # ---------- 排行榜 ----------
    def _load_board(self):
        try:
            return json.loads(BOARD_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_board(self):
        BOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        BOARD_FILE.write_text(json.dumps(self.board, ensure_ascii=False, indent=1),
                              encoding="utf-8")

    def reset_board(self):
        with self._lock:
            self.board = []
            self._save_board()

    # ---------- 遊戲流程 ----------
    def start(self, player: str = ""):
        with self._lock:
            pool = list(self.cfg.get("pool", []))
            n = min(self.cfg.get("targets_per_round", 5), len(pool))
            self.targets = random.sample(pool, n)
            self.found = {}
            self._streak = {t: 0 for t in self.targets}
            self.player = (player or "").strip()[:12]   # 空白時由前端顯示「來賓 / Guest」
            self.start_time = time.time()
            self.end_time = self.start_time + self.cfg.get("duration", 30)
            self.active = True
            self.last_result = None

    def stop(self):
        with self._lock:
            if self.active:
                self._finish()

    def update(self, present: set[str]):
        """每個影格呼叫一次;present 是這個影格偵測到的英文類別名稱。"""
        if not self.active:
            return
        with self._lock:
            now = time.time()
            need = self.cfg.get("confirm_frames", 3)
            for t in self.targets:
                if t in self.found:
                    continue
                self._streak[t] = self._streak[t] + 1 if t in present else 0
                if self._streak[t] >= need:
                    self.found[t] = round(now - self.start_time, 1)
            if len(self.found) == len(self.targets) or now >= self.end_time:
                self._finish()

    def _finish(self):
        self.active = False
        elapsed = round(min(time.time(), self.end_time) - self.start_time, 1)
        n = len(self.found)
        # 分數:每找到一個 100 分,全部找到再依剩餘秒數加分
        bonus = int(max(0.0, self.end_time - time.time()) * 10) if n == len(self.targets) else 0
        score = n * 100 + bonus
        self.last_result = {"player": self.player, "found": n,
                            "total": len(self.targets), "time": elapsed,
                            "score": score}
        self.board.append({**self.last_result, "ts": int(time.time())})
        self.board.sort(key=lambda r: (-r["score"], r["time"]))
        self.board = self.board[:10]
        self._save_board()

    def state(self) -> dict:
        with self._lock:
            remain = max(0.0, self.end_time - time.time()) if self.active else 0.0
            return {
                "active": self.active,
                "player": self.player,
                "remain": round(remain, 1),
                "duration": self.cfg.get("duration", 30),
                "targets": [{"name": t, "zh": zh(t), "zh_cn": zh_cn(t), "found": t in self.found,
                             "at": self.found.get(t)} for t in self.targets],
                "result": self.last_result,
                "board": self.board,
            }
