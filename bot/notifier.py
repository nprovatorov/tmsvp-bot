import os
import logging

from . import app
from pyrogram.enums import ParseMode
from .messages import notify_new_upload, weekly_usage, retention_warning, retention_deleted

PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0") or "0")

async def safe_send(text: str, reply_markup=None):
    if not PRIVATE_CHANNEL_ID:
        logging.debug("PRIVATE_CHANNEL_ID not set; skipping notify: %s", text)
        return
    try:
        await app.send_message(
            PRIVATE_CHANNEL_ID,
            text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
            reply_markup=reply_markup,          # ← NEW
        )
    except Exception:
        logging.exception("Failed to notify private channel")

notify = safe_send