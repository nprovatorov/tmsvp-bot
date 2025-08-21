import os
import logging
from random import randint
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from .. import app, folder
from random import randint
from ..notifier import notify
from ..notify_helpers import media_resolution, message_link, channel_handle, author_display
from ..messages import admin_upload_started, file_added, file_exists
from ..desc_cache import take as desc_take  # ok if you’re not using it; will just return None
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton  # ← import buttons

from .types import Download
from .. import app, folder
from .manager import downloads


def _pick_filename_from_media(message: Message, default_name: str) -> str:
    try:
        if getattr(message, "media", None):
            media_obj = getattr(message, message.media.value, None)
            if media_obj and getattr(media_obj, "file_name", None):
                return media_obj.file_name
    except Exception:
        pass
    return default_name

def _contact_button_for(msg: Message):
    """Return InlineKeyboardMarkup with one 'Send Message' button, or None."""
    u = getattr(msg, "from_user", None)
    if not u:
        return None
    uname = getattr(u, "username", None)
    if uname:
        url = f"https://t.me/{uname}"            # universal (mobile/desktop/web)
    else:
        uid = getattr(u, "id", None)
        if not uid:
            return None
        url = f"tg://user?id={uid}"              # native apps fallback
    return InlineKeyboardMarkup([[InlineKeyboardButton("Send Message", url=url)]])


async def addFile(_, message: Message):
    # Description: prefer caption, else cached text
    desc = (getattr(message, "caption", None) or "").strip() or desc_take(message.chat.id)
    logging.warning("addFile: caption/desc=%r", desc)

    # Filename selection
    filename = f"File-{randint(int(1e9), int(1e10) - 1)}"
    caption = (getattr(message, "caption", None) or "").strip()
    if caption.startswith(">"):
        filename = caption[1:].strip()
    else:
        filename = _pick_filename_from_media(message, filename)
    filename = filename.lstrip("/\\")  # ← avoid absolute paths

    # Path checks
    file_display = os.path.join(folder.getPath(), filename)
    real_file = os.path.join(folder.get(), filename)
    if os.path.isfile(real_file):
        return await message.reply(file_exists(file_display), quote=True, parse_mode=ParseMode.MARKDOWN)

    # Progress message
    progress = await message.reply(file_added(file_display), quote=True, parse_mode=ParseMode.MARKDOWN)
    logging.info("addFile: caption=%r desc=%r filename=%r", caption, desc, filename)

    # Enqueue
    downloads.append(
        Download(
            client=app,
            id=message.id,
            filename=filename,
            from_message=message,
            progress_message=progress,
            description=desc,
        )
    )

    # Admin “new upload request” with buttons
    res = media_resolution(message)
    chan = channel_handle(message)
    author = author_display(message)
    buttons = _contact_button_for(message)
    
    await notify(
        admin_upload_started(
            channel_handle=chan,
            filename=filename,
            resolution=res,
            link=None,          # no inline link; we use a button
            author=author,
        ),
        reply_markup=buttons
    )

async def addFileFromUser(fileMessage: Message, linkMessage: Message):
    # Description from file caption (or cached)
    desc = (getattr(fileMessage, "caption", None) or "").strip() or desc_take(fileMessage.chat.id)

    # Filename selection
    filename = f"File-{randint(int(1e9), int(1e10) - 1)}"
    caption = (getattr(fileMessage, "caption", None) or "").strip()
    ltextParts = (getattr(linkMessage, "text", "") or "").split()

    if len(ltextParts) >= 3:
        filename = ltextParts[2]
    elif caption.startswith(">"):
        filename = caption[1:].strip()
    else:
        filename = _pick_filename_from_media(fileMessage, filename)
    filename = filename.lstrip("/\\")  # ← avoid absolute paths

    file_display = os.path.join(folder.getPath(), filename)
    real_file = os.path.join(folder.get(), filename)
    if os.path.isfile(real_file):
        return await linkMessage.reply(text=f"File `{file_display}` already exists!", quote=True)

    progress = await linkMessage.reply(
        f"File `{file_display}` added to list.", quote=True, parse_mode=ParseMode.MARKDOWN
    )
    logging.info("addFileFromUser: caption=%r desc=%r filename=%r", caption, desc, filename)

    downloads.append(
        Download(
            client=app,
            id=fileMessage.id,
            filename=filename,
            from_message=fileMessage,
            progress_message=progress,
            description=desc,
        )
    )

    # Admin “new upload request” with buttons
    res = media_resolution(fileMessage)
    chan = channel_handle(fileMessage)
    author = author_display(fileMessage)

    buttons = _contact_button_for(message)
    await notify(
        admin_upload_started(
            channel_handle=chan,
            filename=filename,
            resolution=res,
            link=None,
            author=author,
        ),
        reply_markup=buttons
    )