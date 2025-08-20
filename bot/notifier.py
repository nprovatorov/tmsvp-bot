import os
import logging

from . import app
from .messages import notify_new_upload, weekly_usage, retention_warning, retention_deleted

PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0") or "0")

async def safe_send(text: str):
    if not PRIVATE_CHANNEL_ID:
        logging.debug("PRIVATE_CHANNEL_ID not set; skipping notify: %s", text)
        return
    try:
        await app.send_message(PRIVATE_CHANNEL_ID, text)
    except Exception:
        logging.exception("Failed to notify private channel")

notify = safe_send
