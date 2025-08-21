import os
import asyncio
import time
import logging
from datetime import datetime
from pathlib import Path

from . import folder
from .messages import retention_warning, retention_deleted
from .notifier import notify
from .metrics import append_event, send_weekly_report

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30") or "30")
RETENTION_NOTICE_DAYS = int(os.getenv("RETENTION_NOTICE_DAYS", "2") or "2")
RETENTION_WARN_ONCE = os.getenv("RETENTION_WARN_ONCE", "1") != "0"  # warn once by default

DISK_USAGE_DAY = (os.getenv("DISK_USAGE_DAY", "Monday") or "Monday").lower()
DISK_USAGE_HOUR = int(os.getenv("DISK_USAGE_HOUR", "9"))

DAY_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6
}


def now_ts() -> float:
    return time.time()


def file_age_days(p: Path) -> int:
    try:
        st = p.stat()
        return int((now_ts() - st.st_mtime) / 86400.0)
    except Exception:
        return 0


def _safe_regular_file(p: Path, base: Path) -> bool:
    """
    Resolve symlinks and ensure the file lives directly under the base folder.
    Prevents accidental deletes outside of /data via symlinks.
    """
    try:
        rp = p.resolve(strict=True)
        return rp.is_file() and rp.parent == base.resolve(strict=True)
    except FileNotFoundError:
        return False
    except Exception:
        logging.exception("housekeeping: resolve failed for %s", p)
        return False


def _warn_flag(p: Path) -> Path:
    # Sidecar marker to warn only once per file within the T-RETENTION_NOTICE window
    return p.with_name(p.name + ".warned")


async def do_retention():
    base = Path(folder.get())
    if not base.exists():
        logging.info("housekeeping: base folder missing: %s", base)
        return

    warn_window_start = max(0, RETENTION_DAYS - RETENTION_NOTICE_DAYS)

    for p in base.iterdir():
        if not _safe_regular_file(p, base):
            continue

        age = file_age_days(p)

        # --- Warning window (T - notice_days ... T - 1)
        if warn_window_start <= age < RETENTION_DAYS:
            flag = _warn_flag(p)
            should_warn = True
            if RETENTION_WARN_ONCE and flag.exists():
                should_warn = False
            if should_warn:
                try:
                    await notify(retention_warning(p.name, age, RETENTION_NOTICE_DAYS))
                    logging.info("housekeeping: warned: %s (age=%d)", p.name, age)
                    if RETENTION_WARN_ONCE:
                        try:
                            flag.touch(exist_ok=True)
                        except Exception:
                            logging.exception("housekeeping: failed to write warn flag for %s", p)
                except Exception:
                    logging.exception("housekeeping: warning notify failed for %s", p)

        # --- Deletion at/after retention threshold
        if age >= RETENTION_DAYS:
            size_b = 0
            try:
                size_b = p.stat().st_size
            except Exception:
                pass

            try:
                p.unlink()
                # clean warn flag if present
                try:
                    wf = _warn_flag(p)
                    if wf.exists():
                        wf.unlink(missing_ok=True)
                except Exception:
                    logging.exception("housekeeping: failed to remove warn flag for %s", p)

                # metrics + notify
                append_event(
                    "retention_deleted",
                    filename=p.name,
                    size_bytes=int(size_b),
                    age_days=int(age),
                )
                await notify(retention_deleted(p.name, age))
                logging.info("housekeeping: deleted: %s (age=%d, size=%d)", p.name, age, size_b)
            except Exception:
                logging.exception("housekeeping: failed to delete %s", p)


async def run_schedules():
    """
    Simple scheduler loop:
      - Weekly report: on configured weekday & hour (admin dashboard)
      - Retention pass: daily at ~03:00
    """
    while True:
        try:
            now = datetime.now()
            # Weekly analytics report at configured weekday/hour (once at minute :00)
            if (
                now.weekday() == DAY_INDEX.get(DISK_USAGE_DAY, 0)
                and now.hour == DISK_USAGE_HOUR
                and now.minute == 0
            ):
                try:
                    await send_weekly_report()
                    logging.info("housekeeping: weekly report sent")
                except Exception:
                    logging.exception("housekeeping: weekly report failed")
                await asyncio.sleep(61)  # prevent double-fire within the same minute

            # Daily retention at ~03:00
            if now.hour == 3 and now.minute == 0:
                await do_retention()
                await asyncio.sleep(61)

        except asyncio.CancelledError:
            break
        except Exception:
            logging.exception("housekeeping tick failed")

        await asyncio.sleep(30)
