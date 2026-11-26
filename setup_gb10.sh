#!/usr/bin/env bash
# GB10(DGX OS / Ubuntu, aarch64)一鍵安裝。在專案資料夾執行:./setup_gb10.sh
# 需要網路。完成後依畫面提示匯出 TensorRT 並啟動。
set -euo pipefail
cd "$(dirname "$0")"
PROFILE="${DEMO_PROFILE:-config.gb10.yaml}"

echo "== 1/6 系統套件(中文字型、攝影機工具、Python venv)"
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev fonts-noto-cjk v4l-utils curl

echo "== 2/6 建立 Python 虛擬環境"
python3 -m venv .venv
.venv/bin/pip install -U pip

echo "== 3/6 PyTorch(CUDA 13,aarch64)"
# 必須先裝 PyTorch,否則下一步可能從 PyPI 裝到不吃 GPU 的版本
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130

echo "== 4/6 其他套件"
.venv/bin/pip install -r requirements.txt

echo "== 5/6 Ollama 模型"
if command -v ollama >/dev/null 2>&1; then
  for m in $(.venv/bin/python -c "
from app.config import load_config, set_profile
set_profile('$PROFILE'); o = load_config()['ollama']
print(' '.join(dict.fromkeys([o['vlm_model'], o['llm_model']])))"); do
    ollama pull "$m" || echo "  △ $m 下載失敗;若是自訂模型,請從原本的機器匯入"
  done
else
  echo "  △ 找不到 ollama。請先依官方說明安裝:https://ollama.com/download/linux"
fi

echo "== 6/6 YOLO 模型"
.venv/bin/python tools/prefetch_models.py --profile "$PROFILE"

echo
.venv/bin/python tools/check_env.py --profile "$PROFILE" || true
cat <<EOF

下一步:
  1. 匯出 TensorRT(約數分鐘,只需做一次):.venv/bin/python tools/export_trt.py --profile $PROFILE
  2. 啟動:./start_demo.sh,瀏覽器開 http://localhost:8000
  3. 開機自動啟動(選用):./deploy/install_autostart.sh
EOF
