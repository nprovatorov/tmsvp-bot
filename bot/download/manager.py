import os
import logging
from asyncio import create_task, sleep
from datetime import datetime, timedelta
from time import time
from typing import List

from pyrogram.client import Client
from pyrogram.enums import ParseMode
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from .. import BASE_FOLDER, MAX_SIMULTANEOUS_TRANSMISSIONS
from ..util import humanReadableSize, humanReadableTime, safe_relpath
from .types import Download

from ..notifier import notify
from ..messages import (
    starting_download,
    download_progress,
    stopped,
    download_success_user,
    download_infected_user,
    download_failed_user,
    admin_upload_finished,
)
from ..notify_helpers import media_resolution, channel_handle, author_display

from ..scanner import scan_path


downloads: List[Download] = []
running: int = 0
# List of downloads to stop
stop: List[int] = []

def _contact_button_for_message(msg):
    u = getattr(msg, "from_user", None)
    if not u:
        return None
    uname = getattr(u, "username", None)
    if uname:
        url = f"https://t.me/{uname}"
    else:
        uid = getattr(u, "id", None)
        if not uid:
            return None
        url = f"tg://user?id={uid}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("Send Message", url=url)]])


async def run():
    global running
    while True:
        for download in list(downloads):
            if running == MAX_SIMULTANEOUS_TRANSMISSIONS:
                break
            create_task(downloadFile(download))
            logging.info(f"New download initialized: {download.filename}")
            running += 1
            downloads.remove(download)
        try:
            await sleep(1)
        except Exception:
            break


async def downloadFile(download: Download):
    global running
    await download.progress_message.edit(
        text=starting_download(),
        parse_mode=ParseMode.MARKDOWN,
    )
    download.started = time()

    # Resolve paths safely
    clean_name = safe_relpath(download.filename)
    target_path = os.path.join(BASE_FOLDER, clean_name)
    logging.info(
        "[DL] saving to %s (BASE_FOLDER=%s, raw filename=%r)",
        target_path, BASE_FOLDER, download.filename
    )

    # Info for admin summary
    res_str = media_resolution(download.from_message)
    chan = channel_handle(download.from_message)
    author = author_display(download.from_message)
    RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30") or "30")
    delete_on = datetime.now() + timedelta(days=RETENTION_DAYS)

    # Fallback description: prefer what handler set, else message.caption (if any)
    desc_final = (
        (download.description or "") or (getattr(download.from_message, "caption", None) or "")
    ).strip() or None
    if desc_final:
        logging.info("[DL] admin description attached (first 120 chars): %r", desc_final[:120])

    buttons = _contact_button_for_message(download.from_message)

    try:
        result = await download.client.download_media(
            message=download.from_message,
            file_name=target_path,
            progress=createProgress(download.client),
            progress_args=(download,),
        )
        if not isinstance(result, str):
            await download.progress_message.reply(
                download_failed_user(download.filename),
                parse_mode=ParseMode.MARKDOWN,
            )
            # Admin: finished with crash
            await notify(
                admin_upload_finished(
                    channel_handle=chan,
                    author=author,
                    filename=download.filename,
                    resolution=res_str,
                    size_h="unknown",
                    av_status="error",
                    retention_days=RETENTION_DAYS,
                    delete_on=None,
                    description=desc_final,  # include if present
                ),
                reply_markup=buttons,
            )
            return

        real_filename = result
        logging.info("[DL] pyrogram returned path: %s", real_filename)

        # Success message to USER (backwards-compatible)
        seconds_took = max(1e-6, (download.last_update - download.started))
        speed = humanReadableSize(download.size / seconds_took)
        time_took = humanReadableTime(int(seconds_took))
        size_h = humanReadableSize(download.size)

        await download.progress_message.edit(
            download_success_user(download.filename, size_h, time_took, speed),
            parse_mode=ParseMode.MARKDOWN,
        )

        # === Antivirus check ===
        av_status = "clean"
        try:
            res = scan_path(real_filename)
            if res.status == "infected":
                av_status = f"infected:{res.signature or 'unknown'}"
                try:
                    os.remove(real_filename)
                except Exception:
                    logging.exception("Failed to remove infected file %s", real_filename)

                # Tell USER (unchanged)
                await download.progress_message.reply(
                    download_infected_user(download.filename, res.signature or "unknown"),
                    parse_mode=ParseMode.MARKDOWN,
                )

                # Admin: finished (infected/removed)
                await notify(
                    admin_upload_finished(
                        channel_handle=chan,
                        author=author,
                        filename=download.filename,
                        resolution=res_str,
                        size_h=size_h,
                        av_status=av_status,
                        retention_days=RETENTION_DAYS,
                        delete_on=None,           # removed by AV
                        description=desc_final,   # include if present
                    ),
                    reply_markup=buttons,
                )
                return

            elif res.status == "error":
                av_status = "error"

        except Exception:
            logging.exception("AV handling failed")
            av_status = "error"

        # Admin: finished (clean OR scan error)
        await notify(
            admin_upload_finished(
                channel_handle=chan,
                author=author,
                filename=download.filename,
                resolution=res_str,
                size_h=size_h,
                av_status=av_status,           # "clean" | "error"
                retention_days=RETENTION_DAYS,
                delete_on=delete_on,           # planned deletion date
                description=desc_final,        # include if present
            ),
            reply_markup=buttons,
        )

    except Exception:
        logging.exception("Download pipeline crashed for %s", download.filename)
        try:
            await download.progress_message.reply(download_failed_user(download.filename))
        except Exception:
            pass
        # Admin: finished with crash
        await notify(
            admin_upload_finished(
                channel_handle=chan,
                author=author,
                filename=download.filename,
                resolution=res_str,
                size_h="unknown",
                av_status="error",
                retention_days=RETENTION_DAYS,
                delete_on=None,
                description=desc_final,        # include if present
            ),
            reply_markup=buttons,
        )
    finally:
        running -= 1


def createProgress(client: Client):
    async def progress(received: int, total: int, download: Download):
        # This function is called every time that 1MB is downloaded
        if download.id in stop:
            await download.progress_message.edit(
                text=stopped(download.filename),
                parse_mode=ParseMode.MARKDOWN,
            )
            stop.remove(download.id)
            client.stop_transmission()
            return

        # Only update download progress if the last update is 1 second old:
        # avoids flood on very fast networks
        now = time()
        if download.last_update != 0 and (now - download.last_update) < running:
            return

        percent = (received / total * 100) if total else 0
        avg_speed = received / max(1e-6, (now - download.started))
        tte = int((total - received) / max(1e-6, avg_speed)) if total else 0

        await download.progress_message.edit(
            text=download_progress(
                download.filename,
                humanReadableSize(received),
                humanReadableSize(total),
                percent,
                humanReadableSize(avg_speed),
                humanReadableTime(tte),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Stop", callback_data=f"stop {download.id}")]]
            ),
        )
        download.last_update = now
        download.size = total

    return progress


async def stopDownload(_, callback: CallbackQuery):
    id = int(callback.data.split()[-1])
    stop.append(id)
    await callback.answer("Stopping...")
