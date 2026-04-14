"""
main.py — OTP Bot Entry Point (Durian Only)
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from countries_manager import countries_manager
from database import db
from durian_api import get_client
from middlewares import UserMiddleware
from handlers import user as user_handlers
from handlers import admin as admin_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    await db.connect()
    countries_manager.load("countries.json")

    # تهيئة نظام التسعير
    from pricing import pricing
    pricing.init(db)
    await pricing.seed_defaults()

    # تهيئة قناة الإشعارات
    from notifier import init_notifier
    ch_id   = await db.get_setting("notif_channel_id",   "")
    ch_link = await db.get_setting("notif_channel_link", "")
    init_notifier(bot, ch_id, ch_link)

    client = get_client()
    logger.info("Durian client ready: user=%s", config.durian_name)
    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)


async def on_shutdown(bot: Bot) -> None:
    await db.close()
    from durian_api import get_client
    await get_client().close()
    logger.info("Bot stopped.")


async def main() -> None:
    if not config.bot_token:
        logger.critical("BOT_TOKEN not set!")
        sys.exit(1)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(UserMiddleware())
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling…")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
