@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  Установка агента мониторинга мониторов
echo ============================================
echo.
echo Запускайте этот файл ПРАВОЙ кнопкой ->
echo "Запуск от имени администратора"
echo.
set /p TOKEN=Вставьте токен точки от администратора: 
set /p HOSTNAME=Имя точки (например Касса-1): 

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -AgentToken "%TOKEN%" -Hostname "%HOSTNAME%"
echo.
pause
