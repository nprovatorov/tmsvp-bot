# messages.py (append these)
from textwrap import dedent
from datetime import datetime

def _md(s: str) -> str:
    # super-light markdown escaping for backticks only (filenames)
    return s.replace("`", "ʼ")

def admin_upload_started(channel_handle: str | None, filename: str, resolution: str | None, link: str | None, author: str) -> str:
    title = f"🆕 New Upload Request from #{channel_handle or 'unknown'}"
    parts = [
        title,
        f"- File: `{_md(filename)}`" + (f" ({resolution})" if resolution else ""),
        f"- From: {author}" + (f" · [open]({link})" if link else ""),
    ]
    return "\n".join(parts)

def admin_upload_finished(
    channel_handle: str | None,
    author: str,
    filename: str,
    resolution: str | None,
    size_h: str,
    av_status: str,          # "clean" | "infected:<sig>" | "error"
    retention_days: int,
    delete_on: datetime | None,
) -> str:
    title = "📥 File Download Finished"
    lines = [title]
    lines.append(f"- From: #{channel_handle or 'unknown'} (account: {author})")
    lines.append(f"- File: `{_md(filename)}`" + (f" ({resolution})" if resolution else ""))
    lines.append(f"- Size: **{size_h}**")

    # Antivirus line with emoji
    if av_status.startswith("infected:"):
        sig = av_status.split(":", 1)[1]
        lines.append(f"- AV: ❌ Infected (`{_md(sig)}`)")
        # Status line for infection
        lines.append("- Status: removed by antivirus")
    elif av_status == "error":
        lines.append(f"- AV: ⚠️ Scan error (kept)")
        # File status (kept; still under retention)
        if delete_on:
            lines.append(f"- Status: retained for {retention_days} days · auto-delete on **{delete_on:%Y-%m-%d}**")
    else:
        lines.append(f"- AV: ✅ Clean")
        if delete_on:
            lines.append(f"- Status: retained for {retention_days} days · auto-delete on **{delete_on:%Y-%m-%d}**")

    return "\n".join(lines)


def file_added(path: str) -> str:
    return f"File `{path}` added to list."

def file_exists(path: str) -> str:
    return f"File `{path}` already exists!"

def starting_download() -> str:
    return "Starting download..."

def download_done(filename: str, total_h: str, took_h: str, speed_h: str) -> str:
    return dedent(f"""
        ✅ File `{filename}` downloaded.
        Download of {total_h} complete in {took_h}, it's an average speed of **{speed_h}/s**
    """)

def download_progress(filename: str, got_h: str, total_h: str, pct: float, speed_h: str, tte_h: str) -> str:
    return dedent(f"""
        `{filename}`:
        **{got_h}/{total_h} {pct:0.2f}%**
        {speed_h}/s {tte_h} till complete
    """)

def stopped(filename: str) -> str:
    return f"Download of `{filename}` stopped!"

def uploads_notice_disabled() -> str:
    return "Uploads are only accepted in the public channel."

# Admin / private channel notifications
def notify_new_upload(channel: str, filename: str, size_h: str, author: str) -> str:
    return dedent(f"""
        🆕 New upload from **#{channel}**
        - File: `{filename}`
        - Size: {size_h}
        - From: {author}
    """)

def weekly_usage(total_h: str, used_h: str, free_h: str) -> str:
    return dedent(f"""
        📊 Weekly disk usage
        - Total: **{total_h}**
        - Used: **{used_h}**
        - Free: **{free_h}**
    """)

def retention_warning(filename: str, age_days: int, delete_in_days: int) -> str:
    return f"⚠️ File `{filename}` is {age_days}d old and will be deleted in {delete_in_days}d."

def retention_deleted(filename: str, age_days: int) -> str:
    return f"🧹 Deleted `{filename}` (age: {age_days}d)."

# messages.py

def download_success_user(filename: str, size_h: str, time_h: str, speed_h: str) -> str:
    return f"✅ File `{filename}` downloaded ({size_h}) in {time_h} at ~{speed_h}/s."

def download_infected_user(filename: str, signature: str) -> str:
    return f"❌ File `{filename}` was infected ({signature}) and has been removed."

def download_failed_user(filename: str) -> str:
    return f"❌ Download failed for `{filename}`."

def admin_download_clean(channel: str, filename: str, size_h: str, author: str) -> str:
    return (
        f"✅ File downloaded & clean\n"
        f"- File: `{filename}` ({size_h})\n"
        f"- From: #{channel} by {author}"
    )

def admin_download_infected(filename: str, signature: str) -> str:
    return f"⚠️ Infected file removed: `{filename}` (sig: {signature})"

def admin_scan_error(filename: str) -> str:
    return f"⚠️ AV scan error for `{filename}`; file kept."

def admin_download_crashed(filename: str) -> str:
    return f"⚠️ Download crashed for `{filename}`"
