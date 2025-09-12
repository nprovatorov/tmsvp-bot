# Telegram Downloader Bot on Synology NAS (Docker Compose)

This project deploys the **Telegram downloader bot** together with **ClamAV** on a Synology NAS using Docker Compose. It allows downloading files from Telegram directly to your NAS, using [Pyrogram Framework](https://github.com/pyrogram/pyrogram) for MTProto support (up to 4GB per file).

The setup keeps **code and configs off shared SMB volumes**, while storing downloads in a shared folder for easy access.

---

## 🚀 Prerequisites

* Synology DSM with **Docker** and **docker-compose** installed (via Package Center).
* SSH access enabled:
  DSM → **Control Panel → Terminal & SNMP → Enable SSH service**.
* An existing shared folder for downloads, e.g. `/volume2/Quaratine/incoming`.
* A **Telegram Bot Token** created via [BotFather](https://t.me/BotFather).
* A **Telegram API ID & Hash** generated at [My Telegram](https://my.telegram.org/auth).

> Adjust paths if your download folder is different. The guide uses the path above verbatim.

---

## 🔑 Setup Instructions

### 1. SSH into the NAS

```bash
ssh <username>@<NAS_IP>
# If you’re using a custom SSH port:
ssh -p <PORT> <username>@<NAS_IP>
```

### 2. Become root

```bash
sudo -i
```

### 3. Create working directory

```bash
mkdir -p /var/local/src/tm-bot
```

### 4. Clone the repository (via one-shot git container)

```bash
REPO_URL="https://github.com/tvorchamaysternya/tmsvp-bot.git"
docker run --rm -v /var/local/src:/git alpine/git \
  clone --depth 1 "$REPO_URL" /git/tm-bot
```

### 5. Create the `.env` file

Create `/var/local/src/tm-bot/.env` with the following content (replace placeholders with your real values):

```ini
PUBLIC_MODE=true

BOT_TOKEN=<your bot token>
TELEGRAM_API_ID=<your telegram api id>
TELEGRAM_API_HASH=<your telegram api hash>
DOWNLOAD_FOLDER=/data
CONFIG_FOLDER=/config
PUBLIC_CHANNELS=<name of public bot>
PRIVATE_CHANNEL_ID=<id of private channel>
RETENTION_DAYS=30
RETENTION_NOTICE_DAYS=2
DISK_USAGE_DAY=Monday
DISK_USAGE_HOUR=10
TZ=Europe/Kyiv
DEBUG=1
```

You can create the file quickly:

```bash
cat > /var/local/src/tm-bot/.env <<'EOF'
PUBLIC_MODE=true

BOT_TOKEN=<your bot token>
TELEGRAM_API_ID=<your telegram api id>
TELEGRAM_API_HASH=<your telegram api hash>
DOWNLOAD_FOLDER=/data
CONFIG_FOLDER=/config
PUBLIC_CHANNELS=<name of public bot>
PRIVATE_CHANNEL_ID=<id of private channel>
RETENTION_DAYS=30
RETENTION_NOTICE_DAYS=2
DISK_USAGE_DAY=Monday
DISK_USAGE_HOUR=10
TZ=Europe/Kyiv
DEBUG=1
EOF
```

---

## 📦 Environment Variables

* **BOT\_TOKEN** → from [BotFather](https://t.me/BotFather).
* **TELEGRAM\_API\_ID** / **TELEGRAM\_API\_HASH** → from [My Telegram](https://my.telegram.org/auth).
* **PUBLIC\_MODE** → `true` to allow anyone, or `false` for restricted.
* **DOWNLOAD\_FOLDER** → inside container path for downloads (mapped to NAS path).
* **CONFIG\_FOLDER** → inside container path for configs.
* **PUBLIC\_CHANNELS** / **PRIVATE\_CHANNEL\_ID** → specify bot access.
* **RETENTION\_DAYS**, **RETENTION\_NOTICE\_DAYS** → cleanup configuration.
* **DISK\_USAGE\_DAY**, **DISK\_USAGE\_HOUR** → schedule for usage reports.
* **TZ** → timezone.
* **DEBUG** → `1` for debug logging.

---

## 📁 Prepare Folders & Permissions

```bash
mkdir -p /var/local/src/tm-bot/config
mkdir -p /volume2/Quaratine/incoming

chmod 775 /var/local/src/tm-bot/config /volume2/Quaratine/incoming
# Example (only if needed):
# chown -R 1000:1000 /var/local/src/tm-bot/config /volume2/Quaratine/incoming
```

---

## 🐳 Docker Install

### Build and start containers

```bash
cd /var/local/src/tm-bot
docker-compose up -d --build
```

This will:

* Build the `tg-downloader` image from the local Dockerfile.
* Start `clamav` and `tg-bot` containers with `restart: unless-stopped`.

---

## ✅ Verification

* Tail logs from all services:

  ```bash
  cd /var/local/src/tm-bot
  docker-compose logs --tail=200 -f
  ```

* Check running containers:

  ```bash
  docker ps
  ```

---

## 📂 Paths Overview

* **Downloads:** `/volume2/Quaratine/incoming`
* **Config files:** `/var/local/src/tm-bot/config`
* **Environment file:** `/var/local/src/tm-bot/.env`

Containers are configured with `restart: unless-stopped` → they **auto-start on reboot** and **auto-restart on failures**.

---

## 📖 References

* [Pyrogram Framework](https://github.com/pyrogram/pyrogram) — Telegram MTProto client used by this bot.
* [My Telegram](https://my.telegram.org/auth) — Create your API ID and Hash.
* [BotFather](https://t.me/BotFather) — Create and manage your Telegram bots.
