$ErrorActionPreference = "Stop"
$TaskName = "SZUNetAutoLogin"
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($null -eq $Task) {
    Write-Host "计划任务不存在：$TaskName"
    exit 0
}

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "已卸载 Windows 计划任务：$TaskName" -ForegroundColor Green
