# Установка MonitorAgent.exe (без Python).
# Запуск от администратора:
#   .\setup.ps1 -AgentToken "xxxx" -Hostname "Касса-1"
#   .\setup.ps1 -Uninstall

param(
    [string]$AgentToken = "",
    [string]$Hostname = "",
    [string]$ServerUrl = "http://94.159.18.22:8787",
    [string]$TaskName = "MonitorAgent",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $AgentDir "MonitorAgent.exe"
$ConfigPath = Join-Path $AgentDir "config.json"
$ExamplePath = Join-Path $AgentDir "config.example.json"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run as Administrator (right-click INSTALL.bat)."
    }
}

Assert-Admin

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Get-Process -Name "MonitorAgent" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Автозапуск удалён, процесс остановлен."
    exit 0
}

if (-not (Test-Path $ExePath)) {
    throw "Не найден MonitorAgent.exe рядом со скриптом."
}

if (-not (Test-Path $ConfigPath)) {
    if (-not (Test-Path $ExamplePath)) { throw "Нет config.example.json" }
    Copy-Item $ExamplePath $ConfigPath
}

$config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$config.server_url = $ServerUrl
if ($AgentToken) { $config.agent_token = $AgentToken }
if ($Hostname) { $config.hostname = $Hostname }

if (-not $config.agent_token -or $config.agent_token -match "PASTE|ТОКЕН") {
    throw "Укажите токен: .\setup.ps1 -AgentToken `"ТОКЕН`" -Hostname `"Касса-1`""
}

$config | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8
Write-Host "config.json сохранён (host=$($config.hostname))."

try {
    $health = Invoke-RestMethod -Uri ($ServerUrl.TrimEnd('/') + "/health") -TimeoutSec 10
    Write-Host "Сервер OK: $($health | ConvertTo-Json -Compress)"
} catch {
    Write-Warning "Сервер не ответил: $($_.Exception.Message). Установка продолжается."
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Get-Process -Name "MonitorAgent" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $ExePath -WorkingDirectory $AgentDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Start-Sleep -Seconds 2
if (Get-Process -Name "MonitorAgent" -ErrorAction SilentlyContinue) {
    Write-Host "MonitorAgent.exe запущен."
} else {
    Write-Warning "Процесс не видно сразу — проверьте agent.log и Планировщик задач ($TaskName)."
}

Write-Host ""
Write-Host "Готово. Лог: $(Join-Path $AgentDir 'agent.log')"
Write-Host "Удаление: .\setup.ps1 -Uninstall"
