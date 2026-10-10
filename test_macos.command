#!/bin/zsh
cd -- "$(dirname -- "$0")"
python3 szu_autologin.py once
result=$?
echo
read -r "?按回车键关闭窗口..."
exit ${result}
