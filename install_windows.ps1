$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptPath = Join-Path $ScriptDir "szu_autologin.py"
$ConfigPath = Join-Path $env:USERPROFILE ".config\szu-autologin\config.json"
$LogPath = Join-Path $env:USERPROFILE ".config\szu-autologin\autologin.log"
$TaskName = "SZUNetAutoLogin"
$TaskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    Write-Host "未找到配置文件：$ConfigPath" -ForegroundColor Red
    Write-Host "请先双击 setup_windows.bat 保存账号密码。"
    exit 1
}

$PythonPrefix = @()
$PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -ne $PythonCommand) {
    $PythonExe = $PythonCommand.Source
    $PythonDir = Split-Path -Parent $PythonExe
    $PythonwExe = Join-Path $PythonDir "pythonw.exe"
    if (Test-Path -LiteralPath $PythonwExe) {
        $Runner = $PythonwExe
    } else {
        $Runner = $PythonExe
    }
} else {
    $PyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -eq $PyLauncher) {
        throw "未找到 Python。请先安装 Python 3.10 或更高版本，并勾选 Add python.exe to PATH。"
    }
    $PyLauncherDir = Split-Path -Parent $PyLauncher.Source
    $PywLauncher = Join-Path $PyLauncherDir "pyw.exe"
    if (Test-Path -LiteralPath $PywLauncher) {
        $Runner = $PywLauncher
    } else {
        $Runner = $PyLauncher.Source
    }
    $PythonPrefix = @("-3")
}

$ScriptArg = '"' + $ScriptPath + '"'
$ConfigArg = '"' + $ConfigPath + '"'
$LogArg = '"' + $LogPath + '"'
$Arguments = ($PythonPrefix + @($ScriptArg, "--config", $ConfigArg, "--log-file", $LogArg, "run")) -join " "

$Action = New-ScheduledTaskAction `
    -Execute $Runner `
    -Argument $Arguments `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $TaskUser

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$Description = "深圳大学 Dr.COM 内网断线自动重连"
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "已安装 Windows 计划任务：$TaskName" -ForegroundColor Green
Write-Host "配置文件：$ConfigPath"
Write-Host "运行日志：$LogPath"
