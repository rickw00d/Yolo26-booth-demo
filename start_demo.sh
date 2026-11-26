#!/usr/bin/env bash
# Linux / GB10 手動啟動(程式結束會自動重啟)。開機自動啟動請改用 deploy/install_autostart.sh。
cd "$(dirname "$0")"
PROFILE="${DEMO_PROFILE:-config.gb10.yaml}"
while true; do
  echo "[$(date '+%F %T')] 啟動 YOLO26 展示(平台設定:$PROFILE)"
  .venv/bin/python run.py --profile "$PROFILE"
  echo "程式結束,3 秒後自動重啟(按 Ctrl+C 停止)"
  sleep 3
done
