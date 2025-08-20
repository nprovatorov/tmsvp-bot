import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pyrogram.client import Client

# ---- Load environment -------------------------------------------------------
# Prefer /config/.env if you mounted it; fallback to default load_dotenv()
ENV_FILE = os.getenv("ENV_FILE", "/config/.env")
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)
else:
    # This still lets you run locally with a .env in CWD if you want
    load_dotenv()

# ---- Logging ---------------------------------------------------------------
DEBUG = (os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"})
logging.basicConfig(level=logging.INFO if DEBUG else logging.WARN)

# ---- Helpers ---------------------------------------------------------------
def _parse_list_env(name: str):
    raw = os.getenv(name, "") or ""
    return [v for v in raw.replace(",", " ").split() if v.strip()]

def _mkdirp(path: str):
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception:
        logging.exception("Failed to create folder: %s", path)
        sys.exit(1)

def _require_env_int(name: str) -> int:
    v = os.getenv(name)
    if not v:
        logging.error("Missing required env: %s", name)
        sys.exit(2)
    try:
        return int(v)
    except Exception:
        logging.error("Env %s must be an integer (got: %r)", name, v)
        sys.exit(2)

def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        logging.error("Missing required env: %s", name)
        sys.exit(2)
    return v

# ---- Configuration ---------------------------------------------------------
MAX_SIMULTANEOUS_TRANSMISSIONS = int(os.getenv("MAX_SIMULTANEOUS_TRANSMISSIONS", "3") or "3")

ADMINS = _parse_list_env("ADMINS")                     # optional
BASE_FOLDER = os.getenv("DOWNLOAD_FOLDER", "/data")
CONFIG_FOLDER = os.getenv("CONFIG_FOLDER", "/config")
DL_FOLDER = BASE_FOLDER

# Optional; some modules may use it without importing back into bot
PUBLIC_CHANNELS = {x.lstrip("@") for x in _parse_list_env("PUBLIC_CHANNELS")}

# ---- Telegram API creds (required) -----------------------------------------
BOT_TOKEN   = _require_env("BOT_TOKEN")
TAPI_ID     = _require_env_int("TELEGRAM_API_ID")
TAPI_HASH   = _require_env("TELEGRAM_API_HASH")

# Optional user account for “fetch by link”
PHONE_NUMBER = os.getenv("PHONE_NUMBER")

# ---- Folders ---------------------------------------------------------------
for f in (BASE_FOLDER, CONFIG_FOLDER):
    _mkdirp(f)

# ---- Pyrogram Clients ------------------------------------------------------
app = Client(
    name="TDownloader-bot",
    api_id=TAPI_ID,
    api_hash=TAPI_HASH,
    bot_token=BOT_TOKEN,
    workdir=CONFIG_FOLDER,
    max_concurrent_transmissions=MAX_SIMULTANEOUS_TRANSMISSIONS,
)

user = None
if PHONE_NUMBER:
    user = Client(
        name="TDownloader-user",
        api_id=TAPI_ID,
        api_hash=TAPI_HASH,
        phone_number=PHONE_NUMBER,
        workdir=CONFIG_FOLDER,
        no_updates=True,
        max_concurrent_transmissions=MAX_SIMULTANEOUS_TRANSMISSIONS,
    )
