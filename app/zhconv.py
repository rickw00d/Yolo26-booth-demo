"""中文輸出的字形與用語轉換(OpenCC)。

- zh-TW:s2twp,簡體字與中國用語 → 台灣繁體與用語(視頻→影片、軟件→軟體)
- zh-CN:tw2sp,繁體字與台灣用語 → 簡體與大陸用語(影片→视频、滑鼠→鼠标)

詞彙轉換需要前後文,所以串流時不能逐片段轉換:改成每次轉換「累積的完整文字」,
並保留最後幾個字不送出,等詞彙完整再送。
"""
import logging

log = logging.getLogger("zhconv")

_CONFIGS = {"zh-TW": "s2twp", "zh-CN": "tw2sp"}
_converters = {}

try:
    from opencc import OpenCC
    for _lang, _cfg in _CONFIGS.items():
        _converters[_lang] = OpenCC(_cfg)
except Exception as e:  # 沒裝 OpenCC 時原樣輸出,不影響展示
    log.warning("OpenCC 無法載入,略過繁簡轉換:%s", e)


def convert(text: str, lang: str) -> str:
    cc = _converters.get(lang)
    return cc.convert(text) if cc else text


def to_tw(text: str) -> str:
    return convert(text, "zh-TW")


class StreamConverter:
    """串流用轉換:feed() 回傳可以安全送出的新文字,flush() 送出剩下的部分。"""

    def __init__(self, lang: str = "zh-TW", hold: int = 3):
        self.lang = lang
        self.hold = hold          # 保留不送出的字數(詞彙最長通常 2~4 字)
        self._raw = ""
        self._sent = 0            # 已送出的「轉換後」字數

    def feed(self, piece: str) -> str:
        self._raw += piece
        converted = convert(self._raw, self.lang)
        safe = max(self._sent, len(converted) - self.hold)
        out = converted[self._sent:safe]
        self._sent = safe
        return out

    def flush(self) -> str:
        converted = convert(self._raw, self.lang)
        out = converted[self._sent:]
        self._sent = len(converted)
        return out
