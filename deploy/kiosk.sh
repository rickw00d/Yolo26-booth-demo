#!/usr/bin/env bash
# 等展示程式啟動後,用找得到的瀏覽器以全螢幕(kiosk)開啟儀表板。
URL="${DEMO_URL:-http://localhost:8000}"
for _ in $(seq 1 120); do          # 最多等 4 分鐘(GB10 預先載入大模型需要時間)
  curl -fs "$URL/api/config" >/dev/null 2>&1 && break
  sleep 2
done
FLAGS=(--kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble
       --autoplay-policy=no-user-gesture-required --incognito)
for b in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$b" >/dev/null 2>&1; then
    exec "$b" "${FLAGS[@]}" "$URL"
  fi
done
if command -v firefox >/dev/null 2>&1; then
  exec firefox --kiosk "$URL"
fi
echo "找不到 Chromium / Chrome / Firefox,請手動開啟 $URL" >&2
