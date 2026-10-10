#!/bin/zsh
set -euo pipefail

LABEL="com.szu.autologin"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"

launchctl bootout "gui/${UID_NUM}" "${PLIST_PATH}" >/dev/null 2>&1 || true
if [[ -f "${PLIST_PATH}" ]]; then
  /bin/unlink "${PLIST_PATH}" 2>/dev/null || true
fi

echo "已卸载 macOS 后台服务：${LABEL}"
