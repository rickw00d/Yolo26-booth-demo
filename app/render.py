"""展場風格的繪圖:霓虹角框、追蹤軌跡、半透明遮罩、骨架、中文標籤。"""
import colorsys
import platform
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# COCO 17 點骨架連線
SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12),
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2),
            (1, 3), (2, 4)]

# (字型檔, TTC 內的字面索引);Noto CJK 的 TTC 順序為 JP=0, KR=1, SC=2, TC=3, HK=4
_FONT_CANDIDATES = {
    "zh-TW": [("C:/Windows/Fonts/msjhbd.ttc", 0), ("C:/Windows/Fonts/msjh.ttc", 0),
              ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 3),
              ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 3),
              ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 3),
              ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0)],
    "zh-CN": [("C:/Windows/Fonts/msyhbd.ttc", 0), ("C:/Windows/Fonts/msyh.ttc", 0),
              ("C:/Windows/Fonts/simhei.ttf", 0),
              ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
              ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
              ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 2),
              ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0)],
}


def _load_font(lang: str, size: int):
    for path, index in _FONT_CANDIDATES[lang]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=index)
            except OSError:
                continue
    return None


FONTS = {lang: _load_font(lang, 22) for lang in _FONT_CANDIDATES}
FONTS["en"] = FONTS["zh-TW"] or FONTS["zh-CN"]


def color_for(key: int) -> tuple[int, int, int]:
    """依 id 產生鮮豔的 BGR 顏色(黃金角分佈,相鄰 id 顏色差異大)。"""
    h = (key * 0.618033988749895) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.85, 1.0)
    return int(b * 255), int(g * 255), int(r * 255)


def corner_box(img, x1, y1, x2, y2, color, t=3):
    w, h = x2 - x1, y2 - y1
    L = max(12, int(min(w, h) * 0.22))
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
    for (cx, cy, dx, dy) in [(x1, y1, 1, 1), (x2, y1, -1, 1),
                             (x1, y2, 1, -1), (x2, y2, -1, -1)]:
        cv2.line(img, (cx, cy), (cx + dx * L, cy), color, t, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * L), color, t, cv2.LINE_AA)


def draw_masks(img, masks_xy, colors, alpha=0.40):
    if not masks_xy:
        return
    overlay = img.copy()
    for poly, c in zip(masks_xy, colors):
        if poly is None or len(poly) < 3:
            continue
        pts = poly.astype(np.int32)
        cv2.fillPoly(overlay, [pts], c)
        cv2.polylines(img, [pts], True, c, 2, cv2.LINE_AA)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, dst=img)


def draw_pose(img, kpts, conf_thr=0.5):
    """kpts: (N, 17, 3)"""
    for person in kpts:
        for a, b in SKELETON:
            if person[a, 2] > conf_thr and person[b, 2] > conf_thr:
                pa = tuple(int(v) for v in person[a, :2])
                pb = tuple(int(v) for v in person[b, :2])
                cv2.line(img, pa, pb, (255, 255, 0), 3, cv2.LINE_AA)
        for x, y, c in person:
            if c > conf_thr:
                cv2.circle(img, (int(x), int(y)), 5, (0, 0, 255), -1, cv2.LINE_AA)
                cv2.circle(img, (int(x), int(y)), 7, (255, 255, 255), 1, cv2.LINE_AA)


def draw_trails(img, trails: dict, colors: dict):
    for tid, pts in trails.items():
        if len(pts) < 2:
            continue
        c = colors.get(tid, (255, 255, 255))
        n = len(pts)
        for i in range(1, n):
            thick = max(1, int(5 * i / n))
            cv2.line(img, pts[i - 1], pts[i], c, thick, cv2.LINE_AA)


def draw_labels(img, labels, lang: str = "zh-TW"):
    """labels: [(x, y, text, bgr)];用 PIL 畫中文,一次處理整張圖以降低成本。"""
    if not labels:
        return img
    FONT = FONTS.get(lang) or FONTS["zh-TW"]
    if FONT is None:  # 找不到中文字型時退回 OpenCV
        for x, y, text, c in labels:
            cv2.putText(img, text.encode("ascii", "replace").decode(), (x, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2, cv2.LINE_AA)
        return img
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    for x, y, text, c in labels:
        rgb = (c[2], c[1], c[0])
        l, t, r, b = d.textbbox((0, 0), text, font=FONT)
        tw, th = r - l, b - t
        y0 = max(0, y - th - 10)
        d.rectangle([x, y0, x + tw + 12, y0 + th + 8], fill=(10, 14, 30))
        d.rectangle([x, y0, x + 4, y0 + th + 8], fill=rgb)
        d.text((x + 8, y0 + 2 - t), text, font=FONT, fill=rgb)
    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
