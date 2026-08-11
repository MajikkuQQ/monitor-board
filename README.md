# Monitor Board

Мониторинг питания мониторов на Windows mini PC / кассах.

Агент на точке опрашивает монитор через **DDC/CI** и шлёт heartbeat на сервер.  
Сервер хранит историю отключений, показывает **веб-панель** и шлёт алерты в **Telegram**.

```text
Windows PC  --heartbeat-->  Server (FastAPI + SQLite)
                               ├── Web dashboard
                               └── Telegram bot
```

## Возможности

- Веб-дашборд: статусы точек, история отключений
- Telegram-бот: алерты, `/add_point`, `/stats`
- Детект offline агента (нет heartbeat)
- Windows-агент с GUI-установщиком `.exe`

## Установка сервера

Нужны: Linux (Debian/Ubuntu и т.п.), Python 3.11+, токен Telegram-бота.

```bash
git clone https://github.com/MajikkuQQ/monitor-board.git
cd monitor-board

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # TELEGRAM_TOKEN, ADMIN_API_KEY, при необходимости WEB_PASSWORD

mkdir -p data
python -m server.main
```

Откройте `http://SERVER:8787/` — пароль = `WEB_PASSWORD` или `ADMIN_API_KEY`.

Автозапуск через systemd — в **[INSTALL.md](INSTALL.md)**.

## Агент (только .exe)

Сборка установщика (на машине разработчика):

```powershell
cd agent
.\build.ps1
```

Результат: `agent/release/monitor-agent/MonitorAgentSetup.exe`

Сотруднику:
1. Запустить `MonitorAgentSetup.exe` **от администратора**
2. Ввести токен точки и имя
3. Нажать «Установить»

Автозапуск при входе в Windows создаётся сам. Python на точке не нужен.

Токен точки: в Telegram `/add_point ИмяТочки`.

Подробнее: [agent/README.md](agent/README.md)

## Структура

```text
├── server/          # API, веб, Telegram
├── agent/           # исходники агента + сборка Setup.exe
├── INSTALL.md       # сервер: venv + systemd
├── .env.example
└── requirements.txt
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_TOKEN` | токен бота |
| `ADMIN_API_KEY` | ключ admin API / пароль веб по умолчанию |
| `TELEGRAM_API_BASE` | по умолчанию `https://t.api.lookinsoft.ru` |
| `ALLOWED_USER_IDS` | whitelist id через запятую; пусто = все |
| `WEB_PASSWORD` | пароль сайта; пусто = `ADMIN_API_KEY` |
| `PORT` | по умолчанию `8787` |

## Лицензия

MIT — [LICENSE](LICENSE)
