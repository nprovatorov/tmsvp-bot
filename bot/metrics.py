# bot/metrics.py
import os, json, logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from collections import defaultdict, Counter
from typing import Tuple, Optional

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from . import CONFIG_FOLDER, folder
from .sysinfo import diskUsage
from .util import humanReadableSize
from .notifier import notify
from .messages import weekly_report_text


# ========= Paths & constants =========

METRICS_DIR = Path(CONFIG_FOLDER) / "metrics"
CLIENTS_FILE = METRICS_DIR / "clients_seen.json"   # { user_id(str): first_ts(int) }
EXPORTS_DIR = METRICS_DIR / "exports"

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30") or "30")
RETENTION_NOTICE_DAYS = int(os.getenv("RETENTION_NOTICE_DAYS", "2") or "2")

# ========= Utilities =========

def _mkdirp(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _now_ts() -> int:
    return int(datetime.now().timestamp())

def _week_key_from_ts(ts: int) -> Tuple[int, int]:
    d = datetime.fromtimestamp(ts)
    y, w, _ = d.isocalendar()  # Python 3.11: (year, week, weekday)
    return int(y), int(w)

def _events_file_for_ts(ts: int) -> Path:
    y, w = _week_key_from_ts(ts)
    return METRICS_DIR / f"events-{y}-W{w:02d}.jsonl"

def _safe_load_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def _append_jsonl(path: Path, obj: dict):
    _mkdirp(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _load_clients_seen() -> Dict[str, int]:
    try:
        if CLIENTS_FILE.exists():
            return json.loads(CLIENTS_FILE.read_text("utf-8"))
    except Exception:
        logging.exception("metrics: failed to read clients_seen.json")
    return {}

def _save_clients_seen(data: Dict[str, int]):
    try:
        _mkdirp(CLIENTS_FILE.parent)
        tmp = CLIENTS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(CLIENTS_FILE)
    except Exception:
        logging.exception("metrics: failed to write clients_seen.json")

# ========= Public API: event appenders =========

def append_event(kind: str, **kwargs):
    """
    Append a single metrics event to the current ISO week JSONL file.
    DB-free, append-only.
    """
    ts = int(kwargs.pop("ts", _now_ts()))
    rec = {"ts": ts, "kind": kind}
    rec.update(kwargs)
    try:
        _append_jsonl(_events_file_for_ts(ts), rec)
    except Exception:
        logging.exception("metrics: append_event failed (%s)", kind)

    # Track first-seen time for clients (for "new client this week")
    if kind == "upload_started":
        uid = kwargs.get("user_id")
        if uid is not None:
            seen = _load_clients_seen()
            key = str(uid)
            if key not in seen:
                seen[key] = ts
                _save_clients_seen(seen)

# ========= Aggregation / rollup =========

@dataclass
class WeekRollup:
    iso_year: int
    iso_week: int
    # volumes
    uploads_started: int = 0
    uploads_finished: int = 0
    clean_count: int = 0
    infected_count: int = 0
    cancelled_count: int = 0
    error_count: int = 0
    scan_error_count: int = 0
    total_clean_bytes: int = 0
    # performance
    durations: List[float] = None
    speeds: List[float] = None
    # clients
    per_client_bytes: Dict[str, int] = None
    per_client_count: Dict[str, int] = None
    new_clients: List[str] = None
    missing_desc_count: int = 0
    # timing buckets
    started_by_hour: Counter = None
    # file mix
    by_ext_bytes: Dict[str, int] = None
    by_ext_count: Dict[str, int] = None
    size_buckets: Dict[str, int] = None
    largest_files: List[Tuple[str, int, str]] = None  # (filename, size, client)
    # retention/deletions (this week)
    deleted_files_count: int = 0
    deleted_bytes: int = 0

def _client_key(username: Optional[str], user_id: Optional[int]) -> str:
    if username:
        return f"@{username}"
    return f"id:{user_id}" if user_id is not None else "unknown"

def _ext_of(name: str) -> str:
    _, ext = os.path.splitext(name or "")
    return (ext[1:].lower() if ext else "noext")

def _size_bucket(sz: int) -> str:
    if sz < 10 * 1024 * 1024: return "<10MB"
    if sz < 100 * 1024 * 1024: return "10–100MB"
    if sz < 1024 * 1024 * 1024: return "100MB–1GB"
    return ">1GB"

def _percentile(vals: List[float], p: float) -> float:
    if not vals:
        return 0.0
    a = sorted(vals)
    k = int(round((len(a) - 1) * p))
    return a[k]

def _iter_week_files() -> List[Path]:
    if not METRICS_DIR.exists():
        return []
    return sorted(METRICS_DIR.glob("events-*-W*.jsonl"))

def _prev_weeks_keys(curr: Tuple[int, int], max_weeks: int = 4) -> List[Tuple[int, int]]:
    files = _iter_week_files()
    keys = []
    for p in files:
        try:
            name = p.stem  # events-YYYY-Www
            _, y, W = name.split("-")
            y = int(y)
            w = int(W[1:])
            keys.append((y, w))
        except Exception:
            continue
    keys = sorted(set(keys))
    y0, w0 = curr
    keys = [k for k in keys if k <= (y0, w0)]
    return keys[-max_weeks:]

def _load_week(iso_year: int, iso_week: int) -> List[dict]:
    path = METRICS_DIR / f"events-{iso_year}-W{iso_week:02d}.jsonl"
    return list(_safe_load_jsonl(path))

def rollup_week(iso_year: int, iso_week: int) -> WeekRollup:
    events = _load_week(iso_year, iso_week)
    roll = WeekRollup(
        iso_year=iso_year, iso_week=iso_week,
        durations=[], speeds=[],
        per_client_bytes=defaultdict(int),
        per_client_count=defaultdict(int),
        new_clients=[],
        started_by_hour=Counter(),
        by_ext_bytes=defaultdict(int),
        by_ext_count=defaultdict(int),
        size_buckets=defaultdict(int),
        largest_files=[],
    )

    for ev in events:
        k = ev.get("kind")
        if k == "upload_started":
            roll.uploads_started += 1
            if not ev.get("has_desc", False):
                roll.missing_desc_count += 1
            ts = int(ev.get("ts", 0))
            hour = datetime.fromtimestamp(ts).hour
            roll.started_by_hour[hour] += 1

        elif k == "upload_finished":
            roll.uploads_finished += 1
            uid = ev.get("user_id")
            uname = ev.get("username")
            key = _client_key(uname, uid)

            result = ev.get("result")
            size_b = int(ev.get("size_bytes", 0) or 0)
            if result == "clean":
                roll.clean_count += 1
                roll.total_clean_bytes += size_b
                roll.per_client_bytes[key] += size_b
                roll.per_client_count[key] += 1
                roll.durations.append(float(ev.get("duration_sec", 0) or 0.0))
                roll.speeds.append(float(ev.get("speed_mb_s", 0) or 0.0))
                ext = _ext_of(ev.get("filename", ""))
                roll.by_ext_bytes[ext] += size_b
                roll.by_ext_count[ext] += 1
                roll.size_buckets[_size_bucket(size_b)] += 1
                roll.largest_files.append((ev.get("filename",""), size_b, key))
            elif result == "infected":
                roll.infected_count += 1
            elif result == "cancelled":
                roll.cancelled_count += 1
            elif result == "scan_error":
                roll.scan_error_count += 1
            else:
                roll.error_count += 1

        elif k == "retention_deleted":
            roll.deleted_files_count += 1
            roll.deleted_bytes += int(ev.get("size_bytes", 0) or 0)

    roll.largest_files = sorted(roll.largest_files, key=lambda x: x[1], reverse=True)[:5]
    return roll

def _aggregate_net_growth(week_keys: List[Tuple[int,int]]) -> List[int]:
    out = []
    for (y, w) in week_keys:
        r = rollup_week(y, w)
        out.append(int(r.total_clean_bytes) - int(r.deleted_bytes))
    return out

# ========= Report rendering =========

def _mk_dm_button_for_top_client(roll: WeekRollup) -> Optional[InlineKeyboardMarkup]:
    if not roll.per_client_bytes:
        return None
    top_client = max(roll.per_client_bytes.items(), key=lambda kv: kv[1])[0]  # "@name" or "id:123"
    if top_client.startswith("@"):
        url = f"https://t.me/{top_client[1:]}"
    elif top_client.startswith("id:"):
        try:
            uid = int(top_client.split(":",1)[1])
            url = f"tg://user?id={uid}"
        except Exception:
            return None
    else:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("Send Message to top client", url=url)]])


