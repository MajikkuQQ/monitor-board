@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Агент мониторинга мониторов
echo  Установка (Python не нужен)
echo ============================================
echo.
echo Запускайте файл ПРАВОЙ кнопкой мыши -
echo "Запуск от имени администратора"
echo.
if not exist "%~dp0MonitorAgent.exe" (
  echo ОШИБКА: рядом нет MonitorAgent.exe
  pause
  exit /b 1
)

set /p TOKEN=Токен точки от администратора: 
set /p HOSTNAME=Имя точки (например Касса-1): 

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -AgentToken "%TOKEN%" -Hostname "%HOSTNAME%"
echo.
pause
