"""把模型回答中混入的簡體字與中國用語轉成台灣繁體(OpenCC s2twp)。

s2twp 會做詞彙轉換(軟件→軟體、視頻→影片),需要前後文,
所以串流時不能逐片段轉換:改成每次轉換「累積的完整文字」,
並保留最後幾個字不送出,等詞彙完整再送。
"""
import logging

log = logging.getLogger("zhconv")

try:
    from opencc import OpenCC
    _cc = OpenCC("s2twp")
except Exception as e:  # 沒裝 OpenCC 時原樣輸出,不影響展示
    log.warning("OpenCC 無法載入,略過簡轉繁:%s", e)
    _cc = None


def to_tw(text: str) -> str:
    return _cc.convert(text) if _cc else text


class StreamConverter:
    """串流用的簡轉繁:feed() 回傳可以安全送出的新文字,flush() 送出剩下的部分。"""

    def __init__(self, hold: int = 3):
        self.hold = hold          # 保留不送出的字數(詞彙最長通常 2~4 字)
        self._raw = ""
        self._sent = 0            # 已送出的「轉換後」字數

    def feed(self, piece: str) -> str:
        self._raw += piece
        converted = to_tw(self._raw)
        safe = max(self._sent, len(converted) - self.hold)
        out = converted[self._sent:safe]
        self._sent = safe
        return out

    def flush(self) -> str:
        converted = to_tw(self._raw)
        out = converted[self._sent:]
        self._sent = len(converted)
        return out
