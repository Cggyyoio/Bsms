"""
handlers/user.py — User-facing handlers (telebot async)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Buy flow:
  menu:buy → service (TG / WA) → [WA: server] → country (+ price shown) → buy

SMS polling:
  • Wait 5s initial
  • Poll every 2s
  • Timeout: 300s

Cancel button:
  • Hidden first 60s
  • Shown after cancel_delay

Retry:
  • 1 retry with new number
  • Failed number → blacklist

Notifications:
  • Send to activation channel on SUCCESS only
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Tuple

from telebot.types import CallbackQuery, Message

from config import config
from database import db
from durian_api import get_client
from keyboards import (
    kb_active_order, kb_back, kb_charge_crypto,
    kb_countries, kb_language, kb_main_menu,
    kb_select_service, kb_wa_servers,
)
from strings import t
from countries_manager import countries_manager
from pricing import pricing
from notifier import get_notifier

logger = logging.getLogger(__name__)

# ── نظام حالة المستخدم (بديل FSM) ───────────────────────────────
# نستخدم dict بسيط بدلاً من FSM
_USER_STATES: dict = {}

def _set_state(uid: int, state: str, data: dict = None):
    _USER_STATES[uid] = {"state": state, "data": data or {}}

def _get_state(uid: int) -> dict:
    return _USER_STATES.get(uid, {})

def _clear_state(uid: int):
    _USER_STATES.pop(uid, None)


# ── Service labels & PIDs ─────────────────────────────────────────
_SVC_LABEL = {
    "tg":    "✈️ Telegram",
    "wa_s1": "💬 WhatsApp S1",
    "wa_s2": "💬 WhatsApp S2",
}


def _get_pid(service_key: str) -> str:
    return {
        "tg":    config.pid_telegram,
        "wa_s1": config.pid_whatsapp_s1,
        "wa_s2": config.pid_whatsapp_s2,
    }.get(service_key, config.pid_telegram)


# ── Helper: main menu ─────────────────────────────────────────────
async def send_main_menu(bot, chat_id: int, user, lang: str,
                         message_id: int = None) -> None:
    balance = await db.get_balance(user.id)
    text    = t("main_menu", lang, name=user.full_name, balance=balance)
    kb      = kb_main_menu(lang)
    if message_id:
        try:
            await bot.edit_message_text(text, chat_id, message_id,
                                        reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


# ── Helper: country info ──────────────────────────────────────────
def _country_info(country_code: str) -> Tuple[str, str]:
    c = countries_manager.get(country_code)
    if c:
        return c.get("flag", "🏳️"), c.get("name_ar", c.get("name_en", country_code.upper()))
    return "🏳️", country_code.upper()


# ── Helper: fetch + sort country list ────────────────────────────
async def _fetch_countries(service_key: str):
    pid        = _get_pid(service_key)
    client     = get_client()
    raw_counts = await client.get_country_counts(pid)
    all_c      = countries_manager.all()
    top_codes  = [r["country"] for r in await db.get_top_countries(10)]

    result = []
    seen   = set()
    for c in all_c:
        iso = c["code"]
        cnt = raw_counts.get(iso.lower(), 0)
        if cnt <= 0:
            continue
        result.append((iso, c.get("flag", "🏳️"), c.get("name_ar", c.get("name_en", iso)), cnt))
        seen.add(iso.lower())

    for iso, cnt in raw_counts.items():
        if iso not in seen and cnt > 0:
            result.append((iso, "🏳️", iso.upper(), cnt))

    def sort_key(row):
        code, _, _, cnt = row
        return (0 if code in top_codes else 1, -cnt)

    result.sort(key=sort_key)
    return result


# ══════════════════════════════════════════════════════════════════
#  تسجيل الـ handlers
# ══════════════════════════════════════════════════════════════════
def register(bot):
    """يُسجّل كل handlers الخاصة بالمستخدمين."""

    # ── /start ────────────────────────────────────────────────────
    @bot.message_handler(commands=["start"])
    async def cmd_start(message: Message):
        lang = await db.get_user_lang(message.from_user.id)
        user = await db.get_user(message.from_user.id)
        if user and user.get("lang"):
            await send_main_menu(bot, message.chat.id, message.from_user, user["lang"])
        else:
            await bot.send_message(
                message.chat.id,
                t("choose_language", "ar"),
                reply_markup=kb_language(),
            )
            _set_state(message.from_user.id, "lang_select")

    # ── Callback query router ─────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: True)
    async def route_callback(call: CallbackQuery):
        uid  = call.from_user.id
        lang = await db.get_user_lang(uid)
        data = call.data

        # ── Language ──────────────────────────────────────────────
        if data.startswith("lang:"):
            lang_code = data.split(":")[1]
            await db.set_user_lang(uid, lang_code)
            await bot.answer_callback_query(call.id, t("lang_set", lang_code))
            _clear_state(uid)
            await send_main_menu(bot, call.message.chat.id, call.from_user,
                                 lang_code, call.message.message_id)

        elif data == "menu:lang":
            await bot.edit_message_text(
                t("choose_language", "ar"), call.message.chat.id, call.message.message_id,
                reply_markup=kb_language(),
            )

        # ── Main nav ──────────────────────────────────────────────
        elif data == "menu:main":
            await send_main_menu(bot, call.message.chat.id, call.from_user,
                                 lang, call.message.message_id)

        elif data == "menu:help":
            await bot.edit_message_text(
                t("help_text", lang), call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang), parse_mode="HTML",
            )

        elif data == "menu:balance":
            balance = await db.get_balance(uid)
            await bot.edit_message_text(
                t("balance_info", lang, balance=balance),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang), parse_mode="HTML",
            )

        elif data == "menu:add_balance":
            bep20 = await db.get_setting("pay_bep20") == "1"
            trc20 = await db.get_setting("pay_trc20") == "1"
            if not bep20 and not trc20:
                await bot.edit_message_text(
                    t("no_payment_methods", lang),
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang), parse_mode="HTML",
                )
                return
            await bot.edit_message_text(
                t("add_balance_select", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_charge_crypto(bep20, trc20, lang), parse_mode="HTML",
            )

        # ── Crypto ────────────────────────────────────────────────
        elif data.startswith("crypto:"):
            from crypto_pay import CryptoPayHandler
            handler = CryptoPayHandler(db=db, bot=bot)
            await bot.answer_callback_query(call.id)
            await handler.show_pay_page(call.message.chat.id, uid, data.split(":")[1])

        elif data.startswith("crypto_sent:"):
            from crypto_pay import CryptoPayHandler
            handler = CryptoPayHandler(db=db, bot=bot)
            await bot.answer_callback_query(call.id)
            await handler.prompt_txid(call, data.split(":")[1])

        elif data.startswith("crypto_copy:"):
            from crypto_pay import CryptoPayHandler
            handler = CryptoPayHandler(db=db, bot=bot)
            await bot.answer_callback_query(call.id)
            await handler.handle_copy_address(call, data.split(":")[1])

        # ── Buy flow ──────────────────────────────────────────────
        elif data == "menu:buy":
            await bot.edit_message_text(
                t("select_service", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_select_service(lang), parse_mode="HTML",
            )

        elif data == "svc:tg":
            await bot.answer_callback_query(call.id, t("loading_countries", lang))
            countries = await _fetch_countries("tg")
            if not countries:
                await bot.edit_message_text(
                    t("no_countries", lang),
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang, "menu:buy"), parse_mode="HTML",
                )
                return
            await bot.edit_message_text(
                t("select_country_tg", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_countries(countries, 0, "tg", lang), parse_mode="HTML",
            )

        elif data == "svc:wa":
            await bot.edit_message_text(
                t("select_wa_server", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_wa_servers(lang), parse_mode="HTML",
            )

        elif data in ("wa:s1", "wa:s2"):
            service_key = "wa_s1" if data == "wa:s1" else "wa_s2"
            await bot.answer_callback_query(call.id, t("loading_countries", lang))
            countries = await _fetch_countries(service_key)
            if not countries:
                await bot.edit_message_text(
                    t("no_countries", lang),
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang, "svc:wa"), parse_mode="HTML",
                )
                return
            await bot.edit_message_text(
                t("select_country_wa", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_countries(countries, 0, service_key, lang), parse_mode="HTML",
            )

        elif data == "wa:refresh":
            await bot.answer_callback_query(call.id, "🔄")
            await bot.edit_message_text(
                t("select_wa_server", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_wa_servers(lang), parse_mode="HTML",
            )

        elif data.startswith("refresh_countries:"):
            service_key = data.split(":")[1]
            await bot.answer_callback_query(call.id, t("loading_countries", lang))
            countries = await _fetch_countries(service_key)
            if not countries:
                back = "menu:buy" if service_key == "tg" else "svc:wa"
                await bot.edit_message_text(
                    t("no_countries", lang),
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang, back), parse_mode="HTML",
                )
                return
            txt_key = "select_country_tg" if service_key == "tg" else "select_country_wa"
            await bot.edit_message_text(
                t(txt_key, lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_countries(countries, 0, service_key, lang), parse_mode="HTML",
            )

        elif data.startswith("cpage:"):
            parts       = data.split(":")
            service_key = parts[1]
            page        = int(parts[2])
            countries   = await _fetch_countries(service_key)
            txt_key     = "select_country_tg" if service_key == "tg" else "select_country_wa"
            await bot.edit_message_text(
                t(txt_key, lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_countries(countries, page, service_key, lang), parse_mode="HTML",
            )

        elif data == "noop":
            await bot.answer_callback_query(call.id)

        # ── Purchase ──────────────────────────────────────────────
        elif data.startswith("buy:"):
            parts       = data.split(":")
            service_key = parts[1]
            country     = parts[2]

            if await db.has_pending_order(uid):
                await bot.answer_callback_query(
                    call.id, t("already_has_order", lang), show_alert=True
                )
                return

            price   = await pricing.get_price(service_key, country)
            balance = await db.get_balance(uid)
            if balance < price:
                await bot.answer_callback_query(
                    call.id,
                    t("insufficient_balance", lang, needed=price, have=balance),
                    show_alert=True,
                )
                return

            flag, country_name = _country_info(country)
            svc_lbl = _SVC_LABEL.get(service_key, service_key)

            await bot.edit_message_text(
                t("buying_number", lang, service=svc_lbl, flag=flag, country=country_name),
                call.message.chat.id, call.message.message_id,
                parse_mode="HTML",
            )

            await db.update_balance(uid, -price)

            pid    = _get_pid(service_key)
            result = await _buy_with_retry(pid, country, uid, lang, bot,
                                           call.message.chat.id, call.message.message_id)
            if not result:
                await db.update_balance(uid, price)
                return

            number, order_id = result
            country_line = t("order_country_line", lang, flag=flag, country=country_name)
            msg_text = t(
                "order_active", lang,
                number=number, service=svc_lbl,
                country_line=country_line, price=price,
            )
            try:
                await bot.edit_message_text(
                    msg_text, call.message.chat.id, call.message.message_id,
                    reply_markup=kb_active_order(order_id, lang, show_cancel=False),
                    parse_mode="HTML",
                )
                msg_id = call.message.message_id
            except Exception:
                sent = await bot.send_message(
                    call.message.chat.id, msg_text,
                    reply_markup=kb_active_order(order_id, lang, show_cancel=False),
                    parse_mode="HTML",
                )
                msg_id = sent.message_id

            asyncio.create_task(_poll_sms(
                bot=bot, chat_id=uid, msg_id=msg_id,
                order_id=order_id, pid=pid, number=number,
                service_key=service_key, price=price, lang=lang,
                country_line=country_line, svc_lbl=svc_lbl,
                country_flag=flag, country_name=country_name, country_code=country,
            ))

        # ── Cancel order ──────────────────────────────────────────
        elif data.startswith("cancel_order:"):
            order_id = int(data.split(":")[1])
            order    = await db.get_order(order_id)

            if not order or order["user_id"] != uid:
                await bot.answer_callback_query(call.id, "❌", show_alert=True)
                return
            if order["status"] != "pending":
                await bot.answer_callback_query(
                    call.id, t("error_generic", lang), show_alert=True
                )
                return

            from datetime import datetime
            created = datetime.fromisoformat(order["created_at"])
            elapsed = (datetime.utcnow() - created).total_seconds()
            if elapsed < config.cancel_delay:
                remaining = int(config.cancel_delay - elapsed)
                await bot.answer_callback_query(
                    call.id, t("cancel_too_early", lang, remaining=remaining), show_alert=True
                )
                return

            client = get_client()
            await client.add_black(pid=order["pid"], number=order["number"])
            await client.pass_mobile(pid=order["pid"], number=order["number"])
            await db.update_order(order_id, "cancelled")
            if config.refund_enabled:
                await db.update_balance(uid, order["price"])

            try:
                await bot.edit_message_text(
                    t("order_cancelled", lang, order_id=order_id, refund=order["price"]),
                    call.message.chat.id, call.message.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                await bot.answer_callback_query(call.id, "❌ Cancelled", show_alert=True)

        # ── My Orders ─────────────────────────────────────────────
        elif data == "menu:orders":
            orders = await db.get_user_orders(uid, 15)
            if not orders:
                await bot.edit_message_text(
                    t("my_orders_empty", lang),
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang), parse_mode="HTML",
                )
                return
            icons = {"pending": "⏳", "completed": "✅", "cancelled": "❌"}
            lines = [t("my_orders_header", lang, count=len(orders))]
            for o in orders:
                icon      = icons.get(o["status"], "❓")
                num       = o.get("number", "—")
                code_part = f" 🔑<code>{o['sms_code']}</code>" if o.get("sms_code") else ""
                lines.append(
                    f"{icon} #{o['id']} | {o['service']} | "
                    f"<code>{num}</code>{code_part}"
                )
            await bot.edit_message_text(
                "\n".join(lines),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang), parse_mode="HTML",
            )

    # ── Incoming text ─────────────────────────────────────────────
    @bot.message_handler(func=lambda m: m.content_type == "text")
    async def handle_text(message: Message):
        uid   = message.from_user.id
        state = _get_state(uid)

        # حالة اختيار اللغة
        if state.get("state") == "lang_select":
            return  # يُعالج من الـ callback

        # TXID للكريبتو
        try:
            from crypto_pay import CryptoPayHandler
            handler = CryptoPayHandler(db=db, bot=bot)
            handled = await handler.handle_crypto_message(message)
            if handled:
                return
        except Exception:
            pass


# ── Buy with retry ────────────────────────────────────────────────
async def _buy_with_retry(
    pid: str, country: str,
    user_id: int, lang: str,
    bot, chat_id: int, msg_id: int,
    attempt: int = 1,
) -> Optional[Tuple[str, int]]:
    client = get_client()
    res    = await client.get_mobile(pid=pid, country=country, noblack=0)

    if res.ok:
        price    = await pricing.get_price(_pid_to_svc(pid), country)
        order_id = await db.create_order(
            user_id=user_id, service=_pid_to_svc(pid),
            pid=pid, country=country, number=res.number, price=price,
        )
        return res.number, order_id

    if res.code in (403, 406, 800, 802, 904):
        msg = t("buy_failed_balance", lang) if res.code == 403 else t("buy_failed_generic", lang)
        try:
            await bot.edit_message_text(msg, chat_id, msg_id, parse_mode="HTML")
        except Exception:
            await bot.send_message(chat_id, msg, parse_mode="HTML")
        return None

    if res.code == 906 or attempt >= 2:
        try:
            await bot.edit_message_text(
                t("buy_failed_no_numbers", lang), chat_id, msg_id, parse_mode="HTML"
            )
        except Exception:
            await bot.send_message(chat_id, t("buy_failed_no_numbers", lang), parse_mode="HTML")
        return None

    try:
        await bot.edit_message_text(
            t("retrying_number", lang), chat_id, msg_id, parse_mode="HTML"
        )
    except Exception:
        pass
    await asyncio.sleep(2)
    return await _buy_with_retry(pid, country, user_id, lang, bot, chat_id, msg_id, attempt=2)


def _pid_to_svc(pid: str) -> str:
    if pid == config.pid_telegram:
        return "tg"
    if pid == config.pid_whatsapp_s1:
        return "wa_s1"
    if pid == config.pid_whatsapp_s2:
        return "wa_s2"
    return "tg"


# ── SMS Poller ────────────────────────────────────────────────────
async def _poll_sms(
    bot, chat_id: int, msg_id: int,
    order_id: int, pid: str, number: str,
    service_key: str, price: float, lang: str,
    country_line: str, svc_lbl: str,
    country_flag: str, country_name: str, country_code: str,
) -> None:
    client       = get_client()
    start_time   = time.time()
    cancel_shown = False

    await asyncio.sleep(5)

    while True:
        elapsed = time.time() - start_time

        if elapsed >= config.otp_timeout:
            await _handle_timeout(bot, chat_id, msg_id, order_id, pid, number, price, lang)
            return

        sms = await client.get_msg(pid=pid, pn=number)

        if sms.ok and sms.code:
            await db.update_order(order_id, "completed", sms_code=sms.code, sms_text=sms.message)
            success_text = t("sms_received", lang, number=number,
                             code=sms.code, text=sms.message)
            try:
                await bot.edit_message_text(
                    success_text, chat_id, msg_id,
                    parse_mode="HTML",
                )
            except Exception:
                await bot.send_message(chat_id, success_text, parse_mode="HTML")

            notifier = get_notifier()
            if notifier:
                await notifier.notify_success(
                    service_key=service_key, number=number,
                    country_code=country_code, country_flag=country_flag,
                    country_name=country_name, price=price,
                )
            return

        if sms.status == 405:
            await client.add_black(pid=pid, number=number)
            await _handle_timeout(bot, chat_id, msg_id, order_id, pid, number, price, lang)
            return

        if not cancel_shown and elapsed >= config.cancel_delay:
            cancel_shown = True
            try:
                await bot.edit_message_reply_markup(
                    chat_id, msg_id,
                    reply_markup=kb_active_order(order_id, lang, show_cancel=True),
                )
            except Exception:
                pass

        await asyncio.sleep(2)


async def _handle_timeout(
    bot, chat_id: int, msg_id: int,
    order_id: int, pid: str, number: str, price: float, lang: str,
) -> None:
    client = get_client()
    await client.add_black(pid=pid, number=number)
    await client.pass_mobile(pid=pid, number=number)
    await db.update_order(order_id, "cancelled")
    if config.refund_enabled:
        await db.update_balance(chat_id, price)
    text = t("order_timeout", lang, order_id=order_id, refund=price)
    try:
        await bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML")
    except Exception:
        await bot.send_message(chat_id, text, parse_mode="HTML")
