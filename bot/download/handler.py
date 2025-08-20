import os
from random import randint

from pyrogram.enums.parse_mode import ParseMode
from pyrogram.types import Message

from .. import folder
from .. import app, user
from .manager import downloads
from .types import Download
from ..util import is_from_public_channel
from .. import folder

from ..notifier import notify
from ..notify_helpers import media_resolution, message_link, channel_handle, author_display
from ..messages import admin_upload_started, file_added, file_exists

from ..util import humanReadableSize

async def addFile(_, message: Message):
    caption = (message.caption or "").strip()
    filename = f"File-{randint(1e9, 1e10 - 1)}"
    if caption[:1] == ">":
        filename = caption[2:].strip()
    else:
        try:
            media = getattr(message, message.media.value)
            if media.file_name:
                filename = media.file_name
        except AttributeError:
            pass
    file = os.path.join(folder.getPath(), filename)
    realFile = os.path.join(folder.get(), filename)
    if os.path.isfile(realFile):
        return await message.reply(file_exists(file), quote=True, parse_mode=ParseMode.MARKDOWN)
    progress = await message.reply(file_added(file), quote=True, parse_mode=ParseMode.MARKDOWN)

    downloads.append(
        Download(
            client=app,
            id=message.id,
            filename=file,
            from_message=message,
            progress_message=progress,
        )
    )
    res = media_resolution(message)
    lnk = message_link(message)
    chan = channel_handle(message)
    author = author_display(message)

    await notify(admin_upload_started(
        channel_handle=chan,
        filename=filename,
        resolution=res,
        link=lnk,
        author=author,
    ))
    # # Notify private channel about the new upload
    # channel = getattr(getattr(message, "chat", None), "username", "unknown")
    # author = getattr(getattr(message, "from_user", None), "mention", "unknown")
    # await notify(MSG.notify_new_upload(channel, filename, "unknown", author))


async def addFileFromUser(fileMessage: Message, linkMessage: Message):
    filename = f"File-{randint(int(1e9), int(1e10 - 1))}"  # Default filename
    caption = (fileMessage.caption or "").strip()
    ltextParts = linkMessage.text.split()
    if len(ltextParts) >= 3:  # Name set after message link has biggest priority
        filename = ltextParts[2]
    elif caption[:1] == ">":  # Caption filename has medium priory
        filename = caption[1:].strip()
    else:
        try:
            media = getattr(fileMessage, fileMessage.media.value)
            if media.file_name:  # Lowest filename priority
                filename = media.file_name
        except AttributeError:
            pass
    file = os.path.join(folder.getPath(), filename)
    realFile = os.path.join(folder.get(), filename)
    if os.path.isfile(realFile):
        return await linkMessage.reply(text=f"File `{file}` already exists!", quote=True)
    progress = await linkMessage.reply(
        f"File `{file}` added to list.", quote=True, parse_mode=ParseMode.MARKDOWN
    )
    downloads.append(
        Download(
            client=user,
            id=fileMessage.id,
            filename=file,
            from_message=fileMessage,
            progress_message=progress,
        )
    )
