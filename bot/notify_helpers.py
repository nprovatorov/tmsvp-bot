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
        
def _md_escape_name(s: str) -> str:
    """Escape characters that break Telegram Markdown links."""
    if not s:
        return "user"
    # Legacy Markdown: [],() and backticks are risky in link text; also tame *_ which format text
    return (s
            .replace("[", "⟮").replace("]", "⟯")
            .replace("(", "⟨").replace(")", "⟩")
            .replace("`", "ʼ")
            .replace("*", "·").replace("_", "ˍ"))

def author_display(msg: Message) -> str:
    """
    Return a Markdown-friendly author string:
      - Prefer @username
      - Else a Markdown link to the user ID with a safely-escaped name
    """
    try:
        u = getattr(msg, "from_user", None)
        if not u:
            return "unknown"
        if getattr(u, "username", None):
            return f"@{u.username}"
        uid = getattr(u, "id", None)
        if uid:
            name = " ".join(filter(None, [getattr(u, "first_name", None), getattr(u, "last_name", None)])).strip() or "user"
            return f"[{_md_escape_name(name)}](tg://user?id={uid})"
    except Exception:
        pass
    return "unknown"
