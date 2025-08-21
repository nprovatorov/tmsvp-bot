import logging
from textwrap import dedent

from pyrogram import filters
from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import Message

from . import DL_FOLDER, download, folder, sysinfo, user
from .util import checkAdmins
from .desc_cache import put as desc_put
from .metrics import send_weekly_report

from pyrogram.enums import ParseMode
from .messages import (
    start_text, help_text, usage_text,
    use_need_path, use_path_warning, use_ok, leave_ok, get_folder,
    add_need_user_client, add_need_link, add_invalid_link, add_message_not_found, add_no_media,
    weekly_report_done, weekly_report_failed, unsupported_media
)

bot_help = """
You can send files to me and I'll save it to your storage(where bot is hosted), when sending a file you can set caption as "> filename.ext" to rename it

The name of the files to be downloaded has a priority sequence:
  - Name set on message to add file;
  - Caption starting with ">";
  - Original filename provided by telegram;
  - Random name without extension starting with 'File-'.

This bot is capable of stopping downloads, so don't worry if you don't want a file that is being downloaded :)

My commands are:\n\n"""


def register(app: Client):
    logging.info("Registering commands...")

    # Commands
    addCommand(app, start, "start")
    addCommand(app, botHelp, "help")
    addCommand(app, usage, "usage")
    addCommand(app, useFolder, "use")
    addCommand(app, leaveFolder, "leave")
    addCommand(app, getFolder, "get")
    addCommand(app, addByLink, "add")
    addCommand(app, weekly_report_cmd, "weekly")

    # ---- Handlers ----
    scope = filters.incoming & (filters.private | filters.group)

    # ACCEPT ONLY: documents & photos
    SUPPORTED_MEDIA = (filters.document | filters.photo)
    app.add_handler(
        MessageHandler(
            checkAdmins(download.handler.addFile),   # PUBLIC_MODE still respected inside checkAdmins
            SUPPORTED_MEDIA & scope
        ),
        group=0,
    )
    logging.info("commands: media handler (documents/photos) registered")

    # Politely REJECT these media types (no download)
    REJECTED_MEDIA = (
        filters.sticker
        | filters.video
        | filters.voice
        | filters.video_note
        | filters.location
        | filters.venue
        # (Optional) also reject GIF/animations:
        # | filters.animation
        # (Optional) also reject audio/music:
        # | filters.audio
    )

    async def _reject_unsupported(_, message: Message):
        await message.reply(unsupported_media(), parse_mode=ParseMode.MARKDOWN)

    app.add_handler(
        MessageHandler(
            checkAdmins(_reject_unsupported),
            REJECTED_MEDIA & scope
        ),
        group=0,
    )
    logging.info("commands: unsupported media handler registered")

    # Description cache: plain text that isn't a command (stored silently)
    text_filters = filters.text & ~filters.command(["start", "help", "usage", "add", "use", "leave", "get", "weekly"])
    app.add_handler(
        MessageHandler(
            remember_desc,
            text_filters & scope
        ),
        group=1,
    )
    logging.info("commands: description cache handler registered")

    # Callback (e.g., stop button)
    app.add_handler(CallbackQueryHandler(download.manager.stopDownload))
    logging.info("commands: callback handler registered")



def addCommand(app, func, cmd):
    global bot_help
    bot_help += f"/{cmd} - {dedent(func.__doc__ or 'No description').strip()}\n"
    app.add_handler(MessageHandler(checkAdmins(func), filters.command(cmd)))

# commands.py  — only the relevant changes shown

from pyrogram.enums import ParseMode
# ...
from .messages import (
    start_text, help_text, usage_text,
    use_need_path, use_path_warning, use_ok, leave_ok, get_folder,
    add_need_user_client, add_need_link, add_invalid_link, add_message_not_found, add_no_media,
    weekly_report_done, weekly_report_failed,
)

# ...

async def start(_, message: Message):
    """Shows bot start message"""
    await message.reply(start_text(), parse_mode=ParseMode.MARKDOWN)

async def botHelp(_, message: Message):
    """Send this message"""
    await message.reply(help_text(), parse_mode=ParseMode.MARKDOWN)

async def addByLink(_, message: Message):
    """
    Add a link to download a file from a private channel that doesn't allow forwarding
    First argument is the message link where file is, second is optional and can be used to rename file
    """
    if not user:
        await message.reply(add_need_user_client())
        return

    parts = (message.text or "").split()
    if len(parts) == 1 or "://" not in parts[1]:
        await message.reply(add_need_link())
        return

    linkParts = parts[1].split("/c/")
    if len(linkParts) < 2:
        await message.reply(add_invalid_link())
        return

    ids = linkParts[1].split("/")
    chatID = int(f"-100{ids[0]}")
    messageID = int(ids[-1])
    try:
        messages = await user.get_messages(chatID, [messageID])
    except Exception as error:
        logging.error("Getting messages from user", {"chatID": chatID, "messageID": messageID}, error)
        await message.reply(add_message_not_found())
        return

    if not messages or not messages[0].media:
        await message.reply(add_no_media())
        return

    await download.handler.addFileFromUser(messages[0], message)

async def usage(_, message: Message):
    """
    Lets you know how many storage your device has and how many of it is available
    You can use it to know if your storage has enough available space
    """
    u = sysinfo.diskUsage(DL_FOLDER)
    await message.reply(usage_text(u.capacity, u.used, u.free), parse_mode=ParseMode.MARKDOWN)

async def useFolder(_, message: Message):
    """
    Set a subfolder for downloading files into it
    This must be used before adding a file to download, so it will be save where you want it
    """
    args = (message.text or "").split()
    userSetPath = " ".join(args[1:]).strip()
    if not userSetPath:
        await message.reply(use_need_path())
        return

    path = userSetPath.replace("../", "").replace("/..", "")
    if userSetPath != path:
        await message.reply(use_path_warning(path, " ".join(args[1:])), parse_mode=ParseMode.MARKDOWN)

    folder.set(path)
    await message.reply(use_ok())

async def leaveFolder(_, message: Message):
    """Go back to default download folder"""
    folder.reset()
    await message.reply(leave_ok())

async def getFolder(_, message: Message):
    """Get actual download folder"""
    path = folder.getPath()
    await message.reply(get_folder(path), parse_mode=ParseMode.MARKDOWN)

async def remember_desc(_, message: Message):
    """Cache a free-text description to attach to the next upload from this chat."""
    desc_put(message.chat.id, message.text)
    logging.info("remember_desc: cached text for chat %s: %r", message.chat.id, (message.text or "")[:120])

async def weekly_report_cmd(_, message):
    """Generate and send the weekly analytics report to the admin channel"""
    try:
        await send_weekly_report()
        await message.reply(weekly_report_done())
    except Exception:
        logging.exception("Failed to send weekly report")
        await message.reply(weekly_report_failed())
