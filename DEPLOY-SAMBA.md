# Samba: загрузить проект на CT

Нужна только чтобы с Windows удобно скопировать папку `monitor-telegram-bot` на сервер (вместо `scp`).  
После загрузки и `docker compose up` шару можно оставить или выключить.

Шару держи **только в LAN**. Порт `445` на внешку `94.159.18.22` не открывай.

---

## 1. В консоли CT

```bash
apt update
apt install -y samba
mkdir -p /opt/monitor-telegram-bot
chmod 777 /opt/monitor-telegram-bot
```

`chmod 777` — временно, чтобы с Windows залить файлы без танцев с правами. После деплоя можно ужесточить.

Добавь пользователя Samba (пароль задашь сам):

```bash
adduser --disabled-password --gecos "" shareuser
smbpasswd -a shareuser
smbpasswd -e shareuser
```

---

## 2. Конфиг

```bash
cp /etc/samba/smb.conf /etc/samba/smb.conf.bak
nano /etc/samba/smb.conf
```

В **конец** файла:

```ini
[deploy]
   path = /opt/monitor-telegram-bot
   browseable = yes
   read only = no
   guest ok = no
   valid users = shareuser
   create mask = 0666
   directory mask = 0777
   force user = root
```

`force user = root` — чтобы Docker потом без проблем читал залитые файлы.

```bash
testparm
systemctl enable --now smbd nmbd
```

Узнай IP CT:

```bash
hostname -I
```

---

## 3. С Windows залить проект

1. Проводник → адресная строка:
   ```text
   \\IP_CT\deploy
   ```
2. Логин: `shareuser`, пароль из `smbpasswd`.
3. Скопируй **содержимое** папки  
   `C:\Users\Гришаня\monitor-telegram-bot\`  
   в эту шару  
   (должны появиться `Dockerfile`, `docker-compose.yml`, `server`, `agent`, `.env.example` …).

`.venv` и `data\*.db` с Windows лучше **не копировать** — на сервере не нужны.

Обновление только агента на mini PC: копируй папку `agent/` (с DDC/CI) на точки; сервер перезапускать не обязательно, если API не менялся.

---

## 4. Дальше на CT — запуск бота

```bash
cd /opt/monitor-telegram-bot
cp .env.example .env
nano .env
# TELEGRAM_TOKEN, ADMIN_API_KEY

mkdir -p data
docker compose up -d --build
curl http://127.0.0.1:8787/health
```

Подробности: [DEPLOY-PROXMOX.md](DEPLOY-PROXMOX.md).

---

## 5. После загрузки (по желанию)

Остановить Samba:

```bash
systemctl disable --now smbd nmbd
```

Или оставить — удобно обновлять файлы проекта снова через `\\IP_CT\deploy`.
