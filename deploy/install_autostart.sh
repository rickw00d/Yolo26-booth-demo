#!/usr/bin/env bash
# 設定開機自動啟動(GB10 / Ubuntu 桌面):
#   1. systemd 使用者服務:開機就啟動展示程式,當掉自動重啟
#   2. 登入桌面後,自動用全螢幕(kiosk)瀏覽器開啟儀表板
#   3. 關閉螢幕保護與自動鎖定
# 取消:./deploy/install_autostart.sh --uninstall
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${DEMO_PROFILE:-config.gb10.yaml}"
UNIT_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl --user disable --now yolo-demo.service || true
  rm -f "$UNIT_DIR/yolo-demo.service" "$AUTOSTART_DIR/yolo-demo-kiosk.desktop"
  systemctl --user daemon-reload
  echo "已移除開機自動啟動。"
  exit 0
fi

mkdir -p "$UNIT_DIR" "$AUTOSTART_DIR"
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__PROFILE__#$PROFILE#g" \
  "$APP_DIR/deploy/yolo-demo.service" > "$UNIT_DIR/yolo-demo.service"
sed -e "s#__APP_DIR__#$APP_DIR#g" \
  "$APP_DIR/deploy/yolo-demo-kiosk.desktop" > "$AUTOSTART_DIR/yolo-demo-kiosk.desktop"
chmod +x "$APP_DIR/deploy/kiosk.sh"

# 讓使用者服務在開機時就啟動(不用等登入)
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now yolo-demo.service

# 展場不要螢幕保護、不要鎖定(GNOME)
if command -v gsettings >/dev/null 2>&1; then
  gsettings set org.gnome.desktop.session idle-delay 0 || true
  gsettings set org.gnome.desktop.screensaver lock-enabled false || true
  gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' || true
fi

echo "完成。查看狀態:systemctl --user status yolo-demo;查看日誌:journalctl --user -u yolo-demo -f"
echo "下次登入桌面時會自動開啟全螢幕儀表板。"
