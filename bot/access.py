from typing import Coroutine, Callable
from pyrogram import Client
from pyrogram.types import Message
from config import PUBLIC_MODE, ADMINS

def check_access(func: Callable[[Client, Message], Coroutine]):
    async def wrapper(app: Client, message: Message):
        # Allow everyone if PUBLIC_MODE is enabled
        if PUBLIC_MODE:
            return await func(app, message)

        # Otherwise enforce admins (by @username or chat.id)
        uname = f"@{message.chat.username}" if message.chat and message.chat.username else None
        uid = str(message.chat.id) if message.chat and message.chat.id else None
        if (uname and uname in ADMINS) or (uid and uid in ADMINS):
            return await func(app, message)

        await message.reply("You aren't my admin :)")
        return
    return wrapper
