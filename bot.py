"""
Stranger Chaos Bot — main entry point
Run:  python bot.py
"""

import asyncio
import logging
import os

from aiohttp import ClientSession, ClientTimeout, web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from middlewares import BanMiddleware
from plugins import start, chat, commands, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="search",     description="Find a stranger"),
    BotCommand(command="next",       description="Skip to a new partner"),
    BotCommand(command="stop",       description="End current chat"),
    BotCommand(command="icebreaker", description="Send a conversation starter"),
    BotCommand(command="interests",  description="Pick interests for better matches"),
    BotCommand(command="daily",      description="Claim your daily bonus searches"),
    BotCommand(command="profile",    description="View / edit your profile"),
    BotCommand(command="link",       description="Send your Telegram profile to your partner"),
    BotCommand(command="block",      description="Block current partner (premium)"),
    BotCommand(command="blocklist",  description="View blocked users"),
    BotCommand(command="unblock",    description="Unblock a user by list number"),
    BotCommand(command="del",        description="Delete a message for both sides (premium)"),
    BotCommand(command="report",     description="Report current partner"),
    BotCommand(command="start",      description="Restart / register"),
]


# ── Tiny web server so the bot can run as a Render *Web Service* ──────────────
# Render web services must listen on $PORT. Only starts when PORT is set
# (Render/Heroku web), so local runs and worker deploys are unaffected.

async def start_web_server():
    port = os.getenv("PORT")
    if not port:
        return None

    async def alive(_request):
        return web.Response(text="Stranger Chaos Bot is running")

    app = web.Application()
    app.router.add_get("/", alive)
    app.router.add_get("/health", alive)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    logger.info("Health server listening on port %s", port)
    return runner


async def keep_alive():
    """
    Free Render web services sleep after ~15 min without web traffic, which
    would stop the bot. Ping our own public URL every 10 min. (Even more
    reliable: also add the URL to a free uptime monitor such as UptimeRobot.)
    """
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("SELF_URL")
    if not url:
        return
    async with ClientSession(timeout=ClientTimeout(total=20)) as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(url) as r:
                    logger.debug("keep-alive ping -> %s", r.status)
            except Exception as e:
                logger.warning("keep-alive ping failed: %s", e)


async def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Set BOT_TOKEN (env var or .env file) before starting the bot.")

    runner = await start_web_server()      # bind the port first, fast
    ping_task = asyncio.create_task(keep_alive())

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Registers users + blocks banned ones for every message and button press
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())

    # Order matters: registration FSM first, then features, relay (catch-all) last
    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(admin.router)
    dp.include_router(chat.router)

    await bot.set_my_commands(BOT_COMMANDS)
    me = await bot.get_me()
    logger.info("Stranger Chaos Bot starting as @%s ...", me.username)

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        ping_task.cancel()
        if runner:
            await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
