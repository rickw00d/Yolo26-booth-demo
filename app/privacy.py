"""人臉模糊:用姿態模型的臉部關鍵點(鼻、雙眼、雙耳)定位頭部,再打馬賽克。

不需要額外的人臉模型,在 Windows 和 GB10 上都能直接使用。
為了避免偵測漏掉一兩個影格造成人臉「閃現」,會保留最近幾個影格的位置一起模糊。
"""
import threading
from collections import deque

import cv2
import numpy as np

FACE_KPTS = [0, 1, 2, 3, 4]   # 鼻、左眼、右眼、左耳、右耳
L_SHOULDER, R_SHOULDER = 5, 6


class FaceBlur:
    def __init__(self, cfg: dict):
        self.enabled = bool(cfg.get("face_blur", True))
        self.style = cfg.get("style", "pixelate")       # pixelate | gaussian
        self.pixel_blocks = int(cfg.get("pixel_blocks", 10))
        self.scale = float(cfg.get("scale", 1.0))
        self.kpt_conf = float(cfg.get("kpt_conf", 0.3))
        self._history = deque(maxlen=max(1, int(cfg.get("hold_frames", 6))))
        self._lock = threading.Lock()   # apply(繪圖執行緒)與 reset(API 執行緒)互斥

    # ---------- 定位 ----------
    def locate(self, kpts: np.ndarray | None, boxes: np.ndarray | None) -> list[tuple]:
        """kpts: (N,17,3);boxes: (N,4) 人的框。回傳 [(cx, cy, rx, ry)]。"""
        faces = []
        if kpts is None or len(kpts) == 0:
            return faces
        for i, person in enumerate(kpts):
            box = boxes[i] if boxes is not None and i < len(boxes) else None
            vis = person[FACE_KPTS][person[FACE_KPTS, 2] > self.kpt_conf][:, :2]
            sh = person[[L_SHOULDER, R_SHOULDER]]
            shoulder_w = (float(np.linalg.norm(sh[0, :2] - sh[1, :2]))
                          if (sh[:, 2] > self.kpt_conf).all() else 0.0)
            if len(vis) >= 2:
                cx, cy = vis.mean(axis=0)
                spread = float(np.ptp(vis, axis=0).max())
                r = max(spread * 1.2, shoulder_w * 0.35, 14.0)
                cy -= r * 0.15                      # 臉中心略高於眼鼻平均位置
            elif box is not None:                   # 臉部點不足:取人框頂部當頭部
                x1, y1, x2, y2 = box
                r = max(0.2 * min(x2 - x1, y2 - y1), shoulder_w * 0.35, 14.0)
                cx, cy = (x1 + x2) / 2, y1 + r
            else:
                continue
            if box is not None:                     # 不超過人框高度的一半
                r = min(r, 0.5 * (box[3] - box[1]) + 14)
            r *= self.scale
            faces.append((float(cx), float(cy), r, r * 1.25))
        return faces

    def locate_from_box(self, box) -> list[tuple]:
        """只有人框(遠處、背對、側臉)時,以框頂部估計頭部位置。"""
        x1, y1, x2, y2 = box
        w, h = x2 - x1, y2 - y1
        r = max(0.25 * min(w, h), 10.0) * self.scale
        return [(float((x1 + x2) / 2), float(y1 + r), r, r * 1.25)]

    # ---------- 模糊 ----------
    def apply(self, img: np.ndarray, faces: list[tuple]) -> int:
        """就地模糊,回傳這次處理的臉數(含保留的歷史位置)。"""
        with self._lock:
            self._history.append(faces)
            history = [list(f) for f in self._history]
        h, w = img.shape[:2]
        n = 0
        for frame_faces in history:
            for cx, cy, rx, ry in frame_faces:
                x1, y1 = max(0, int(cx - rx)), max(0, int(cy - ry))
                x2, y2 = min(w, int(cx + rx)), min(h, int(cy + ry))
                if x2 - x1 < 4 or y2 - y1 < 4:
                    continue
                roi = img[y1:y2, x1:x2]
                if self.style == "gaussian":
                    k = max(15, (int(rx) // 2) * 2 + 1)
                    blurred = cv2.GaussianBlur(roi, (k, k), 0)
                else:
                    b = self.pixel_blocks
                    small = cv2.resize(roi, (b, max(1, int(b * (y2 - y1) / (x2 - x1)))),
                                       interpolation=cv2.INTER_LINEAR)
                    blurred = cv2.resize(small, (x2 - x1, y2 - y1),
                                         interpolation=cv2.INTER_NEAREST)
                mask = np.zeros(roi.shape[:2], np.uint8)
                cv2.ellipse(mask, (int(cx) - x1, int(cy) - y1), (int(rx), int(ry)),
                            0, 0, 360, 255, -1)
                roi[mask > 0] = blurred[mask > 0]
                n += 1
        return len(faces)

    def reset(self):
        with self._lock:
            self._history.clear()