def _retention_outlook() -> Tuple[int, Optional[int]]:
    base = Path(folder.get())
    if not base.exists():
        return (0, None)

    def age_days(p: Path) -> int:
        try:
            st = p.stat()
            return int((datetime.now().timestamp() - st.st_mtime) / 86400.0)
        except Exception:
            return 0

    warn_start = RETENTION_DAYS - RETENTION_NOTICE_DAYS
    soon = 0
    oldest = 0
    for p in base.iterdir():
        if p.is_file():
            a = age_days(p)
            if warn_start <= a < RETENTION_DAYS:
                soon += 1
            if a > oldest:
                oldest = a

    return (soon, oldest or None)


def _avg_growth_last_weeks(incl_year: int, incl_week: int, window: int = 4) -> Optional[float]:
    keys = _prev_weeks_keys((incl_year, incl_week), max_weeks=window)
    if not keys:
        return None
    growths = _aggregate_net_growth(keys)
    if not growths:
        return None
    return sum(growths) / max(1, len(growths))

def generate_weekly_text_and_buttons() -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    y, w, _ = datetime.now().isocalendar()
    this = rollup_week(y, w)
    last = rollup_week(y, w-1) if w > 1 else None
    avg_growth = _avg_growth_last_weeks(y, w, 4)  # kept for future use if needed

    # Build date range label (Mon–Sun)
    week_start = datetime.fromisocalendar(this.iso_year, this.iso_week, 1)
    week_end = week_start + timedelta(days=6)
    date_range = f"{week_start.strftime('%b %d')}–{week_end.strftime('%b %d, %Y')}"

    # Current disk usage (strings)
    usage = diskUsage(folder.get())
    used = usage.used
    total = usage.capacity

    # WoW delta helper (produce string like "↑ 25%" / "↓ 10%" / "→ 0%"/"n/a")
    def _delta(cur: int, prev: int) -> str:
        if not prev:
            return "n/a"
        ch = ((cur - prev) / prev) * 100.0
        sign = "↑" if ch > 0 else ("↓" if ch < 0 else "→")
        return f"{sign} {abs(ch):.0f}%"

    last_bytes = (last.total_clean_bytes if last else 0)
    wow_bytes = _delta(this.total_clean_bytes, last_bytes)

    # Top lists & busiest hour
    busiest_hour = max(this.started_by_hour.items(), key=lambda kv: kv[1])[0] if this.started_by_hour else None
    top_by_bytes = sorted(this.per_client_bytes.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_by_count = sorted(this.per_client_count.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_ext = sorted(this.by_ext_count.items(), key=lambda kv: kv[1], reverse=True)[:6]

    # Retention outlook from filesystem
    soon, oldest = _retention_outlook()

    # Prepare payload for messages.weekly_report_text
    payload = {
        "iso_year": this.iso_year,
        "iso_week": this.iso_week,
        "date_range": date_range,
        "used": used,
        "total": total,
        "total_clean_bytes": int(this.total_clean_bytes),
        "wow_bytes": wow_bytes,
        "uploads_started": int(this.uploads_started),
        "uploads_finished": int(this.uploads_finished),
        "clean_count": int(this.clean_count),
        "infected_count": int(this.infected_count),
        "cancelled_count": int(this.cancelled_count),
        "error_count": int(this.error_count),
        "scan_error_count": int(this.scan_error_count),
        "busiest_hour": busiest_hour,
        "missing_desc_count": int(this.missing_desc_count),
        "top_by_bytes": list(top_by_bytes),   # List[Tuple[str,int]]
        "top_by_count": list(top_by_count),   # List[Tuple[str,int]]
        "top_ext": list(top_ext),             # List[Tuple[str,int]]
        "largest_files": list(this.largest_files),  # List[Tuple[str,int,str]]
        "retention_notice_days": RETENTION_NOTICE_DAYS,
        "soon": int(soon),
        "deleted_files_count": int(this.deleted_files_count),
        "deleted_bytes": int(this.deleted_bytes),
        "oldest": oldest,
        "new_clients": list(this.new_clients or []),
    }

    text = weekly_report_text(payload)
    buttons = _mk_dm_button_for_top_client(this)
    return text, buttons

async def send_weekly_report():
    text, buttons = generate_weekly_text_and_buttons()
    await notify(text, reply_markup=buttons)
