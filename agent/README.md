# Windows-агент

Установка на точках — один файл **`MonitorAgentSetup.exe`**.

## Скачать

https://github.com/MajikkuQQ/monitor-board/releases/latest/download/MonitorAgentSetup.exe

## Установка

1. Запустить от имени администратора  
2. Ввести токен и имя точки  
3. Нажать «Установить»  

Автозапуск создаётся сам. Python не нужен.

Токен: Telegram `/add_point ИмяТочки`.

## Сборка

```powershell
cd agent
.\build.ps1
```

Результат: `release/MonitorAgentSetup.exe`
