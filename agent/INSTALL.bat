@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Monitor Agent install
echo  Python not required
echo ============================================
echo.
echo Right-click this file -^> Run as administrator
echo.
if not exist "%~dp0MonitorAgent.exe" (
  echo ERROR: MonitorAgent.exe not found
  pause
  exit /b 1
)

set /p TOKEN=Agent token: 
set /p HOSTNAME=Point name (e.g. Kassa-1): 

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -AgentToken "%TOKEN%" -Hostname "%HOSTNAME%"
echo.
pause
