from typing import Coroutine
from datetime import timedelta

from pyrogram import Client
from pyrogram.types import Message
import os

from . import ADMINS

KIB = 1024
MIB = 1024 * KIB
GIB = 1024 * MIB



def humanReadableSize(size: float) -> str:
    symbol, divider = "B", 1
    if size >= GIB:
        symbol, divider = "GiB", GIB
    elif size >= MIB:
        symbol, divider = "MiB", MIB
    elif size >= KIB:
        symbol, divider = "KiB", KIB
    readableSize = size / divider
    return f"{readableSize:.1f} {symbol}"

def humanReadableTime(s: int) -> str:
    time = timedelta(seconds=s)
    hours, remaining = divmod(time.seconds, 3600)
    minutes, seconds = divmod(remaining, 60)
    
    parts = []
    if time.days > 0:
        parts.append(f"{time.days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:  # Show seconds if theres no other parts
        parts.append(f"{seconds}s")

    return " ".join(parts)

def checkAdmins(func: Coroutine) -> Coroutine:
    async def wrapper(app: Client, message: Message):
        # if (f"@{message.chat.username}" not in ADMINS) and (
        #     str(message.chat.id) not in ADMINS
        # ):
        #     await message.reply("You aren't my admin :)")
        #     return
        return await func(app, message)

    return wrapper

# def parse_list_env(name: str) -> set[str]:
#     raw = os.getenv(name, "") or ""
#     # supports comma or space separated values, trims @ prefixes too
#     vals = [v.strip() for v in raw.replace(",", " ").split() if v.strip()]
#     return {v.lstrip("@") for v in vals}


def is_from_public_channel(message) -> bool:
    # works for channels/supergroups that have usernames
    try:
        uname = getattr(getattr(message, "chat", None), "username", None)
        if not uname:
            return False
        return uname in PUBLIC_CHANNELS
    except Exception:
        return False

def safe_relpath(name: str) -> str:
    name = (name or "").strip().lstrip("/\\").replace("\x00", "")
    # If you want to allow subfolders, swap to normpath + a whitelist.
    # For now keep it as a plain file name:
    return os.path.basename(os.path.normpath(name))

