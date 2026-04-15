"""
main.py — OTP Bot Entry Point (Durian Only)
pyTelegramBotAPI (asyncio) version
"""
from __future__ import annotations

import asyncio
import logging
import sys

import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_storage import StateMemoryStorage

from config import config
from countries_manager import countries_manager
from database import db
from durian_api import get_client

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

# ── Bot singleton (يُستورد من الـ handlers) ───────────────────────
bot = AsyncTeleBot(
    token=config.bot_token,
    state_storage=StateMemoryStorage(),
    parse_mode="HTML",
)


async def on_startup() -> None:
    await db.connect()
    countries_manager.load("countries.json")

    from pricing import pricing
    pricing.init(db)
    await pricing.seed_defaults()

    from notifier import init_notifier
    ch_id   = await db.get_setting("notif_channel_id",   "")
    ch_link = await db.get_setting("notif_channel_link", "")
    init_notifier(bot, ch_id, ch_link)

    client = get_client()
    logger.info("Durian client ready: user=%s", config.durian_name)
    me = await bot.get_me()
    logger.info("Bot started: @%s", me.username)


async def on_shutdown() -> None:
    await db.close()
    from durian_api import get_client as gc
    await gc().close()
    logger.info("Bot stopped.")


async def main() -> None:
    if not config.bot_token:
        logger.critical("BOT_TOKEN not set!")
        sys.exit(1)

    # تسجيل الـ middleware
    from middlewares import UserMiddleware
    bot.setup_middleware(UserMiddleware())

    # تسجيل كل الـ handlers
    from handlers import register_all
    register_all(bot)

    await on_startup()

    logger.info("Starting polling…")
    try:
        await bot.infinity_polling(allowed_updates=["message", "callback_query"])
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
