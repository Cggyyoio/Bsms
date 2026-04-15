"""middlewares.py — User registration, lang injection, ban check (telebot)"""
from __future__ import annotations

from telebot.asyncio_handler_backends import BaseMiddleware, CancelUpdate
from telebot.types import Message, CallbackQuery

from database import db
from strings import t


class UserMiddleware(BaseMiddleware):
    """
    يُسجّل المستخدم، يحقن lang، ويتحقق من الحظر.
    """
    update_types = ["message", "callback_query"]

    async def pre_process(self, update: Message | CallbackQuery, data: dict):
        if isinstance(update, Message):
            user = update.from_user
        elif isinstance(update, CallbackQuery):
            user = update.from_user
        else:
            return

        if not user:
            return

        await db.upsert_user(user.id, user.username, user.full_name)
        lang = await db.get_user_lang(user.id)
        data["lang"] = lang

        if await db.is_banned(user.id):
            from main import bot
            try:
                if isinstance(update, Message):
                    await bot.send_message(update.chat.id, t("banned", lang))
                elif isinstance(update, CallbackQuery):
                    await bot.answer_callback_query(update.id, t("banned", lang), show_alert=True)
            except Exception:
                pass
            return CancelUpdate()

    async def post_process(self, update, data, exception):
        pass
