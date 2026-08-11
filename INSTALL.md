# Полная установка с нуля

Система мониторинга мониторов на mini PC (Windows) + центральный сервер (Proxmox / Debian).

**Что получите:**
- веб-панель: `http://94.159.18.22:8787/`
- Telegram-бот (алерты + команды)
- агент на каждой точке (DDC/CI)

**Параметры по умолчанию:**

| Параметр | Значение |
|----------|----------|
| Внешний адрес | `94.159.18.22` |
| Порт | `8787` |
| Telegram API | `https://t.api.lookinsoft.ru` |
| Код на ПК | `C:\Users\Гришаня\monitor-telegram-bot` |
| Код на сервере | `/opt/monitor-telegram-bot` |

---

## 0. Что подготовить заранее

1. Токен Telegram-бота от [@BotFather](https://t.me/BotFather).
2. Свой Telegram user id (например через `@userinfobot`) — для whitelist.
3. Доступ к Proxmox и к CT, куда будете ставить.
4. На mini PC: Windows 10 + Python 3.11+.

---

## 1. Создать CT в Proxmox

### 1.1. Скачать шаблон Debian

На хосте Proxmox (Shell):

```bash
pveam update
pveam available | grep debian
pveam download local debian-12-standard_12.7-1_amd64.tar.zst
```

Имя файла возьми из вывода `pveam available` (версия может отличаться).

### 1.2. Create CT

| Поле | Значение |
|------|----------|
| Hostname | `monitor-telegram-bot` |
| Unprivileged | лучше **снять** (проще Docker) |
| Nesting | **включить** |
| Пароль | задай root-пароль |
| Шаблон | Debian 12 |
| Диск | 8–64 GB |
| CPU | 1–2 |
| RAM | 1024 MB |
| Swap | 0 или 512 |
| Сеть | Bridge `vmbr0`, статический **LAN IP** (пример: `192.168.1.150`) |
| DNS | `1.1.1.1` или DNS провайдера |

**Start** CT. Запомни LAN IP — ниже везде `IP_CT`.

---

## 2. Загрузить проект на CT (через Samba)

### 2.1. Samba на CT

Зайди в консоль CT (`pct enter CTID` или SSH):

```bash
apt update
apt install -y samba
mkdir -p /opt/monitor-telegram-bot
chmod 777 /opt/monitor-telegram-bot

adduser --disabled-password --gecos "" share
smbpasswd -a share
smbpasswd -e share
```

В конец `/etc/samba/smb.conf`:

```ini
[deploy]
   path = /opt/monitor-telegram-bot
   browseable = yes
   read only = no
   guest ok = no
   valid users = share
   create mask = 0666
   directory mask = 0777
   force user = root
```

```bash
testparm -s
systemctl enable --now smbd nmbd
hostname -I
```

### 2.2. Копирование с Windows

В проводнике:

```text
\\IP_CT\deploy
```

Пример: `\\192.168.1.150\deploy`  
Логин: `share`, пароль из `smbpasswd`.

Скопируй **содержимое** папки:

```text
C:\Users\Гришаня\monitor-telegram-bot\
```

**Нужно:**
- `server/`
- `agent/`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env.example`
- `INSTALL.md`, `README.md` (по желанию)

**Не копируй:**
- `.venv\`
- `data\`
- `__pycache__\`

Проверка на CT:

```bash
cd /opt/monitor-telegram-bot
ls
# Dockerfile  docker-compose.yml  requirements.txt  server  agent  .env.example
```

---

## 3. Настроить `.env`

```bash
cd /opt/monitor-telegram-bot
cp .env.example .env
nano .env
```

Пример:

```env
TELEGRAM_TOKEN=123456:ABCDEF_от_BotFather
TELEGRAM_API_BASE=https://t.api.lookinsoft.ru
ALLOWED_USER_IDS=123456789
# несколько: 123,456  | пусто = все | не пиши [123]
ADMIN_API_KEY=сгенерируй_ниже
WEB_PASSWORD=пароль_для_браузера
DATABASE_PATH=./data/monitors.db
OFFLINE_THRESHOLD_SEC=180
HOST=0.0.0.0
PORT=8787
```

Сгенерировать `ADMIN_API_KEY` (пробел обязателен):

```bash
openssl rand -hex 32
```

- `ALLOWED_USER_IDS` — твой Telegram id (можно несколько через запятую). Пусто = доступ всем.
- `WEB_PASSWORD` — пароль входа на сайт. Если пусто — используется `ADMIN_API_KEY`.
- Для запуска **без Docker** (рекомендуется на Proxmox LXC) путь БД: `./data/monitors.db`.

Подсказка: `.env` удобнее править через Samba (`\\IP_CT\deploy\.env` в Блокноте), если в консоли Proxmox плохо вставляется текст.

---

## 4. Запуск сервера без Docker (рекомендуется на LXC)

На CT:

```bash
apt update
apt install -y python3 python3-venv python3-pip ca-certificates curl

cd /opt/monitor-telegram-bot
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

mkdir -p data

# убедись что .env заполнен (шаг 3)
grep -E 'TELEGRAM_TOKEN|ADMIN_API_KEY|PORT|DATABASE_PATH' .env
```

Создай systemd-службу:

```bash
cat >/etc/systemd/system/monitor-bot.service <<'EOF'
[Unit]
Description=Monitor Board + Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/monitor-telegram-bot
EnvironmentFile=/opt/monitor-telegram-bot/.env
ExecStart=/opt/monitor-telegram-bot/.venv/bin/python -m server.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now monitor-bot
systemctl status monitor-bot --no-pager
```

Логи:

```bash
journalctl -u monitor-bot -f
```

Проверка:

```bash
curl http://127.0.0.1:8787/health
# {"status":"ok"}
```

Полезное:

```bash
systemctl restart monitor-bot
systemctl stop monitor-bot
```

После обновления файлов через Samba:

```bash
cd /opt/monitor-telegram-bot
.venv/bin/pip install -r requirements.txt
systemctl restart monitor-bot
```

### Альтернатива: Docker

Только если CT **Privileged + Nesting**. Иначе будет `permission denied` на `/proc`.

```bash
apt install -y docker.io docker-compose
systemctl enable --now docker
cd /opt/monitor-telegram-bot
# в .env для Docker лучше: DATABASE_PATH=/app/data/monitors.db
docker-compose up -d --build
```

---

## 5. Открыть порт 8787 на внешку

Агенты и браузер ходят на:

```text
http://94.159.18.22:8787
```

### 5.1. Проброс с хоста Proxmox → CT

На **хосте Proxmox** (не в CT), подставь свой `IP_CT`:

```bash
iptables -t nat -A PREROUTING -p tcp -d 94.159.18.22 --dport 8787 -j DNAT --to-destination IP_CT:8787
iptables -A FORWARD -p tcp -d IP_CT --dport 8787 -j ACCEPT
```

Сохранить правила:

```bash
apt install -y iptables-persistent
netfilter-persistent save
```

Или настрой DNAT/Firewall в UI Proxmox / на роутере:  
**WAN TCP 8787 → IP_CT:8787**.

### 5.2. Firewall в CT (если ufw включён)

```bash
ufw allow 8787/tcp
ufw allow OpenSSH
ufw enable
```

### 5.3. Проверка снаружи

С любой машины в интернете:

```bash
curl http://94.159.18.22:8787/health
```

В браузере открой:

```text
http://94.159.18.22:8787/
```

Войди паролем `WEB_PASSWORD` (или `ADMIN_API_KEY`).

---

## 6. Telegram-бот

1. Напиши боту `/start`.
2. Создай точку:

```text
/add_point Касса-1
```

3. Бот пришлёт `agent_token` — сохрани.

Команды:

| Команда | Действие |
|---------|----------|
| `/start` | список точек |
| `/add_point Имя` | создать точку + токен |
| `/stats` | статистика |
| `/alerts Имя on\|off` | алерты точки |

Алерты приходят при отключении/включении монитора и при пропаже агента.

---

## 7. Агент на Windows mini PC

На **каждой** точке:

### 7.1. Установка

1. Установи [Python 3.11+](https://www.python.org/downloads/) (галка «Add to PATH»).
2. Скопируй папку `agent` с сервера/с ПК, например в `C:\monitor-agent\`.
3. В PowerShell:

```powershell
cd C:\monitor-agent
python -m pip install -r requirements.txt
copy config.example.json config.json
notepad config.json
```

### 7.2. config.json

```json
{
  "server_url": "http://94.159.18.22:8787",
  "agent_token": "ТОКЕН_ИЗ_/add_point",
  "hostname": "Касса-1",
  "poll_interval_sec": 5,
  "debounce_checks": 3,
  "request_timeout_sec": 10
}
```

- `agent_token` — свой для каждой точки.
- `hostname` — понятное имя (опционально).

### 7.3. Проверка вручную

```powershell
python agent.py
```

В логе должно быть `Heartbeat ok`.  
На сайте точка станет зелёной.  
Выключи монитор кнопкой → через ~15 с алерт в Telegram и красная карточка на сайте.

Остановка: `Ctrl+C`.

### 7.4. Автозапуск (служба NSSM)

1. Скачай [NSSM](https://nssm.cc/download), добавь `nssm.exe` в PATH.
2. PowerShell **от администратора**:

```powershell
cd C:\monitor-agent
.\install_service.ps1
```

Либо Планировщик заданий: при входе в систему запускать  
`pythonw.exe C:\monitor-agent\agent.py`.

---

## 8. Как это работает (кратко)

```text
Mini PC (агент, DDC/CI)
    │  каждые 5 сек heartbeat
    ▼
http://94.159.18.22:8787
    ├── веб-панель (браузер)
    ├── Telegram-бот (алерты)
    └── SQLite (история отключений)
```

Агент спрашивает монитор по **DDC/CI** (питание on/off), а не по списку дисплеев Windows — это нужно для USB-C / одного кабеля.

---

## 9. Обновление кода потом

1. Снова скопируй файлы в `\\IP_CT\deploy` (без `.venv` / `data`).
2. На CT:

```bash
cd /opt/monitor-telegram-bot
docker compose up -d --build
```

Агенты: обнови папку `agent` на точках и перезапусти службу.

---

## 10. Полезные команды

| Действие | Где | Команда |
|----------|-----|---------|
| Логи сервера | CT | `journalctl -u monitor-bot -f` |
| Перезапуск | CT | `systemctl restart monitor-bot` |
| Стоп | CT | `systemctl stop monitor-bot` |
| Статус | CT | `systemctl status monitor-bot` |
| Бэкап БД | CT | `cp /opt/monitor-telegram-bot/data/monitors.db ~/monitors-$(date +%F).db` |
| Создать точку API | любая машина | см. ниже |

```bash
curl -X POST http://94.159.18.22:8787/admin/endpoints \
  -H "X-Admin-Key: ТВОЙ_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Касса-2\"}"
```

---

## 11. Чеклист «всё работает»

- [ ] `curl http://127.0.0.1:8787/health` на CT → ok  
- [ ] `curl http://94.159.18.22:8787/health` снаружи → ok  
- [ ] Браузер: вход на `http://94.159.18.22:8787/`  
- [ ] Telegram: `/start`, `/add_point Тест`  
- [ ] Агент на точке: `Heartbeat ok`  
- [ ] Точка зелёная на сайте  
- [ ] Выключение монитора кнопкой → алерт + красная карточка  

---

## 12. Частые проблемы

| Проблема | Что проверить |
|----------|----------------|
| Снаружи нет `/health` | DNAT/порт 8787, firewall, `docker compose ps` |
| Бот молчит | `TELEGRAM_TOKEN`, доступ CT к `t.api.lookinsoft.ru`, логи |
| Не пускает на сайт | пароль `WEB_PASSWORD` / `ADMIN_API_KEY` |
| Агент connection error | с mini PC: `curl http://94.159.18.22:8787/health` |
| Монитор не детектится | монитор должен поддерживать DDC/CI; запусти `python agent.py` и смотри лог |
| Samba «не найдено сетевое имя» | `net use Z: \\IP_CT\deploy /user:share` (пробел после `Z:`) |
| Docker в LXC не стартует | Nesting=yes, Privileged CT |

---

## 13. Автозапуск после ребута

1. В Proxmox у CT: **Options → Start at boot**.
2. Служба `monitor-bot` уже в `enable` (автозапуск).
3. DNAT-правила должны сохраняться (`netfilter-persistent` или firewall Proxmox).
4. Агент на Windows — служба NSSM / планировщик.
