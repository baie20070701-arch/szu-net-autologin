# 深圳大学内网自动登录

[![Cross-platform CI](https://github.com/baie20070701-arch/szu-net-autologin/actions/workflows/ci.yml/badge.svg)](https://github.com/baie20070701-arch/szu-net-autologin/actions/workflows/ci.yml)

深圳大学 Dr.COM 内网断线自动重连工具，支持 **Windows 10/11** 和 **macOS**。

脚本会定期检查内网认证状态，发现掉线时自动重新登录：

- 在线状态：`http://172.30.255.42/drcom/chkstatus`
- 登录接口：`http://172.30.255.42/drcom/login`
- 默认每 20 秒检查一次
- 登录失败默认 5 分钟后重试，避免频繁请求
- 只使用 Python 标准库，不需要安装第三方依赖

## 环境要求

### Windows

1. 安装 [Python 3.10 或更高版本](https://www.python.org/downloads/windows/)。
2. 安装时勾选 **Add python.exe to PATH**。
3. 下载或克隆本仓库。

```powershell
git clone https://github.com/baie20070701-arch/szu-net-autologin.git
```

### macOS

macOS 一般已经带有 `python3`。本项目要求 Python 3.10 或更高版本。

```bash
git clone https://github.com/baie20070701-arch/szu-net-autologin.git
```

## Windows 使用

进入仓库目录，双击：

1. `setup_windows.bat`：输入学号和密码，生成配置文件。
2. `test_windows.bat`：检查状态，并在离线时尝试登录一次。
3. `install_windows.bat`：安装当前用户的计划任务，登录 Windows 后自动在后台运行。

查看日志：

```powershell
Get-Content "$env:USERPROFILE\.config\szu-autologin\autologin.log" -Wait
```

卸载：

```text
双击 uninstall_windows.bat
```

计划任务名称为 `SZUNetAutoLogin`。它会：

- 在当前用户登录时启动
- 使用 `pythonw.exe` 隐藏窗口运行
- 使用电池时继续运行
- 进程异常退出后自动重启
- 错过启动时间后尽可能补启动

## macOS 使用

进入仓库目录，双击：

1. `setup_macos.command`：输入学号和密码，生成配置文件。
2. `test_macos.command`：检查状态，并在离线时尝试登录一次。
3. `install_macos.command`：安装 `launchd` 后台服务。

也可以直接使用终端：

```bash
python3 szu_autologin.py init
python3 szu_autologin.py status
python3 szu_autologin.py once
./install_macos.sh
```

查看日志：

```bash
tail -f ~/Library/Logs/szu-autologin.out.log
tail -f ~/Library/Logs/szu-autologin.err.log
```

卸载：

```text
双击 uninstall_macos.command
```

或：

```bash
./uninstall_macos.sh
```

## 通用命令行

```bash
python3 szu_autologin.py init              # 交互式保存账号和密码
python3 szu_autologin.py status            # 只检测在线状态
python3 szu_autologin.py once              # 离线时尝试登录一次
python3 szu_autologin.py run               # 持续监控并自动重连
python3 szu_autologin.py init --force      # 强制覆盖已有配置
```

`status` 退出码：

- `0`：在线
- `1`：离线
- `2`：无法访问门户或响应异常

## 配置文件

默认位置：

```text
Windows: %USERPROFILE%\.config\szu-autologin\config.json
macOS:   ~/.config/szu-autologin/config.json
```

内容示例：

```json
{
  "portal": "http://172.30.255.42",
  "username": "你的学号",
  "password": "你的密码",
  "check_interval": 20,
  "login_retry_interval": 300,
  "timeout": 5
}
```

密码不会写进脚本代码或日志。macOS 下配置文件权限会设置为 `600`；Windows 下请勿把该文件发送给其他人。

## 常见问题

### 已经在线但脚本仍然登录？

先运行：

```bash
python3 szu_autologin.py status
```

只有在状态接口返回离线时，脚本才会提交登录。

### 登录失败

1. 确认已连接深大 Wi-Fi 或校园网。
2. 确认学号和密码可以在原认证页面正常登录。
3. 若你使用移动、联通、电信入口，请在 `username` 中填写门户要求的完整账号后缀。
4. 修改密码后重新运行 `init --force`。

### 页面接口以后发生变化

本项目根据当前 `172.30.255.42` 的 Dr.COM Eportal 页面实现。如果学校升级认证系统，接口可能变化，需要同步修改。

## 项目结构

```text
szu_autologin.py         跨平台主程序
install_windows.ps1      Windows 计划任务安装脚本
uninstall_windows.ps1    Windows 计划任务卸载脚本
install_macos.sh         macOS launchd 安装脚本
uninstall_macos.sh       macOS launchd 卸载脚本
tests/                   不访问校园网的单元测试
.github/workflows/       Windows、macOS、Linux 跨平台 CI
```

## 许可证

MIT
