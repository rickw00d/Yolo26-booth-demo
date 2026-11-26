# 備案:原生安裝 PyTorch / TensorRT 有問題時,改用 Ultralytics 官方 ARM64 映像檔
# (內含針對 DGX Spark / Jetson 編譯的 PyTorch 與 TensorRT)。
# 程式碼與模型檔用 volume 掛進去,所以 .engine 匯出一次就會保留在主機上。
FROM ultralytics/ultralytics:latest-nvidia-arm64

RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-noto-cjk v4l-utils curl \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" httpx pyyaml psutil pillow \
    opencc-python-reimplemented "lap>=0.5.12" yt-dlp

WORKDIR /app
CMD ["python", "run.py", "--profile", "config.gb10.yaml"]
