import os
import asyncio
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

from . import folder
from .sysinfo import diskUsage
from .messages import weekly_usage, retention_warning, retention_deleted
from .notifier import notify

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
RETENTION_NOTICE_DAYS = int(os.getenv("RETENTION_NOTICE_DAYS", "2"))
DISK_USAGE_DAY = (os.getenv("DISK_USAGE_DAY", "Monday") or "Monday").lower()
DISK_USAGE_HOUR = int(os.getenv("DISK_USAGE_HOUR", "9"))

DAY_INDEX = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}

def now_ts() -> float:
    return time.time()

def file_age_days(p: Path) -> int:
    try:
        st = p.stat()
        age = (now_ts() - st.st_mtime) / 86400.0
        return int(age)
    except Exception:
        return 0

async def do_weekly_usage():
    usage = diskUsage(folder.get())
    await notify(weekly_usage(usage.capacity, usage.used, usage.free))

async def do_retention():
    base = Path(folder.get())
    if not base.exists():
        return
    for p in base.iterdir():
        if not p.is_file():
            continue
        age = file_age_days(p)
        # Warn
        if age == (RETENTION_DAYS - RETENTION_NOTICE_DAYS):
            await notify(retention_warning(p.name, age, RETENTION_NOTICE_DAYS))
        # Delete
        if age >= RETENTION_DAYS:
            try:
                p.unlink()
                await notify(retention_deleted(p.name, age))
            except Exception:
                logging.exception("Failed to delete %s", p)

async def run_schedules():
    # Simple tick loop, wake once per minute
    while True:
        try:
            now = datetime.now()
            # Weekly usage at configured weekday/hour
            if now.weekday() == DAY_INDEX.get(DISK_USAGE_DAY, 0) and now.hour == DISK_USAGE_HOUR and now.minute == 0:
                await do_weekly_usage()
                await asyncio.sleep(61)  # avoid double-fire
            # Daily retention at ~03:00
            if now.hour == 3 and now.minute == 0:
                await do_retention()
                await asyncio.sleep(61)
        except asyncio.CancelledError:
            break
        except Exception:
            logging.exception("housekeeping tick failed")
        await asyncio.sleep(30)
