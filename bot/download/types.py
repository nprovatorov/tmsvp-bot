from dataclasses import dataclass
from typing import Optional  # ← add this

from pyrogram.client import Client
from pyrogram.types import Message


@dataclass
class Download:
    client: Client
    id: int
    filename: str
    from_message: Message
    progress_message: Message
    started: float = 0
    last_update: float = 0
    size: int = 0
    description: Optional[str] = None  # NEW: caption/description for admin summary
