"""Ollama 用戶端:VLM 看圖問答(串流)與中文物品名稱翻譯。"""
import base64
import json
import logging
import re

import httpx

log = logging.getLogger("llm")

VLM_SYSTEM = {
    "zh": ("你是展場攤位上的 AI 視覺助理,正在透過攝影機觀看現場畫面。"
           "請一律使用繁體中文(台灣用語)回答,語氣親切、有趣,回答控制在 80 字以內。"
           "只描述畫面中確實看得到的內容,看不清楚就說不確定,不要猜測個人身分、年齡或敏感特徵。"),
    "en": ("You are an AI vision assistant at a trade-show booth, watching the live camera feed. "
           "Always answer in English, in a friendly and fun tone, within 50 words. "
           "Only describe what is clearly visible; say you are unsure if it is unclear. "
           "Never guess anyone's identity, age or other sensitive traits."),
}
CONTEXT_PREFIX = {"zh": "(偵測模型目前看到:{})", "en": "(The detector currently sees: {})"}

TRANSLATE_PROMPT = (
    "依序把下列 {n} 個物品名稱翻譯成英文名詞片語,給物件偵測模型使用。"
    "每個 1~3 個英文單字、小寫,保留顏色等修飾語,數量與順序必須和輸入完全相同。"
    '只輸出 JSON:{{"en": ["...", "..."]}}\n'
    "物品:\n{items}"
)


class Ollama:
    def __init__(self, cfg: dict):
        self.url = cfg.get("url", "http://127.0.0.1:11434").rstrip("/")
        self.vlm = cfg.get("vlm_model", "qwen2.5vl:7b")
        self.llm = cfg.get("llm_model", "qwen3.5:2b")
        self.keep_alive = cfg.get("keep_alive", "30m")
        self.timeout = cfg.get("timeout", 120)

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                tags = (await c.get(f"{self.url}/api/tags")).json()
            names = {m["name"] for m in tags.get("models", [])}
            return {"ok": True, "vlm": self.vlm in names, "llm": self.llm in names,
                    "vlm_model": self.vlm, "llm_model": self.llm}
        except Exception as e:
            return {"ok": False, "error": str(e), "vlm_model": self.vlm, "llm_model": self.llm}

    async def warmup(self):
        """預先把 VLM 載入記憶體,第一位來賓提問時才不會等很久。"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                await c.post(f"{self.url}/api/generate",
                             json={"model": self.vlm, "prompt": "", "keep_alive": self.keep_alive})
        except Exception as e:
            log.warning("VLM 暖機失敗:%s", e)

    async def ask_stream(self, question: str, jpeg: bytes, context: str = "", lang: str = "zh"):
        """逐段產生 VLM 的回答文字。"""
        img = base64.b64encode(jpeg).decode()
        user = question
        if context:
            user = CONTEXT_PREFIX[lang].format(context) + "\n" + question
        payload = {
            "model": self.vlm, "stream": True, "think": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": 0.4, "num_predict": 256},
            "messages": [{"role": "system", "content": VLM_SYSTEM[lang]},
                         {"role": "user", "content": user, "images": [img]}],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            async with c.stream("POST", f"{self.url}/api/chat", json=payload) as r:
                if r.status_code == 400:  # 舊版 Ollama 或非思考模型不認得 think 參數
                    payload.pop("think")
                    async with c.stream("POST", f"{self.url}/api/chat", json=payload) as r2:
                        async for chunk in self._iter(r2):
                            yield chunk
                    return
                async for chunk in self._iter(r):
                    yield chunk

    @staticmethod
    async def _iter(r):
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line:
                continue
            data = json.loads(line)
            piece = data.get("message", {}).get("content", "")
            if piece:
                yield piece
            if data.get("done"):
                break

    async def translate_vocab(self, text: str) -> list[tuple[str, str]]:
        """'紅色杯子, 眼鏡' → [('red cup','紅色杯子'), ('glasses','眼鏡')]"""
        parts = [p.strip() for p in re.split(r"[,,、;;\n]+", text) if p.strip()]
        if not parts:
            return []
        if all(p.isascii() for p in parts):
            return [(p.lower(), p) for p in parts]
        payload = {"model": self.llm, "stream": False, "format": "json", "think": False,
                   "keep_alive": self.keep_alive, "options": {"temperature": 0},
                   "messages": [{"role": "user", "content": TRANSLATE_PROMPT.format(
                       n=len(parts), items="\n".join(f"{i + 1}. {p}" for i, p in enumerate(parts)))}]}
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(f"{self.url}/api/chat", json=payload)
                if r.status_code == 400:
                    payload.pop("think")
                    r = await c.post(f"{self.url}/api/chat", json=payload)
                r.raise_for_status()
            content = r.json()["message"]["content"]
            en = json.loads(content).get("en", [])
            # 中文名稱一律用來賓原本輸入的文字,只信任模型的英文翻譯
            if len(en) == len(parts) and all(isinstance(e, str) and e.strip() for e in en):
                return [(e.strip().lower(), p) for e, p in zip(en, parts)]
            log.warning("翻譯數量不符:%s → %s", parts, en)
        except Exception as e:
            log.warning("翻譯失敗,直接使用原文:%s", e)
        return [(p, p) for p in parts]
