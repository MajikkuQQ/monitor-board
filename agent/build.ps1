# Build MonitorAgent.exe + MonitorAgentSetup.exe
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

$ReleaseDir = Join-Path $AgentDir "release\monitor-agent"
if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null

Copy-Item $SetupExe $ReleaseDir
Copy-Item (Join-Path $AgentDir "README.md") (Join-Path $ReleaseDir "README.md")

$ZipPath = Join-Path $AgentDir "release\monitor-agent.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "OK"
Write-Host "  Setup: $SetupExe"
Write-Host "  ZIP:   $ZipPath"
