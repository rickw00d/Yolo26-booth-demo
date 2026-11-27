#!/usr/bin/env bash
# 打包成 .deb(線上安裝版:不含 Python 環境與模型,安裝時才下載)
#   ./packaging/build_deb.sh [版本]      → dist/yolo26-booth-demo_<版本>_arm64.deb
# 安裝:sudo apt install ./dist/yolo26-booth-demo_<版本>_arm64.deb
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-1.0.0}"
PKG=yolo26-booth-demo
ARCH=arm64
APP=/opt/$PKG
OUT="dist/${PKG}_${VERSION}_${ARCH}.deb"

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
ROOTFS="$BUILD/root"
mkdir -p "$ROOTFS$APP" "$ROOTFS/DEBIAN" "$ROOTFS/usr/bin" \
         "$ROOTFS/usr/share/applications" "$ROOTFS/usr/share/icons/hicolor/scalable/apps" \
         "$ROOTFS/usr/share/doc/$PKG"

# 程式檔:git 追蹤(或未被 .gitignore 排除)的檔案,所以不會帶到 .venv、模型與截圖。
# Windows 與 Docker 用的檔案、打包本身的設定不放進去。
git ls-files -z --cached --others --exclude-standard \
  | grep -zv -E '^(docker/|packaging/debian/|packaging/build_deb\.sh$|start_demo\.bat$|\.git|dist/)' \
  | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done \
  | xargs -0 cp --parents -t "$ROOTFS$APP"

install -m 755 packaging/yolo26-demo "$ROOTFS/usr/bin/yolo26-demo"
install -m 644 packaging/yolo26-booth-demo.desktop "$ROOTFS/usr/share/applications/"
install -m 644 packaging/yolo26-booth-demo.svg "$ROOTFS/usr/share/icons/hicolor/scalable/apps/"
install -m 644 README.md README.zh-TW.md README.zh-CN.md "$ROOTFS/usr/share/doc/$PKG/"

# 權限:目錄 755、檔案 644,腳本 755
find "$ROOTFS" -type d -exec chmod 755 {} +
find "$ROOTFS$APP" -type f -exec chmod 644 {} +
chmod 755 "$ROOTFS$APP"/start_demo.sh "$ROOTFS$APP"/setup_gb10.sh \
          "$ROOTFS$APP"/deploy/*.sh "$ROOTFS$APP"/packaging/setup_env.sh

for s in postinst prerm postrm; do
  install -m 755 "packaging/debian/$s" "$ROOTFS/DEBIAN/$s"
done
# 設定檔:升級時保留使用者的修改
printf '%s\n' "$APP/config.yaml" "$APP/config.gb10.yaml" > "$ROOTFS/DEBIAN/conffiles"
SIZE=$(du -sk --exclude=DEBIAN "$ROOTFS" | cut -f1)
sed -e "s/__VERSION__/$VERSION/" -e "s/__SIZE__/$SIZE/" packaging/debian/control > "$ROOTFS/DEBIAN/control"

mkdir -p dist
dpkg-deb --root-owner-group -Zxz --build "$ROOTFS" "$OUT" >/dev/null
echo "完成:$OUT($(du -h "$OUT" | cut -f1))"
echo "安裝:sudo apt install ./$OUT"
