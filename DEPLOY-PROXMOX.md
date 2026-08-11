# Установка на Proxmox (Docker-контейнер)

Сервис слушает **`0.0.0.0:8787`**, снаружи доступен как **`http://94.159.18.22:8787`**.  
Telegram Bot API: **`https://t.api.lookinsoft.ru`**.

Рекомендуемый вариант: отдельный **Debian 12 LXC** (или маленькая VM) на Proxmox → внутри Docker Compose.  
На сам гипервизор Docker лучше не ставить.

---

## 1. Создать Debian CT в Proxmox

В веб-UI Proxmox:

1. **Datacenter → local (storage) → CT Templates** — скачай `debian-12-standard`.
2. **Create CT**:
   - **Hostname:** `monitor-bot`
   - **Password:** задай root-пароль
   - **Template:** `debian-12-standard`
   - **Disk:** 8–16 GB
   - **CPU:** 1–2 cores
   - **Memory:** 512–1024 MB
   - **Network:** Bridge `vmbr0` (тот, через который ходит внешка), DHCP или статический LAN-IP  
     Пример: `192.168.1.50/24`, gateway = роутер/шлюз Proxmox
   - **DNS:** `1.1.1.1` или DNS провайдера

3. **Options → Features** — включи:
   - `Nesting` = **yes** (нужно для Docker)
   - при необходимости `keyctl` = yes

4. Если Docker в unprivileged CT капризничает — в **Options** поставь CT **Privileged** (проще для Docker).

5. Запусти CT: **Start**.

Консоль:

```bash
pct enter <CTID>
# или SSH на IP контейнера
```

---

## 2. Базовая подготовка Debian внутри CT

```bash
apt update
apt install -y ca-certificates curl git nano ufw
```

---

## 3. Установить Docker

```bash
apt install -y docker.io docker-compose ca-certificates curl

systemctl enable --now docker
docker --version
docker-compose --version
```

---

## 4. Загрузить проект

С машины, где лежит код (пример с Windows → CT):

```powershell
scp -r C:\Users\Гришаня\monitor-telegram-bot\* root@192.168.1.50:/opt/monitor-telegram-bot/
```

Или внутри CT, если есть git-репозиторий:

```bash
mkdir -p /opt/monitor-telegram-bot
cd /opt/monitor-telegram-bot
# git clone <URL> .
```

Проверь, что есть файлы:

```bash
ls /opt/monitor-telegram-bot
# Dockerfile  docker-compose.yml  .env.example  server/  agent/ ...
```

---

## 5. Настроить `.env`

```bash
cd /opt/monitor-telegram-bot
cp .env.example .env
nano .env
```

Минимум:

```env
TELEGRAM_TOKEN=123456:ABCDEF_от_BotFather
TELEGRAM_API_BASE=https://t.api.lookinsoft.ru
ALLOWED_USER_IDS=ТВОЙ_TELEGRAM_ID
ADMIN_API_KEY=вставь_openssl_rand_hex_32
DATABASE_PATH=/app/data/monitors.db
OFFLINE_THRESHOLD_SEC=180
HOST=0.0.0.0
PORT=8787
```

Ключ:

```bash
openssl rand -hex 32
```

---

## 6. Запустить контейнер

```bash
cd /opt/monitor-telegram-bot
mkdir -p data
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=100
```

Проверка **внутри CT**:

```bash
curl http://127.0.0.1:8787/health
# {"status":"ok"}
```

Бот должен подняться без traceback в логах.

---

## 7. Проброс порта 8787 на внешку `94.159.18.22`

Агенты стучатся на **`http://94.159.18.22:8787`**.  
Нужно, чтобы этот порт с интернета доходил до CT.

### Вариант A — у Proxmox-хоста IP `94.159.18.22`, CT во внутренней сети

На **хосте Proxmox** (не в CT) пробрось порт. Подставь IP своего CT вместо `192.168.1.50`.

```bash
# на хосте Proxmox
iptables -t nat -A PREROUTING -p tcp -d 94.159.18.22 --dport 8787 -j DNAT --to-destination 192.168.1.50:8787
iptables -A FORWARD -p tcp -d 192.168.1.50 --dport 8787 -j ACCEPT
```

Чтобы правила переживали перезагрузку, сохрани их привычным для тебя способом, например:

```bash
apt install -y iptables-persistent
netfilter-persistent save
```

Или через **Datacenter → Firewall / хост Firewall** (DNAT), если пользуешься файрволом Proxmox.

Также на хосте/роутере разреши входящий **TCP 8787**.

### Вариант B — CT напрямую в той же сети, что и внешка

Если CT получил/пробросили адрес так, что `94.159.18.22` слушается на CT (редко, но бывает):

- в CT: `ufw allow 8787/tcp && ufw enable`
- отдельный DNAT на хосте не нужен

### Вариант C — роутер перед Proxmox

На роутере: **WAN TCP 8787 → IP CT (или хоста) :8787**.

---

## 8. Firewall внутри CT (опционально)

```bash
ufw allow OpenSSH
ufw allow 8787/tcp
ufw enable
ufw status
```

---

## 9. Проверка снаружи

С любой машины в интернете:

```bash
curl http://94.159.18.22:8787/health
```

В Telegram боту: `/start` → `/add_point Тест`.

На Windows-точке в `agent/config.json` уже должно быть:

```json
{
  "server_url": "http://94.159.18.22:8787",
  "agent_token": "...",
  "poll_interval_sec": 15
}
```

---

## 10. Автозапуск

Docker-сервис уже в enable. Контейнер с `restart: unless-stopped` поднимется после ребута CT.

После ребута **хоста Proxmox** убедись, что:

1. CT `monitor-bot` в автозапуске (**Options → Start at boot**)
2. DNAT/firewall-правила на месте

---

## Обслуживание

| Действие | Команда (в CT) |
|----------|----------------|
| Логи | `cd /opt/monitor-telegram-bot && docker compose logs -f` |
| Перезапуск | `docker compose restart` |
| Обновление кода | залить файлы → `docker compose up -d --build` |
| Стоп | `docker compose down` |
| Бэкап БД | `cp /opt/monitor-telegram-bot/data/monitors.db /root/monitors-$(date +%F).db` |

Бэкап CT целиком: в Proxmox **Backup** для CTID.

---

## Частые проблемы

| Симптом | Что проверить |
|---------|----------------|
| `curl` снаружи не отвечает | DNAT/порт на роутере, `ufw`, CT запущен, `docker compose ps` |
| Бот молчит в Telegram | `TELEGRAM_TOKEN`, исходящий доступ CT к `t.api.lookinsoft.ru`, логи |
| Агент пишет connection error | с mini PC: `curl http://94.159.18.22:8787/health` |
| Docker не стартует в LXC | Nesting=yes, лучше Privileged CT, или Debian VM |

---

## Краткий чеклист

1. CT Debian 12 + Nesting  
2. Docker + проект в `/opt/monitor-telegram-bot`  
3. `.env` с токеном и `TELEGRAM_API_BASE=https://t.api.lookinsoft.ru`  
4. `docker compose up -d --build`  
5. Проброс **8787 → CT** на хосте/роутере для **94.159.18.22**  
6. `/health` снаружи ок → раздача агентов  
7. Веб-панель: `http://94.159.18.22:8787/` (пароль из `WEB_PASSWORD` или `ADMIN_API_KEY`)  

Samba на этом же CT (опционально): см. **[DEPLOY-SAMBA.md](DEPLOY-SAMBA.md)**.
