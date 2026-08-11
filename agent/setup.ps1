# Установка агента мониторинга мониторов для сотрудников.
# Запускать PowerShell от имени администратора.
#
# Пример:
#   .\setup.ps1 -AgentToken "xxxx" -Hostname "Касса-1"
# Удаление автозапуска:
#   .\setup.ps1 -Uninstall

param(
    [string]$AgentToken = "",
    [string]$Hostname = "",
    [string]$ServerUrl = "http://94.159.18.22:8787",
    [string]$PythonExe = "python",
    [string]$TaskName = "MonitorAgent",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $AgentDir "config.json"
$ExamplePath = Join-Path $AgentDir "config.example.json"
$AgentScript = Join-Path $AgentDir "agent.py"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Запустите PowerShell от имени администратора."
    }
}

function Get-PythonPath {
    $cmd = Get-Command $PythonExe -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Python не найден ($PythonExe). Установите Python 3.11+ с галкой Add to PATH."
    }
    return $cmd.Source
}

Assert-Admin

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$AgentScript*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "Автозапуск '$TaskName' удалён."
    exit 0
}

if (-not (Test-Path $AgentScript)) {
    throw "Не найден agent.py в $AgentDir"
}

$pythonPath = Get-PythonPath
Write-Host "Python: $pythonPath"
Write-Host "Папка агента: $AgentDir"

Write-Host "Установка зависимостей..."
& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $AgentDir "requirements.txt")

if (-not (Test-Path $ConfigPath)) {
    if (-not (Test-Path $ExamplePath)) {
        throw "Нет config.json и config.example.json"
    }
    Copy-Item $ExamplePath $ConfigPath
    Write-Host "Создан config.json из примера."
}

$config = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$config.server_url = $ServerUrl
if ($AgentToken) { $config.agent_token = $AgentToken }
if ($Hostname) { $config.hostname = $Hostname }

if (-not $config.agent_token -or $config.agent_token -like "*PASTE*" -or $config.agent_token -like "*ТОКЕН*") {
    throw "Укажите токен: .\setup.ps1 -AgentToken `"ВАШ_ТОКЕН`" -Hostname `"Касса-1`""
}

$config | ConvertTo-Json -Depth 5 | Set-Content -Path $ConfigPath -Encoding UTF8
Write-Host "config.json сохранён."
Write-Host "  server_url = $($config.server_url)"
Write-Host "  hostname   = $($config.hostname)"
Write-Host "  token      = $($config.agent_token.Substring(0, [Math]::Min(8, $config.agent_token.Length)))..."

Write-Host "Проверка сервера..."
try {
    $health = Invoke-RestMethod -Uri ($config.server_url.TrimEnd('/') + "/health") -TimeoutSec 10
    Write-Host "Сервер отвечает: $($health | ConvertTo-Json -Compress)"
} catch {
    Write-Warning "Сервер пока не ответил: $($_.Exception.Message)"
    Write-Warning "Агент всё равно будет установлен. Проверьте сеть/firewall."
}

# Автозапуск при входе пользователя (нужно для DDC/CI к монитору)
$pythonw = Join-Path (Split-Path $pythonPath -Parent) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $pythonPath }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$AgentScript`"" -WorkingDirectory $AgentDir
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggerLogon -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Готово."
Write-Host "- Задача планировщика: $TaskName"
Write-Host "- Лог: $(Join-Path $AgentDir 'agent.log')"
Write-Host "- Остановка автозапуска: .\setup.ps1 -Uninstall"
