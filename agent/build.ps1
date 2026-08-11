# Build single MonitorAgentSetup.exe for distribution.
# Run from agent folder:
#   .\build.ps1

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $AgentDir

$ProjectRoot = Split-Path $AgentDir -Parent
$VenvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = "python"
}

Write-Host "Python: $VenvPy"
& $VenvPy -m pip install -q pyinstaller httpx

Write-Host "Building MonitorAgent.exe ..."
& $VenvPy -m PyInstaller --noconfirm --clean MonitorAgent.spec
$DistExe = Join-Path $AgentDir "dist\MonitorAgent.exe"
if (-not (Test-Path $DistExe)) {
    throw "Build failed: dist\MonitorAgent.exe not found"
}

Write-Host "Building MonitorAgentSetup.exe ..."
& $VenvPy -m PyInstaller --noconfirm --clean MonitorAgentSetup.spec
$SetupExe = Join-Path $AgentDir "dist\MonitorAgentSetup.exe"
if (-not (Test-Path $SetupExe)) {
    throw "Build failed: dist\MonitorAgentSetup.exe not found"
}

$OutDir = Join-Path $AgentDir "release"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutExe = Join-Path $OutDir "MonitorAgentSetup.exe"
Copy-Item $SetupExe $OutExe -Force

Write-Host ""
Write-Host "OK: $OutExe"
