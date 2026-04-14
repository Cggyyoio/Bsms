"""
handlers/user.py — User-facing handlers (v4)
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

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

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
router = Router()

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


# ── FSM ───────────────────────────────────────────────────────────
class UserState(StatesGroup):
    lang_select = State()


# ── Helper: main menu ─────────────────────────────────────────────
async def send_main_menu(target: Message | CallbackQuery, lang: str) -> None:
    user    = target.from_user
    balance = await db.get_balance(user.id)
    text    = t("main_menu", lang, name=user.full_name, balance=balance)
    kb      = kb_main_menu(lang)
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


# ── Helper: country info ──────────────────────────────────────────
def _country_info(country_code: str) -> Tuple[str, str]:
    """يرجع (flag, name_ar)."""
    c = countries_manager.get(country_code)
    if c:
        return c.get("flag", "🏳️"), c.get("name_ar", c.get("name_en", country_code.upper()))
    return "🏳️", country_code.upper()


# ── Helper: fetch + sort country list ────────────────────────────
async def _fetch_countries(service_key: str):
    """
    يجلب الدول من Durian getCountryPhoneNum ويدمجها مع countries.json.
    يرجع list of (code, flag, name, count).
    """
    pid         = _get_pid(service_key)
    client      = get_client()
    raw_counts  = await client.get_country_counts(pid)
    all_c       = countries_manager.all()
    top_codes   = [r["country"] for r in await db.get_top_countries(10)]

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
#  /start
# ══════════════════════════════════════════════════════════════════
@router.message(CommandStart())
async def cmd_start(message: Message, lang: str, state: FSMContext) -> None:
    user = await db.get_user(message.from_user.id)
    if user and user.get("lang"):
        await send_main_menu(message, user["lang"])
    else:
        await message.answer(t("choose_language", "ar"), reply_markup=kb_language())
        await state.set_state(UserState.lang_select)


# ── Language ──────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("lang:"))
async def cb_set_lang(call: CallbackQuery, state: FSMContext) -> None:
    lang = call.data.split(":")[1]
    await db.set_user_lang(call.from_user.id, lang)
    await call.answer(t("lang_set", lang))
    await state.clear()
    await send_main_menu(call, lang)


@router.callback_query(F.data == "menu:lang")
async def cb_change_lang(call: CallbackQuery) -> None:
    await call.message.edit_text(t("choose_language", "ar"), reply_markup=kb_language())


# ── Main menu nav ─────────────────────────────────────────────────
@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, lang: str) -> None:
    await send_main_menu(call, lang)


@router.callback_query(F.data == "menu:help")
async def cb_help(call: CallbackQuery, lang: str) -> None:
    await call.message.edit_text(t("help_text", lang), reply_markup=kb_back(lang), parse_mode="HTML")


@router.callback_query(F.data == "menu:balance")
async def cb_balance(call: CallbackQuery, lang: str) -> None:
    balance = await db.get_balance(call.from_user.id)
    await call.message.edit_text(
        t("balance_info", lang, balance=balance),
        reply_markup=kb_back(lang), parse_mode="HTML",
    )


@router.callback_query(F.data == "menu:add_balance")
async def cb_add_balance(call: CallbackQuery, lang: str) -> None:
    bep20 = await db.get_setting("pay_bep20") == "1"
    trc20 = await db.get_setting("pay_trc20") == "1"
    if not bep20 and not trc20:
        await call.message.edit_text(
            t("no_payment_methods", lang), reply_markup=kb_back(lang), parse_mode="HTML"
        )
        return
    await call.message.edit_text(
        t("add_balance_select", lang),
        reply_markup=kb_charge_crypto(bep20, trc20, lang), parse_mode="HTML",
    )


# ── Crypto deposit ────────────────────────────────────────────────
@router.callback_query(F.data.startswith("crypto:"))
async def cb_crypto_net(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    from crypto_pay import CryptoPayHandler
    handler = CryptoPayHandler(db=db, bot=call.bot)
    await call.answer()
    await handler.show_pay_page(call.message.chat.id, call.from_user.id, call.data.split(":")[1])


@router.callback_query(F.data.startswith("crypto_sent:"))
async def cb_crypto_sent(call: CallbackQuery, lang: str) -> None:
    from crypto_pay import CryptoPayHandler
    handler = CryptoPayHandler(db=db, bot=call.bot)
    await call.answer()
    await handler.prompt_txid(call, call.data.split(":")[1])


@router.callback_query(F.data.startswith("crypto_copy:"))
async def cb_crypto_copy(call: CallbackQuery, lang: str) -> None:
    from crypto_pay import CryptoPayHandler
    handler = CryptoPayHandler(db=db, bot=call.bot)
    await call.answer()
    await handler.handle_copy_address(call, call.data.split(":")[1])


# ══════════════════════════════════════════════════════════════════
#  BUY FLOW
# ══════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "menu:buy")
async def cb_buy(call: CallbackQuery, lang: str) -> None:
    await call.message.edit_text(
        t("select_service", lang),
        reply_markup=kb_select_service(lang), parse_mode="HTML",
    )


# ── Telegram → اختيار دولة ───────────────────────────────────────
@router.callback_query(F.data == "svc:tg")
async def cb_svc_tg(call: CallbackQuery, lang: str) -> None:
    await call.answer(t("loading_countries", lang))
    countries = await _fetch_countries("tg")
    if not countries:
        await call.message.edit_text(
            t("no_countries", lang), reply_markup=kb_back(lang, "menu:buy"), parse_mode="HTML"
        )
        return
    await call.message.edit_text(
        t("select_country_tg", lang),
        reply_markup=kb_countries(countries, 0, "tg", lang), parse_mode="HTML",
    )


# ── WhatsApp → اختيار سيرفر ──────────────────────────────────────
@router.callback_query(F.data == "svc:wa")
async def cb_svc_wa(call: CallbackQuery, lang: str) -> None:
    await call.message.edit_text(
        t("select_wa_server", lang),
        reply_markup=kb_wa_servers(lang), parse_mode="HTML",
    )


# ── WA server → اختيار دولة ──────────────────────────────────────
@router.callback_query(F.data.in_({"wa:s1", "wa:s2"}))
async def cb_wa_server(call: CallbackQuery, lang: str) -> None:
    service_key = "wa_s1" if call.data == "wa:s1" else "wa_s2"
    await call.answer(t("loading_countries", lang))
    countries = await _fetch_countries(service_key)
    if not countries:
        await call.message.edit_text(
            t("no_countries", lang), reply_markup=kb_back(lang, "svc:wa"), parse_mode="HTML"
        )
        return
    await call.message.edit_text(
        t("select_country_wa", lang),
        reply_markup=kb_countries(countries, 0, service_key, lang), parse_mode="HTML",
    )


# ── Refresh ───────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("refresh_countries:"))
async def cb_refresh_countries(call: CallbackQuery, lang: str) -> None:
    service_key = call.data.split(":")[1]
    await call.answer(t("loading_countries", lang))
    countries = await _fetch_countries(service_key)
    if not countries:
        back = "menu:buy" if service_key == "tg" else "svc:wa"
        await call.message.edit_text(
            t("no_countries", lang), reply_markup=kb_back(lang, back), parse_mode="HTML"
        )
        return
    txt_key = "select_country_tg" if service_key == "tg" else "select_country_wa"
    await call.message.edit_text(
        t(txt_key, lang),
        reply_markup=kb_countries(countries, 0, service_key, lang), parse_mode="HTML",
    )


@router.callback_query(F.data == "wa:refresh")
async def cb_wa_refresh(call: CallbackQuery, lang: str) -> None:
    await call.answer("🔄")
    await call.message.edit_text(
        t("select_wa_server", lang), reply_markup=kb_wa_servers(lang), parse_mode="HTML"
    )


# ── Pagination ────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("cpage:"))
async def cb_cpage(call: CallbackQuery, lang: str) -> None:
    parts       = call.data.split(":")
    service_key = parts[1]
    page        = int(parts[2])
    countries   = await _fetch_countries(service_key)
    txt_key     = "select_country_tg" if service_key == "tg" else "select_country_wa"
    await call.message.edit_text(
        t(txt_key, lang),
        reply_markup=kb_countries(countries, page, service_key, lang), parse_mode="HTML",
    )


@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# ══════════════════════════════════════════════════════════════════
#  PURCHASE — اختيار الدولة → عرض السعر → تأكيد الشراء
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("buy:"))
async def cb_buy_number(call: CallbackQuery, lang: str) -> None:
    """buy:{service_key}:{country_code}"""
    parts       = call.data.split(":")
    service_key = parts[1]
    country     = parts[2]
    user_id     = call.from_user.id

    # ── منع الطلب المزدوج ───────────────────
    if await db.has_pending_order(user_id):
        await call.answer(t("already_has_order", lang), show_alert=True)
        return

    # ── الحصول على السعر (دولة خاصة أو موحد) ──
    price = await pricing.get_price(service_key, country)

    # ── فحص الرصيد ──────────────────────────
    balance = await db.get_balance(user_id)
    if balance < price:
        await call.answer(
            t("insufficient_balance", lang, needed=price, have=balance),
            show_alert=True,
        )
        return

    # ── معلومات الدولة ───────────────────────
    flag, country_name = _country_info(country)
    svc_lbl = _SVC_LABEL.get(service_key, service_key)

    # ── رسالة "جارٍ الشراء" ──────────────────
    await call.message.edit_text(
        t("buying_number", lang, service=svc_lbl, flag=flag, country=country_name),
        parse_mode="HTML",
    )

    # ── خصم الرصيد مؤقتاً ───────────────────
    await db.update_balance(user_id, -price)

    # ── محاولة شراء الرقم ───────────────────
    pid    = _get_pid(service_key)
    result = await _buy_with_retry(pid, country, user_id, lang, call)
    if not result:
        await db.update_balance(user_id, price)   # استرداد
        return

    number, order_id = result

    # ── إنشاء رسالة الطلب النشط ─────────────
    country_line = t("order_country_line", lang, flag=flag, country=country_name)
    msg_text = t(
        "order_active", lang,
        number=number, service=svc_lbl,
        country_line=country_line, price=price,
    )
    try:
        sent = await call.message.edit_text(
            msg_text,
            reply_markup=kb_active_order(order_id, lang, show_cancel=False),
            parse_mode="HTML",
        )
        msg_id = sent.message_id
    except TelegramBadRequest:
        sent = await call.message.answer(
            msg_text,
            reply_markup=kb_active_order(order_id, lang, show_cancel=False),
            parse_mode="HTML",
        )
        msg_id = sent.message_id

    # ── بدء Poller في الخلفية ────────────────
    asyncio.create_task(_poll_sms(
        bot          = call.bot,
        chat_id      = user_id,
        msg_id       = msg_id,
        order_id     = order_id,
        pid          = pid,
        number       = number,
        service_key  = service_key,
        price        = price,
        lang         = lang,
        country_line = country_line,
        svc_lbl      = svc_lbl,
        country_flag = flag,
        country_name = country_name,
        country_code = country,
    ))


async def _buy_with_retry(
    pid: str, country: str,
    user_id: int, lang: str, call: CallbackQuery,
    attempt: int = 1,
) -> Optional[Tuple[str, int]]:
    """
    يشتري رقماً. عند الفشل يحاول مرة واحدة فقط.
    يرجع (number, order_id) أو None.
    """
    client = get_client()
    res    = await client.get_mobile(pid=pid, country=country, noblack=0)

    if res.ok:
        price    = await pricing.get_price(_pid_to_svc(pid), country)
        order_id = await db.create_order(
            user_id=user_id, service=_pid_to_svc(pid),
            pid=pid, country=country, number=res.number, price=price,
        )
        return res.number, order_id

    # أخطاء غير قابلة للتكرار
    if res.code in (403, 406, 800, 802, 904):
        msg = t("buy_failed_balance", lang) if res.code == 403 else t("buy_failed_generic", lang)
        try:
            await call.message.edit_text(msg, parse_mode="HTML")
        except Exception:
            await call.message.answer(msg, parse_mode="HTML")
        return None

    if res.code == 906 or attempt >= 2:
        try:
            await call.message.edit_text(t("buy_failed_no_numbers", lang), parse_mode="HTML")
        except Exception:
            await call.message.answer(t("buy_failed_no_numbers", lang), parse_mode="HTML")
        return None

    # محاولة ثانية
    try:
        await call.message.edit_text(t("retrying_number", lang), parse_mode="HTML")
    except Exception:
        pass
    await asyncio.sleep(2)
    return await _buy_with_retry(pid, country, user_id, lang, call, attempt=2)


def _pid_to_svc(pid: str) -> str:
    """يحول PID إلى service_key."""
    if pid == config.pid_telegram:
        return "tg"
    if pid == config.pid_whatsapp_s1:
        return "wa_s1"
    if pid == config.pid_whatsapp_s2:
        return "wa_s2"
    return "tg"


# ══════════════════════════════════════════════════════════════════
#  SMS POLLER
# ══════════════════════════════════════════════════════════════════
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

    # انتظار 5 ثوانٍ أولي (توصية Durian)
    await asyncio.sleep(5)

    while True:
        elapsed = time.time() - start_time

        # ── Timeout ─────────────────────────────
        if elapsed >= config.otp_timeout:
            await _handle_timeout(bot, chat_id, msg_id, order_id, pid, number, price, lang)
            return

        # ── استطلاع الكود ───────────────────────
        sms = await client.get_msg(pid=pid, pn=number)

        if sms.ok and sms.code:
            # ✅ نجاح
            await db.update_order(order_id, "completed", sms_code=sms.code, sms_text=sms.message)
            success_text = t("sms_received", lang, number=number, code=sms.code, text=sms.message)
            try:
                await bot.edit_message_text(
                    success_text, chat_id=chat_id, message_id=msg_id,
                    parse_mode="HTML", reply_markup=None,
                )
            except Exception:
                await bot.send_message(chat_id, success_text, parse_mode="HTML")

            # ── إشعار القناة ────────────────────
            notifier = get_notifier()
            if notifier:
                await notifier.notify_success(
                    service_key  = service_key,
                    number       = number,
                    country_code = country_code,
                    country_flag = country_flag,
                    country_name = country_name,
                    price        = price,
                )
            return

        if sms.status == 405:
            # فشل نهائي من API
            await client.add_black(pid=pid, number=number)
            await _handle_timeout(bot, chat_id, msg_id, order_id, pid, number, price, lang)
            return

        # ── إظهار زر الإلغاء بعد cancel_delay ──
        if not cancel_shown and elapsed >= config.cancel_delay:
            cancel_shown = True
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=msg_id,
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
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=msg_id,
            parse_mode="HTML", reply_markup=None,
        )
    except Exception:
        await bot.send_message(chat_id, text, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════
#  CANCEL ORDER
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("cancel_order:"))
async def cb_cancel_order(call: CallbackQuery, lang: str) -> None:
    order_id = int(call.data.split(":")[1])
    order    = await db.get_order(order_id)

    if not order or order["user_id"] != call.from_user.id:
        await call.answer("❌", show_alert=True)
        return
    if order["status"] != "pending":
        await call.answer(t("error_generic", lang), show_alert=True)
        return

    from datetime import datetime
    created = datetime.fromisoformat(order["created_at"])
    elapsed = (datetime.utcnow() - created).total_seconds()
    if elapsed < config.cancel_delay:
        remaining = int(config.cancel_delay - elapsed)
        await call.answer(t("cancel_too_early", lang, remaining=remaining), show_alert=True)
        return

    client = get_client()
    await client.add_black(pid=order["pid"], number=order["number"])
    await client.pass_mobile(pid=order["pid"], number=order["number"])
    await db.update_order(order_id, "cancelled")
    if config.refund_enabled:
        await db.update_balance(call.from_user.id, order["price"])

    try:
        await call.message.edit_text(
            t("order_cancelled", lang, order_id=order_id, refund=order["price"]),
            parse_mode="HTML", reply_markup=None,
        )
    except Exception:
        await call.answer("❌ Cancelled", show_alert=True)


# ══════════════════════════════════════════════════════════════════
#  MY ORDERS
# ══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:orders")
async def cb_my_orders(call: CallbackQuery, lang: str) -> None:
    orders = await db.get_user_orders(call.from_user.id, 15)
    if not orders:
        await call.message.edit_text(
            t("my_orders_empty", lang), reply_markup=kb_back(lang), parse_mode="HTML"
        )
        return

    icons = {"pending": "⏳", "completed": "✅", "cancelled": "❌"}
    lines = [t("my_orders_header", lang, count=len(orders))]
    for o in orders:
        icon = icons.get(o["status"], "❓")
        num  = o.get("number", "—")
        code_part = f" 🔑<code>{o['sms_code']}</code>" if o.get("sms_code") else ""
        lines.append(
            f"{icon} #{o['id']} | {o['service']} | "
            f"<code>{num}</code>{code_part}"
        )
    await call.message.edit_text(
        "\n".join(lines), reply_markup=kb_back(lang), parse_mode="HTML"
    )


# ── Incoming text (TXID for crypto) ──────────────────────────────
@router.message(F.text)
async def handle_text(message: Message, lang: str) -> None:
    try:
        from crypto_pay import CryptoPayHandler
        handler = CryptoPayHandler(db=db, bot=message.bot)
        await handler.handle_crypto_message(message)
    except ImportError:
        pass
