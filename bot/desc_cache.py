# desc_cache.py
import os
import time
from typing import Optional, Dict, Tuple

TTL = int(os.getenv("DESC_TTL_SECONDS", "180") or "180")  # 3 minutes
_store: Dict[int, Tuple[str, float]] = {}

def put(chat_id: int, text: str) -> None:
    if text and text.strip():
        _store[chat_id] = (text.strip(), time.time())

def take(chat_id: int) -> Optional[str]:
    item = _store.pop(chat_id, None)
    if not item:
        return None
    text, ts = item
    if time.time() - ts > TTL:
        return None
    return text
