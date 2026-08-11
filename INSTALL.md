# Установка сервера

Обычная установка на Linux: Python venv + systemd.

## 1. Подготовка

- Сервер с Debian/Ubuntu (или аналогичный Linux)
- Python 3.11+
- Токен бота от [@BotFather](https://t.me/BotFather)
- Открытый порт (по умолчанию **8787**) для агентов и веб-панели

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ca-certificates curl git
```

## 2. Код

```bash
sudo mkdir -p /opt/monitor-board
sudo chown "$USER":"$USER" /opt/monitor-board
git clone https://github.com/MajikkuQQ/monitor-board.git /opt/monitor-board
cd /opt/monitor-board
```

Или скопируйте файлы проекта в `/opt/monitor-board` любым удобным способом.

## 3. Окружение

```bash
cd /opt/monitor-board
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

cp .env.example .env
nano .env
```

Пример `.env`:

```env
TELEGRAM_TOKEN=123456:ABCDEF
TELEGRAM_API_BASE=https://t.api.lookinsoft.ru
ALLOWED_USER_IDS=
ADMIN_API_KEY=сгенерируйте_ниже
WEB_PASSWORD=пароль_для_сайта
DATABASE_PATH=./data/monitors.db
OFFLINE_THRESHOLD_SEC=180
HOST=0.0.0.0
PORT=8787
```

```bash
openssl rand -hex 32   # значение для ADMIN_API_KEY
mkdir -p data
```

- `ALLOWED_USER_IDS` — Telegram user id через запятую; пусто = доступ всем  
- `WEB_PASSWORD` — пароль входа на сайт; если пусто, используется `ADMIN_API_KEY`

## 4. Проверка вручную

```bash
cd /opt/monitor-board
set -a && source .env && set +a
.venv/bin/python -m server.main
```

В другом терминале:

```bash
curl http://127.0.0.1:8787/health
# {"status":"ok"}
```

Остановка: `Ctrl+C`.

## 5. systemd

```bash
sudo tee /etc/systemd/system/monitor-board.service >/dev/null <<'EOF'
[Unit]
Description=Monitor Board
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/monitor-board
EnvironmentFile=/opt/monitor-board/.env
ExecStart=/opt/monitor-board/.venv/bin/python -m server.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now monitor-board
sudo systemctl status monitor-board --no-pager
curl http://127.0.0.1:8787/health
```

Логи:

```bash
journalctl -u monitor-board -f
```

## 6. Доступ снаружи

На роутере / firewall пробросьте **TCP 8787** на IP сервера.

Проверка:

```text
http://ВАШ_IP_ИЛИ_ДОМЕН:8787/
http://ВАШ_IP_ИЛИ_ДОМЕН:8787/health
```

## 7. Telegram и точки

1. Напишите боту `/start`
2. Создайте точку: `/add_point Касса-1`
3. Полученный токен отдайте для установки агента (`MonitorAgentSetup.exe`)

## 8. Обновление

```bash
cd /opt/monitor-board
git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart monitor-board
```

## Полезные команды

| Действие | Команда |
|----------|---------|
| Статус | `systemctl status monitor-board` |
| Перезапуск | `systemctl restart monitor-board` |
| Логи | `journalctl -u monitor-board -f` |
| Бэкап БД | `cp /opt/monitor-board/data/monitors.db ~/monitors-backup.db` |

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| Сервис падает на `allowed_user_ids` | В `.env`: `ALLOWED_USER_IDS=` или `123,456` (не JSON) |
| Бот молчит | Проверьте `TELEGRAM_TOKEN` и доступ к `TELEGRAM_API_BASE` |
| Агенты не коннектятся | Открыт ли порт 8787 снаружи, слушает ли `HOST=0.0.0.0` |
