#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="$(command -v python3)"
CONFIG_PATH="${HOME}/.config/szu-autologin/config.json"
AGENT_LABEL="com.szu.autologin"
PLIST_PATH="${HOME}/Library/LaunchAgents/${AGENT_LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs"
UID_NUM="$(id -u)"

if [[ ! -f "${CONFIG_PATH}" ]]; then
  echo "未找到 ${CONFIG_PATH}"
  echo "请先运行：python3 ${SCRIPT_DIR}/szu_autologin.py init"
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${LOG_DIR}"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${AGENT_LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${SCRIPT_DIR}/szu_autologin.py</string>
    <string>--config</string>
    <string>${CONFIG_PATH}</string>
    <string>run</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${SCRIPT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>15</integer>
  <key>ProcessType</key>
  <string>Background</string>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/szu-autologin.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/szu-autologin.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/${UID_NUM}" "${PLIST_PATH}" >/dev/null 2>&1 || true

if launchctl bootstrap "gui/${UID_NUM}" "${PLIST_PATH}"; then
  echo "已启动 launchd 服务：${AGENT_LABEL}"
else
  echo "bootstrap 失败，尝试兼容旧版 launchctl..."
  launchctl load -w "${PLIST_PATH}"
  echo "已加载 launchd 服务：${AGENT_LABEL}"
fi

echo "配置文件：${CONFIG_PATH}"
echo "运行日志：${LOG_DIR}/szu-autologin.out.log"
echo "错误日志：${LOG_DIR}/szu-autologin.err.log"
