# bot/__main__.py
import asyncio
import logging
from contextlib import suppress

from pyrogram import idle

from . import app, commands, download, user
from .housekeeping import run_schedules


# ---------- Resilience helpers (no behavioral changes to your flow) ----------

async def _start_with_retries(client, name: str, first_delay: int = 5, max_delay: int = 300):
    """Start a Pyrogram client with exponential backoff until it succeeds."""
    delay = first_delay
    while True:
        try:
            await client.start()
            me = await client.get_me()
            logging.info("%s started as @%s", name, getattr(me, "username", "?"))
            return
        except Exception as e:
            logging.warning("%s start failed: %r. Retrying in %ss...", name, e, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)


async def _stop_safely(client, name: str):
    with suppress(Exception):
        await client.stop()
        logging.info("%s stopped.", name)


async def _health_watchdog(ping_every: int = 30, backoff_initial: int = 5, backoff_max: int = 300):
    """
    Periodically ping Telegram. If ping fails, stop() and try start() with backoff
    until we’re back online. Uses the same Client instance; handlers remain intact.
    """
    backoff = backoff_initial
    try:
        while True:
            try:
                await app.get_me()          # lightweight health check
                backoff = backoff_initial   # reset on success
            except Exception as e:
                logging.warning("Health ping failed: %r. Reconnecting…", e)
                with suppress(Exception):
                    await app.stop()
                await asyncio.sleep(backoff)
                try:
                    await app.start()
                    await app.get_me()      # verify
                    logging.info("Reconnected to Telegram.")
                    backoff = backoff_initial
                except Exception as e2:
                    logging.error("Reconnect attempt failed: %r. Next in %ss", e2, backoff)
                    backoff = min(backoff * 2, backoff_max)
            await asyncio.sleep(ping_every)
    except asyncio.CancelledError:
        logging.info("health-watchdog cancelled")


# ---------- Main (keeps your original ordering) ----------

async def main():
    logging.info("Registering commands...")
    commands.register(app)

    logging.info("Starting bot v2 (resilient)…")
    await _start_with_retries(app, "Bot")

    if user:
        logging.info("Starting normal user (resilient)…")
        await _start_with_retries(user, "User")

    logging.info("Starting background tasks...")
    manager_task = asyncio.create_task(download.manager.run(), name="download-manager")
    housekeeping_task = asyncio.create_task(run_schedules(), name="housekeeping")
    health_task = asyncio.create_task(_health_watchdog(), name="health-watchdog")

    me = await app.get_me()
    logging.info(f"Bot started! I'm @{me.username}")

    try:
        await idle()  # blocks until stop signal
    finally:
        logging.info("Stopping background tasks...")
        for t in (manager_task, housekeeping_task, health_task):
            t.cancel()
        with suppress(Exception):
            await asyncio.gather(manager_task, housekeeping_task, health_task, return_exceptions=True)

        logging.info("Stopping bot...")
        await _stop_safely(app, "Bot")

        if user:
            logging.info("Stopping user...")
            await _stop_safely(user, "User")

        logging.info("All systems stopped!")
    return 0


# Keep your original launcher style
event_loop = asyncio.get_event_loop()
event_loop.run_until_complete(main())