import asyncio
import logging

from pyrogram import idle

from . import app, commands, download, user
from .housekeeping import run_schedules


async def main():
    logging.info("Registering commands...")
    commands.register(app)
    logging.info("Starting bot v2...")
    await app.start()

    if user:
        logging.info("Starting normal user...")
        await user.start()

    logging.info("Starting background tasks...")
    manager_task = asyncio.create_task(download.manager.run(), name="download-manager")
    housekeeping_task = asyncio.create_task(run_schedules(), name="housekeeping")

    me = await app.get_me()
    logging.info(f"Bot started! I'm @{me.username}")

    try:
        await idle()  # blocks until stop signal
    finally:
        logging.info("Stopping background tasks...")
        for t in (manager_task, housekeeping_task):
            t.cancel()

        # Wait for tasks to finish cancelling without raising
        await asyncio.gather(manager_task, housekeeping_task, return_exceptions=True)

        logging.info("Stopping bot...")
        await app.stop()

        if user:
            logging.info("Stopping user...")
            await user.stop()

        logging.info("All systems stopped!")
    return 0


event_loop = asyncio.get_event_loop()
event_loop.run_until_complete(main())
