#!/bin/zsh
cd -- "$(dirname -- "$0")"
./uninstall_macos.sh
result=$?
echo
read -r "?按回车键关闭窗口..."
exit ${result}
