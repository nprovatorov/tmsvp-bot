# bot/__main__.py
import asyncio
import logging
import os
from contextlib import suppress

from pyrogram import idle

from . import app, commands, download, user
from .housekeeping import run_schedules


# ---------- Resilience configuration ----------
_HEALTH_INTERVAL = 45           # seconds between health pings
_BACKOFF_INIT = 5               # initial backoff delay (seconds)
_BACKOFF_MAX = 300              # max backoff delay (5 min)
_HEALTH_TIMEOUT = 15            # seconds before get_me() times out
_CLIENT_OP_TIMEOUT = 30         # seconds before start()/stop() times out
_MAX_FAILURES = 20              # hard-restart after this many consecutive failures

# ---------- Reconnect state ----------
_reconnect_lock = asyncio.Lock()
_consecutive_failures = 0


async def _ensure_connected():
    """
    Single, lock-guarded reconnect path.

    Every piece of code that needs to reconnect MUST call this function.
    The asyncio.Lock serialises concurrent callers so that only one
    stop → start cycle runs at a time.

    This is the core fix for the death spiral:
    - Old code had BOTH a disconnect handler AND a health watchdog that
      independently called stop()/start().  When they raced, one would
      succeed and the other would hit "Client is already connected",
      leaving the Pyrogram dispatcher dead (HandlerTasks stopped, never
      restarted).
    - Now there is exactly ONE reconnect path.  The lock guarantees that
      the second caller either skips (lock already held) or re-verifies
      after the first caller finishes.
    """
    global _consecutive_failures

    # Fast path: another task is already reconnecting — let it finish.
    # Safe in asyncio (single-threaded): no TOCTOU between check and acquire.
    if _reconnect_lock.locked():
        logging.debug("_ensure_connected: lock held, skipping.")
        return

    async with _reconnect_lock:
        # Re-check after acquiring the lock: the previous holder may have
        # already restored the connection.
        if app.is_connected:
            try:
                await asyncio.wait_for(app.get_me(), timeout=_HEALTH_TIMEOUT)
                _consecutive_failures = 0
                return
            except Exception:
                logging.warning(
                    "is_connected=True but get_me() failed — "
                    "session is stale, forcing full reconnect."
                )

        # ---------- full stop → start cycle ----------
        try:
            await asyncio.wait_for(app.stop(), timeout=_CLIENT_OP_TIMEOUT)
        except asyncio.TimeoutError:
            logging.error("app.stop() timed out after %ds.", _CLIENT_OP_TIMEOUT)
        except Exception:
            pass  # already stopped or never started — both fine

        delay = _BACKOFF_INIT
        while True:
            _consecutive_failures += 1

            if _consecutive_failures >= _MAX_FAILURES:
                logging.critical(
                    "%d consecutive reconnect failures — hard-restarting "
                    "(Docker will bring the container back).",
                    _consecutive_failures,
                )
                os._exit(1)

            try:
                await asyncio.wait_for(app.start(), timeout=_CLIENT_OP_TIMEOUT)
                me = await asyncio.wait_for(
                    app.get_me(), timeout=_HEALTH_TIMEOUT
                )
                _consecutive_failures = 0
                logging.info(
                    "Reconnected as @%s", getattr(me, "username", "?")
                )
                return
            except Exception as e:
                logging.warning(
                    "Reconnect %d/%d failed: %r — retrying in %ds",
                    _consecutive_failures, _MAX_FAILURES, e, delay,
                )
                # Clean up half-started client before next attempt
                try:
                    await asyncio.wait_for(
                        app.stop(), timeout=_CLIENT_OP_TIMEOUT
                    )
                except Exception:
                    pass
                await asyncio.sleep(delay)
                delay = min(delay * 2, _BACKOFF_MAX)


async def _health_watchdog():
    """
    Periodic liveness probe.

    Checks app.is_connected and verifies with get_me() (with timeout).
    On any failure, funnels into the single _ensure_connected() path.
    """
    global _consecutive_failures
    try:
        while True:
            await asyncio.sleep(_HEALTH_INTERVAL)
            try:
                if not app.is_connected:
                    logging.warning(
                        "Health: not connected — triggering reconnect."
                    )
                    await _ensure_connected()
                    continue

                await asyncio.wait_for(
                    app.get_me(), timeout=_HEALTH_TIMEOUT
                )
                _consecutive_failures = 0

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logging.warning(
                    "Health: get_me() timed out — triggering reconnect."
                )
                await _ensure_connected()
            except Exception as e:
                logging.warning(
                    "Health: probe failed (%r) — triggering reconnect.", e
                )
                await _ensure_connected()
    except asyncio.CancelledError:
        logging.info("Health watchdog stopped.")


async def _stop_safely(client, name: str):
    try:
        await asyncio.wait_for(client.stop(), timeout=_CLIENT_OP_TIMEOUT)
        logging.info("%s stopped.", name)
    except Exception:
        logging.debug("%s stop failed (may already be stopped).", name)


# ---------- Main ----------

async def main():
    logging.info("Registering commands...")
    commands.register(app)

    # ---- Initial start with retries ----
    logging.info("Starting bot (resilient)…")
    delay = _BACKOFF_INIT
    for attempt in range(1, _MAX_FAILURES + 1):
        try:
            await asyncio.wait_for(app.start(), timeout=_CLIENT_OP_TIMEOUT)
            break
        except Exception as e:
            logging.warning(
                "Start attempt %d/%d failed: %r. Retrying in %ds...",
                attempt, _MAX_FAILURES, e, delay,
            )
            with suppress(Exception):
                await asyncio.wait_for(app.stop(), timeout=_CLIENT_OP_TIMEOUT)
            if attempt == _MAX_FAILURES:
                logging.critical(
                    "Could not start after %d attempts. Exiting.", _MAX_FAILURES
                )
                os._exit(1)
            await asyncio.sleep(delay)
            delay = min(delay * 2, _BACKOFF_MAX)

    me = await app.get_me()
    logging.info("Bot started as @%s", getattr(me, "username", "?"))

    if user:
        logging.info("Starting user client…")
        try:
            await user.start()
            logging.info("User client started.")
        except Exception:
            logging.exception("User client failed to start (continuing without it).")

    logging.info("Starting background tasks...")
    manager_task = asyncio.create_task(
        download.manager.run(), name="download-manager"
    )
    housekeeping_task = asyncio.create_task(
        run_schedules(), name="housekeeping"
    )
    health_task = asyncio.create_task(
        _health_watchdog(), name="health-watchdog"
    )

    logging.info("Bot started! I'm @%s", me.username)

    try:
        await idle()  # blocks until stop signal
    finally:
        logging.info("Stopping background tasks...")
        for t in (manager_task, housekeeping_task, health_task):
            t.cancel()
        with suppress(Exception):
            await asyncio.gather(
                manager_task, housekeeping_task, health_task,
                return_exceptions=True,
            )

        logging.info("Stopping bot...")
        await _stop_safely(app, "Bot")

        if user:
            logging.info("Stopping user...")
            await _stop_safely(user, "User")

        logging.info("All systems stopped!")


# Keep the original event loop approach — asyncio.run() creates a new loop
# that conflicts with Pyrogram/Kurigram's internal signal handling and
# idle(), causing handlers to never fire on this platform.
loop = asyncio.get_event_loop()
loop.run_until_complete(main())