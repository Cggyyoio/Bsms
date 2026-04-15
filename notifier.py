"""
notifier.py — قناة إشعارات التفعيل (telebot)
• ترسل إشعاراً عند نجاح العملية فقط
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def _mask_number(number: str) -> str:
    n = number.replace(" ", "")
    if len(n) <= 7:
        return n
    prefix = n[:5]
    suffix = n[-4:]
    stars  = "*" * (len(n) - len(prefix) - len(suffix))
    return f"{prefix}{stars}{suffix}"


_SVC_LABELS = {
    "tg":    "✈️ Telegram",
    "wa_s1": "💬 WhatsApp Server 1",
    "wa_s2": "💬 WhatsApp Server 2",
}


class ActivationNotifier:
    def __init__(self, bot, channel_id: Optional[str], channel_link: Optional[str]):
        self.bot          = bot
        self.channel_id   = channel_id
        self.channel_link = channel_link

    def _is_configured(self) -> bool:
        return bool(self.channel_id and self.channel_id.strip())

    def _build_keyboard(self) -> Optional[InlineKeyboardMarkup]:
        if not self.channel_link:
            return None
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton(text="🟢 أونلاين", url=self.channel_link))
        return kb

    def _build_message(self, service_key, number, country_flag, country_name, price) -> str:
        svc_label  = _SVC_LABELS.get(service_key, service_key)
        masked_num = _mask_number(number)
        local_time = datetime.now(timezone.utc) + timedelta(hours=3)
        time_str   = local_time.strftime("%H:%M:%S")
        date_str   = local_time.strftime("%Y-%m-%d")
        return (
            f"✅ <b>تفعيل ناجح</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛎 الخدمة: <b>{svc_label}</b>\n"
            f"🌍 الدولة: {country_flag} <b>{country_name}</b>\n"
            f"📞 الرقم: <code>{masked_num}</code>\n"
            f"💰 السعر: <code>${price:.2f}</code>\n"
            f"⏱️ الوقت: <code>{time_str}</code>\n"
            f"📅 التاريخ: <code>{date_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

    async def notify_success(
        self, service_key, number, country_code, country_flag, country_name, price
    ) -> None:
        if not self._is_configured():
            return
        try:
            text = self._build_message(service_key, number, country_flag, country_name, price)
            kb   = self._build_keyboard()
            await self.bot.send_message(
                self.channel_id, text, reply_markup=kb, parse_mode="HTML"
            )
            logger.info("[Notifier] Sent: %s %s", service_key, _mask_number(number))
        except Exception as exc:
            logger.warning("[Notifier] Failed: %s", exc)


# ── Singleton ──────────────────────────────────────────────────────
_notifier: Optional[ActivationNotifier] = None


def init_notifier(bot, channel_id: str, channel_link: str) -> None:
    global _notifier
    _notifier = ActivationNotifier(bot, channel_id, channel_link)
    logger.info("[Notifier] channel_id=%s", channel_id or "NOT SET")


def get_notifier() -> Optional[ActivationNotifier]:
    return _notifier
