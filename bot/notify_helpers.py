# notify_helpers.py
from typing import Optional, Tuple
from pyrogram.types import Message

def media_resolution(msg: Message) -> Optional[str]:
    try:
        if getattr(msg, "photo", None):
            sizes = msg.photo or []
            if sizes:
                w = sizes[-1].width
                h = sizes[-1].height
                return f"{w}×{h}"
        if getattr(msg, "video", None):
            v = msg.video
            if v and v.width and v.height:
                return f"{v.width}×{v.height}"
        if getattr(msg, "animation", None):
            a = msg.animation
            if a and a.width and a.height:
                return f"{a.width}×{a.height}"
        if getattr(msg, "document", None):
            d = msg.document
            # Telegram doesn't expose generic doc resolution; skip
            # (you could parse filename, but it's unreliable)
            return None
    except Exception:
        return None
    return None

def message_link(msg: Message) -> Optional[str]:
    """
    t.me/<username>/<message_id> for public chats/supergroups with usernames.
    (Private/supergroup without username cannot be linked reliably.)
    """
    try:
        chat = getattr(msg, "chat", None)
        if chat and getattr(chat, "username", None) and getattr(msg, "id", None):
            return f"https://t.me/{chat.username}/{msg.id}"
    except Exception:
        pass
    return None

def channel_handle(msg: Message) -> str:
    try:
        chat = getattr(msg, "chat", None)
        return getattr(chat, "username", None) or "unknown"
    except Exception:
        return "unknown"

def author_display(msg: Message) -> str:
    try:
        u = getattr(msg, "from_user", None)
        # prefer mention if available, fall back to @username or id
        if u and getattr(u, "mention", None):
            return u.mention
        if u and getattr(u, "username", None):
            return f"@{u.username}"
        if u and getattr(u, "id", None):
            return str(u.id)
    except Exception:
        pass
    return "unknown"
