# Агент мониторинга мониторов

Для сотрудников используйте **готовый exe-пакет** (Python не нужен).

## Сборка пакета (администратор)

На ПК с Python:

```powershell
cd C:\Users\Гришаня\monitor-telegram-bot\agent
.\build.ps1
```

Результат:

- `release\monitor-agent\` — папка для копирования  
- `release\monitor-agent.zip` — для BuildIn  

Инструкция сотруднику внутри пакета: `README-EXE.md` (в zip попадёт как `README.md`).  
Текст для BuildIn: [ПУБЛИКАЦИЯ-BUILDIN.md](ПУБЛИКАЦИЯ-BUILDIN.md)

## Установка на точке (сотрудник)

1. Распаковать zip в `C:\monitor-agent\`
2. `УСТАНОВКА.bat` → от администратора
3. Ввести токен и имя точки

## Исходники (разработка)

| Файл | Назначение |
|------|------------|
| `agent.py` / `monitors.py` | код агента (DDC/CI) |
| `MonitorAgent.spec` | сборка PyInstaller |
| `build.ps1` | сборка exe + zip |
| `setup-exe.ps1` | установщик для exe-пакета |
| `setup.ps1` | старый установщик через Python (если нужно) |

Сервер менять не нужно: тот же heartbeat API.
