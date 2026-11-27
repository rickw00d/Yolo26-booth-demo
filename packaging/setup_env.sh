#!/usr/bin/env bash
# 建立 Python 環境並下載模型(需要網路)。
#   .deb 安裝時會以一般使用者身分自動執行;安裝中斷或要修復時可手動重跑:yolo26-demo --setup
# 重跑是安全的:已裝好的部分會直接略過。
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${DEMO_PROFILE:-config.gb10.yaml}"
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cu130}"
cd "$APP_DIR"
PY=.venv/bin/python
PIP=(.venv/bin/python -m pip --disable-pip-version-check)

echo "== 1/5 Python 虛擬環境"
[ -x "$PY" ] || python3 -m venv .venv
"${PIP[@]}" install -q -U pip

echo "== 2/5 PyTorch(CUDA 13,約 3 GB,下載需要數分鐘)"
# 必須先裝 PyTorch,否則下一步可能從 PyPI 裝到不吃 GPU 的版本
if "$PY" -c "import torch, torchvision" 2>/dev/null; then
  echo "  已安裝,略過"
else
  "${PIP[@]}" install --progress-bar off torch torchvision --index-url "$TORCH_INDEX"
fi

echo "== 3/5 其他套件"
"${PIP[@]}" install --progress-bar off -r requirements.txt

echo "== 4/5 YOLO 模型(約 0.7 GB)"
"$PY" tools/prefetch_models.py --profile "$PROFILE" \
  || echo "  △ 部分模型下載失敗,第一次使用該模式時會再自動下載"

echo "== 5/5 Ollama 模型(AI 問答)"
if command -v ollama >/dev/null 2>&1; then
  models=$("$PY" -c "
from app.config import load_config, set_profile
set_profile('$PROFILE'); o = load_config()['ollama']
print(' '.join(dict.fromkeys([o['vlm_model'], o['llm_model']])))")
  for m in $models; do
    ollama pull "$m" || echo "  △ $m 下載失敗;若是自訂模型,請從原本的機器匯入"
  done
else
  echo "  △ 找不到 ollama,AI 問答與自由辨識的翻譯暫時無法使用。"
  echo "    安裝方式:curl -fsSL https://ollama.com/install.sh | sh"
  echo "    裝好後執行 yolo26-demo --setup 下載模型"
fi
echo "環境建立完成。"
