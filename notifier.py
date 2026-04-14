"""
notifier.py — قناة إشعارات التفعيل
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• ترسل إشعاراً عند نجاح العملية فقط
• محتوى الرسالة: الدولة، الرقم (مخفي جزئياً)، الخدمة، الوقت
• تضيف زر "🟢 أونلاين" برابط القناة
• لا تُرسل أي شيء عند الفشل أو الإلغاء
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)


def _mask_number(number: str) -> str:
    """يخفي الجزء الأوسط من الرقم: +9665****1234"""
    n = number.replace(" ", "")
    if len(n) <= 7:
        return n
    prefix = n[:5]          # مثل: +9665
    suffix = n[-4:]         # آخر 4 أرقام
    stars  = "*" * (len(n) - len(prefix) - len(suffix))
    return f"{prefix}{stars}{suffix}"


_SVC_LABELS = {
    "tg":    "✈️ Telegram",
    "wa_s1": "💬 WhatsApp Server 1",
    "wa_s2": "💬 WhatsApp Server 2",
}

_SVC_EMOJI = {
    "tg":    "✈️",
    "wa_s1": "💬",
    "wa_s2": "💬",
}


class ActivationNotifier:
    """
    مسؤول عن إرسال إشعارات القناة عند نجاح العملية.
    """

    def __init__(self, bot: Bot, channel_id: Optional[str], channel_link: Optional[str]):
        self.bot          = bot
        self.channel_id   = channel_id
        self.channel_link = channel_link

    def _is_configured(self) -> bool:
        return bool(self.channel_id and self.channel_id.strip())

    def _build_keyboard(self) -> Optional[InlineKeyboardMarkup]:
        """يبني زر 🟢 أونلاين برابط القناة."""
        if not self.channel_link:
            return None
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(
            text="🟢 أونلاين",
            url=self.channel_link,
        ))
        return b.as_markup()

    def _build_message(
        self,
        service_key: str,
        number: str,
        country_flag: str,
        country_name: str,
        price: float,
    ) -> str:
        """يبني نص رسالة القناة."""
        svc_label  = _SVC_LABELS.get(service_key, service_key)
        masked_num = _mask_number(number)
        now_utc    = datetime.now(timezone.utc)
        # توقيت +3 (السعودية / مصر / تركيا)
        local_time = now_utc + timedelta(hours=3)
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
        self,
        service_key: str,
        number: str,
        country_code: str,
        country_flag: str,
        country_name: str,
        price: float,
    ) -> None:
        """
        يرسل إشعار النجاح للقناة.
        يتجاهل الأخطاء بصمت حتى لا يؤثر على تجربة المستخدم.
        """
        if not self._is_configured():
            return

        try:
            text = self._build_message(
                service_key=service_key,
                number=number,
                country_flag=country_flag,
                country_name=country_name,
                price=price,
            )
            kb = self._build_keyboard()

            await self.bot.send_message(
                chat_id     = self.channel_id,
                text        = text,
                reply_markup= kb,
                parse_mode  = "HTML",
            )
            logger.info("[Notifier] Sent to channel: %s %s", service_key, _mask_number(number))
        except Exception as exc:
            logger.warning("[Notifier] Failed to send channel notification: %s", exc)


# ── Factory (يُنشأ في main.py بعد تحميل الإعدادات) ──────────────
_notifier: Optional[ActivationNotifier] = None


def init_notifier(bot: Bot, channel_id: str, channel_link: str) -> None:
    global _notifier
    _notifier = ActivationNotifier(bot, channel_id, channel_link)
    logger.info("[Notifier] Initialised with channel_id=%s", channel_id or "NOT SET")


def get_notifier() -> Optional[ActivationNotifier]:
    return _notifier
