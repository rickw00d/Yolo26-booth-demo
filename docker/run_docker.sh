#!/usr/bin/env bash
# 用 Docker 執行(備案)。在專案資料夾執行:./docker/run_docker.sh [指令]
#   ./docker/run_docker.sh                                   啟動展示
#   ./docker/run_docker.sh python tools/check_env.py --profile config.gb10.yaml
#   ./docker/run_docker.sh python tools/export_trt.py --profile config.gb10.yaml
# Ollama 跑在主機上,容器用 host 網路連 127.0.0.1:11434。
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE=yolo26-booth-demo:gb10
docker build -t "$IMAGE" docker/
CAMS=()
for d in /dev/video*; do [[ -e "$d" ]] && CAMS+=(--device "$d"); done
# --device nvidia.com/gpu=all 是 Ultralytics 文件中 DGX OS 的用法(CDI)
docker run -it --rm --name yolo26-demo \
  --device nvidia.com/gpu=all "${CAMS[@]}" \
  --network host --ipc host \
  -v "$PWD":/app -w /app \
  "$IMAGE" "$@"
