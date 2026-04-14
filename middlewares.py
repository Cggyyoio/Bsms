"""middlewares.py — User registration, lang injection, ban check"""
from __future__ import annotations
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from database import db
from strings import t


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Update):
            if event.message:
                user = event.message.from_user
            elif event.callback_query:
                user = event.callback_query.from_user

        if user is None:
            return await handler(event, data)

        await db.upsert_user(user.id, user.username, user.full_name)
        lang = await db.get_user_lang(user.id)
        data["lang"] = lang

        if await db.is_banned(user.id):
            try:
                if isinstance(event, Update) and event.message:
                    await event.message.answer(t("banned", lang))
                elif isinstance(event, Update) and event.callback_query:
                    await event.callback_query.answer(t("banned", lang), show_alert=True)
            except Exception:
                pass
            return

        return await handler(event, data)
