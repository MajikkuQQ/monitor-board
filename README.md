# Monitor Board

Мониторинг питания мониторов на Windows mini PC / кассах.

Агент на точке опрашивает монитор через **DDC/CI** (реальный Power Mode) и шлёт heartbeat на сервер.  
Сервер хранит историю отключений, показывает **веб-панель** и шлёт алерты в **Telegram**.

```text
Windows mini PC  --heartbeat-->  Server (FastAPI + SQLite)
                                      ├── Web dashboard
                                      └── Telegram bot
```

Почему DDC/CI, а не список дисплеев Windows: при USB-C / одном кабеле питания+видео Windows часто не видит выключение монитора кнопкой, а DDC/CI видит.

## Возможности

- Веб-дашборд (тёмная тема, карточки точек, история)
- Telegram-бот: алерты, `/add_point`, `/stats`
- Детект offline агента (нет heartbeat)
- Windows-агент + GUI-установщик `.exe` (Python на точке не нужен)
- Запуск сервера через systemd (удобно в Proxmox LXC) или Docker

## Быстрый старт (сервер)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# заполните TELEGRAM_TOKEN и ADMIN_API_KEY
python -m server.main
```

Откройте `http://SERVER:8787/` — пароль веб-панели = `WEB_PASSWORD` или `ADMIN_API_KEY`.

Полная установка на Proxmox / Debian: **[INSTALL.md](INSTALL.md)**

## Агент для сотрудников

Сборка установщика:

```powershell
cd agent
.\build.ps1
```

Выдать: `agent/release/monitor-agent/MonitorAgentSetup.exe`  
Сотрудник запускает от администратора → вводит токен и имя точки → автозапуск создаётся сам.

- [agent/ПУБЛИКАЦИЯ-BUILDIN.md](agent/ПУБЛИКАЦИЯ-BUILDIN.md) — текст для базы знаний  
- [agent/README.md](agent/README.md) — детали агента  

Создать точку и токен: в Telegram `/add_point ИмяТочки`

## Структура

```text
├── server/              # FastAPI + веб + Telegram
├── agent/               # Windows agent + installer
├── INSTALL.md           # полная установка сервера
├── DEPLOY-PROXMOX.md
├── DEPLOY-SAMBA.md
├── docker-compose.yml
└── .env.example
```

## Переменные окружения

См. [.env.example](.env.example). Обязательные:

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_TOKEN` | токен бота |
| `ADMIN_API_KEY` | ключ admin API / пароль веб по умолчанию |
| `TELEGRAM_API_BASE` | по умолчанию `https://t.api.lookinsoft.ru` |
| `ALLOWED_USER_IDS` | whitelist Telegram id через запятую; пусто = все |
| `WEB_PASSWORD` | пароль сайта; пусто = `ADMIN_API_KEY` |
| `PORT` | по умолчанию `8787` |

## API агента

`POST /api/v1/heartbeat`  
`Authorization: Bearer <agent_token>`

```json
{
  "hostname": "Касса-1",
  "monitors": [{ "key": "ddc:1:Display", "name": "Display" }]
}
```

В списке — только мониторы с питанием ON. Отсутствующий монитор = offline.

## Лицензия

MIT — см. [LICENSE](LICENSE)
