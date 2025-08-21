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

    addCommand(app, start, "start")
    addCommand(app, botHelp, "help")
    addCommand(app, usage, "usage")
    addCommand(app, useFolder, "use")
    addCommand(app, leaveFolder, "leave")
    addCommand(app, getFolder, "get")
    addCommand(app, addByLink, "add")

    # ---- Handlers ----
    scope = filters.incoming & (filters.private | filters.group)

    # 1) Media uploads (documents, photos, videos, animations, audio, voice)
    media_filters = filters.media
    app.add_handler(
        MessageHandler(
            checkAdmins(download.handler.addFile),   # PUBLIC_MODE allows everyone; otherwise admins only
            media_filters & scope
        ),
        group=0,
    )
    logging.info("commands: media handler registered")

    # 2) Description cache: plain text that isn't a command (stored silently)
    text_filters = filters.text & ~filters.command(["start", "help", "usage", "add", "use", "leave", "get"])
    app.add_handler(
        MessageHandler(
            remember_desc,
            text_filters & scope
        ),
        group=1,
    )
    logging.info("commands: description cache handler registered")

    # 3) Callback (e.g., stop button)
    app.add_handler(CallbackQueryHandler(download.manager.stopDownload))
    logging.info("commands: callback handler registered")


def addCommand(app, func, cmd):
    global bot_help
    bot_help += f"/{cmd} - {dedent(func.__doc__ or 'No description').strip()}\n"
    app.add_handler(MessageHandler(checkAdmins(func), filters.command(cmd)))


async def start(_, message: Message):
    """Shows bot start message"""
    await message.reply(
        dedent("""
        Hello!
        Send me a file and I will download it to my server.
        If you need help send /help
    """)
    )


async def botHelp(_, message: Message):
    """Send this message"""
    global bot_help
    await message.reply(bot_help)


async def addByLink(_, message: Message):
    """
    Add a link to download a file from a private channel that doesn't allow forwarding
    First argument is the message link where file is, second is optional and can be used to rename file
    """
    if not user:
        await message.reply("Your bot system isn't configured to access your messages!")
        return
    messageParts = message.text.split()
    if len(messageParts) == 1 or "://" not in messageParts[1]:
        await message.reply("You don't sent a link to message!")
        return
    linkParts = messageParts[1].split("/c/")
    if len(linkParts) < 2:
        await message.reply("Invalid link!")
        return
    # Structure can be: [chatID, messageID] or [chatID, topicID, messageID]
    ids = linkParts[1].split("/")
    chatID = int(f"-100{ids[0]}")
    messageID = int(ids[-1])
    try:
        messages = await user.get_messages(chatID, [messageID])
    except Exception as error:
        logging.error("Getting messages from user", {"chatID": chatID, "messageID": messageID}, error)
        await message.reply("Message not found on normal user!")
        return
    if not messages[0].media:
        await message.reply("The message linked has no media files!")
        return
    await download.handler.addFileFromUser(messages[0], message)


async def usage(_, message: Message):
    """
    Lets you know how many storage your device has and how many of it is available
    You can use it to know if your storage has enough available space
    """
    usage = sysinfo.diskUsage(DL_FOLDER)
    await message.reply(
        dedent(f"""
            The storage path configured has __{usage.capacity}__ of storage
            Of those, __{usage.used}__ is in use, and __{usage.free}__ is free.
        """),
        parse_mode=ParseMode.MARKDOWN,
    )


async def useFolder(_, message: Message):
    """
    Set a subfolder for downloading files into it
    This must be used before adding a file to download, so it will be save where you want it
    """
    args = message.text.split()
    userSetPath = " ".join(args[1:]).strip()
    if not userSetPath:
        await message.reply("You haven't told me where I need to put your files!")
        return
    path = userSetPath.replace("../", "").replace("/..", "")
    if userSetPath != path:
        await message.reply(f"Warning: Path is `{path}` not `{' '.join(args[1:])}`")
    folder.set(path)
    await message.reply("Ok, send me files now and I will put it on this folder.")


async def leaveFolder(_, message: Message):
    """Go back to default download folder"""
    folder.reset()
    await message.reply("I'm in the root folder again :)")


async def getFolder(_, message: Message):
    """Get actual download folder"""
    path = folder.getPath()
    await message.reply(f"I'm on the `{path}` folder")


async def remember_desc(_, message: Message):
    """Cache a free-text description to attach to the next upload from this chat."""
    desc_put(message.chat.id, message.text)
    logging.info("remember_desc: cached text for chat %s: %r", message.chat.id, (message.text or "")[:120])
