# Install monitor agent as a Windows service via NSSM.
# Prerequisites:
#   1. Python 3.11+ installed and on PATH
#   2. NSSM available as `nssm` on PATH (https://nssm.cc/download)
#   3. agent/config.json filled
#
# Usage (PowerShell as Administrator):
#   .\install_service.ps1
#   .\install_service.ps1 -ServiceName MonitorAgent -PythonExe "C:\Python311\python.exe"

param(
    [string]$ServiceName = "MonitorAgent",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentScript = Join-Path $AgentDir "agent.py"
$ConfigPath = Join-Path $AgentDir "config.json"

if (-not (Test-Path $AgentScript)) {
    throw "agent.py not found: $AgentScript"
}
if (-not (Test-Path $ConfigPath)) {
    throw "config.json not found. Copy config.example.json to config.json first."
}

$pythonCmd = Get-Command $PythonExe -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    throw "Python executable not found: $PythonExe"
}
$pythonResolved = $pythonCmd.Source

$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    throw "nssm not found on PATH. Install NSSM and retry."
}

Write-Host "Installing service '$ServiceName'..."
& nssm stop $ServiceName 2>$null
& nssm remove $ServiceName confirm 2>$null

& nssm install $ServiceName $pythonResolved $AgentScript
& nssm set $ServiceName AppDirectory $AgentDir
& nssm set $ServiceName AppStdout (Join-Path $AgentDir "service-stdout.log")
& nssm set $ServiceName AppStderr (Join-Path $AgentDir "service-stderr.log")
& nssm set $ServiceName AppRotateFiles 1
& nssm set $ServiceName Start SERVICE_AUTO_START
& nssm set $ServiceName AppExit Default Restart

& nssm start $ServiceName
Write-Host "Service '$ServiceName' installed and started."
Write-Host "Logs: $AgentDir\agent.log , service-stdout.log , service-stderr.log"
