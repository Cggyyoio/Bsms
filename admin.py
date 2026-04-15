"""
handlers/admin.py — Admin panel (telebot async)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Commands:
  /admin   — لوحة الإدارة الرئيسية
  /stats   — إحصائيات سريعة
  /backup  — نسخ احتياطي من DB

Features:
  • إحصائيات + إدارة مستخدمين + تسعير
  • قناة إشعارات + Durian credentials
  • إعدادات الدفع + اختبار API
  • نسخ + استعادة DB
"""
from __future__ import annotations

import asyncio
import logging

from telebot.types import CallbackQuery, Message

from config import config
from database import db
from durian_api import get_client, reload_client
from keyboards import (
    kb_admin, kb_admin_crypto, kb_admin_user, kb_back,
    kb_durian, kb_notif, kb_pricing, kb_country_prices,
)
from pricing import pricing
from strings import t

logger = logging.getLogger(__name__)


def is_admin(uid: int) -> bool:
    return config.is_admin(uid)


# ── نظام حالة الأدمن ─────────────────────────────────────────────
_ADMIN_STATES: dict = {}

def _set_state(uid: int, state: str, data: dict = None):
    _ADMIN_STATES[uid] = {"state": state, "data": data or {}}

def _get_state(uid: int) -> dict:
    return _ADMIN_STATES.get(uid, {})

def _clear_state(uid: int):
    _ADMIN_STATES.pop(uid, None)


_SVC_NAMES = {
    "tg":    "✈️ Telegram",
    "wa_s1": "💬 WhatsApp Server 1",
    "wa_s2": "💬 WhatsApp Server 2",
}


# ── Build stats text ──────────────────────────────────────────────
async def _build_stats(lang: str) -> str:
    client = get_client()
    bal    = await client.get_balance()
    return t("admin_panel", lang,
        orders_today = await db.get_today_orders(),
        profit_today = await db.get_today_profit(),
        users        = await db.count_users(),
        orders_total = await db.count_orders(),
        completed    = await db.count_completed(),
        profit_total = await db.get_total_profit(),
        top_service  = await db.get_top_service(),
        top_country  = await db.get_top_country(),
        balance      = bal,
    )


async def _show_panel(bot, target: Message | CallbackQuery, lang: str) -> None:
    text = await _build_stats(lang)
    kb   = kb_admin(lang)
    if isinstance(target, CallbackQuery):
        try:
            await bot.edit_message_text(
                text, target.message.chat.id, target.message.message_id,
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            await bot.send_message(target.message.chat.id, text,
                                   reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_message(target.chat.id, text, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════
#  تسجيل الـ handlers
# ══════════════════════════════════════════════════════════════════
def register(bot):
    """يُسجّل كل handlers الخاصة بالأدمن."""

    # ── /admin ────────────────────────────────────────────────────
    @bot.message_handler(commands=["admin"])
    async def cmd_admin(message: Message):
        if not is_admin(message.from_user.id):
            return
        lang = await db.get_user_lang(message.from_user.id)
        await _show_panel(bot, message, lang)

    # ── /stats ────────────────────────────────────────────────────
    @bot.message_handler(commands=["stats"])
    async def cmd_stats(message: Message):
        if not is_admin(message.from_user.id):
            return
        lang = await db.get_user_lang(message.from_user.id)
        await bot.send_message(message.chat.id, await _build_stats(lang), parse_mode="HTML")

    # ── /backup ───────────────────────────────────────────────────
    @bot.message_handler(commands=["backup"])
    async def cmd_backup(message: Message):
        if not is_admin(message.from_user.id):
            return
        await _send_backup(bot, message.chat.id)

    # ── /restore ──────────────────────────────────────────────────
    @bot.message_handler(commands=["restore"])
    async def cmd_restore(message: Message):
        if not is_admin(message.from_user.id):
            return
        uid = message.from_user.id
        await bot.send_message(
            message.chat.id,
            "⚠️ <b>استعادة قاعدة البيانات</b>\n\n"
            "أرسل ملف <code>.db</code> الذي تريد استعادته.\n"
            "<b>تحذير: سيتم استبدال قاعدة البيانات الحالية!</b>",
            parse_mode="HTML",
        )
        _set_state(uid, "restore_db")

    # ── Callback router ───────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data.startswith("admin:") or
                                 c.data.startswith("admu:") or
                                 c.data.startswith("durian:") or
                                 c.data.startswith("price:") or
                                 c.data.startswith("notif:") or
                                 c.data.startswith("crypto_adm:") or
                                 c.data == "noop")
    async def route_admin_callback(call: CallbackQuery):
        uid  = call.from_user.id
        if not is_admin(uid) and not call.data == "noop":
            return
        lang = await db.get_user_lang(uid)
        data = call.data

        # noop
        if data == "noop":
            await bot.answer_callback_query(call.id)
            return

        # ── Panel ─────────────────────────────────────────────────
        if data == "admin:panel":
            await _show_panel(bot, call, lang)

        elif data == "admin:stats":
            await bot.edit_message_text(
                await _build_stats(lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_admin(lang), parse_mode="HTML",
            )
            await bot.answer_callback_query(call.id, "✅")

        # ── Margin ────────────────────────────────────────────────
        elif data == "admin:margin":
            margin = await db.get_setting("profit_margin", "30")
            await bot.edit_message_text(
                f"📈 <b>الهامش الحالي: <code>{margin}%</code></b>\n\nأرسل النسبة الجديدة:",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )
            _set_state(uid, "set_margin")

        # ── Users ─────────────────────────────────────────────────
        elif data == "admin:users":
            await bot.edit_message_text(
                t("admin_search_user", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )
            _set_state(uid, "search_user")

        elif data.startswith("admu:add:"):
            target_uid = int(data.split(":")[2])
            await bot.edit_message_text(
                t("admin_enter_amount", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )
            _set_state(uid, "user_add_bal", {"target_uid": target_uid})

        elif data.startswith("admu:deduct:"):
            target_uid = int(data.split(":")[2])
            await bot.edit_message_text(
                t("admin_enter_amount", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )
            _set_state(uid, "user_deduct_bal", {"target_uid": target_uid})

        elif data.startswith("admu:ban:"):
            target_uid = int(data.split(":")[2])
            await db.set_ban(target_uid, True)
            await bot.edit_message_text(
                t("admin_user_banned", lang, uid=target_uid),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )

        elif data.startswith("admu:unban:"):
            target_uid = int(data.split(":")[2])
            await db.set_ban(target_uid, False)
            await bot.edit_message_text(
                t("admin_user_unbanned", lang, uid=target_uid),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )

        # ── Broadcast ─────────────────────────────────────────────
        elif data == "admin:broadcast":
            await bot.edit_message_text(
                t("admin_broadcast_prompt", lang),
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
            )
            _set_state(uid, "broadcast")

        # ── Durian ───────────────────────────────────────────────
        elif data == "admin:durian":
            name    = await db.get_setting("durian_name", config.durian_name)
            key     = await db.get_setting("durian_api_key", config.durian_api_key)
            pid_tg  = await db.get_setting("pid_tg",   config.pid_telegram)
            pid_wa1 = await db.get_setting("pid_wa_s1", config.pid_whatsapp_s1)
            pid_wa2 = await db.get_setting("pid_wa_s2", config.pid_whatsapp_s2)
            key_disp = (key[:6] + "…" + key[-4:]) if len(key) > 10 else ("✅ Set" if key else "❌ Not set")
            await bot.edit_message_text(
                f"🔑 <b>إعدادات Durian API</b>\n\n"
                f"👤 Username: <code>{name}</code>\n"
                f"🔑 API Key: <code>{key_disp}</code>\n\n"
                f"✈️ PID Telegram: <code>{pid_tg}</code>\n"
                f"💬 PID WA S1: <code>{pid_wa1}</code>\n"
                f"💬 PID WA S2: <code>{pid_wa2}</code>",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_durian(), parse_mode="HTML",
            )

        elif data in ("durian:set_name", "durian:set_key", "durian:set_pid_tg",
                      "durian:set_pid_wa1", "durian:set_pid_wa2"):
            _DURIAN_STATES = {
                "durian:set_name":    ("durian_name",    "👤 أرسل اسم المستخدم الجديد:"),
                "durian:set_key":     ("durian_api_key", "🔑 أرسل API Key الجديد:"),
                "durian:set_pid_tg":  ("pid_tg",         "✈️ أرسل PID تيليغرام الجديد:"),
                "durian:set_pid_wa1": ("pid_wa_s1",      "💬 أرسل PID WhatsApp Server 1 الجديد:"),
                "durian:set_pid_wa2": ("pid_wa_s2",      "💬 أرسل PID WhatsApp Server 2 الجديد:"),
            }
            setting_key, prompt = _DURIAN_STATES[data]
            await bot.edit_message_text(
                prompt, call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:durian"), parse_mode="HTML",
            )
            _set_state(uid, "set_durian_key", {"durian_setting": setting_key})

        # ── Test API ──────────────────────────────────────────────
        elif data == "admin:test_api":
            await bot.answer_callback_query(call.id, "⏳ اختبار API...")
            client  = get_client()
            results = []
            try:
                bal = await client.get_balance()
                results.append(f"✅ الاتصال ناجح\n💰 الرصيد: <b>{bal}</b>")
            except Exception as exc:
                results.append(f"❌ فشل الاتصال: {exc}")
            for label, pid in [
                ("Telegram (0257)", config.pid_telegram),
                ("WA S1 (0107)",    config.pid_whatsapp_s1),
                ("WA S2 (0528)",    config.pid_whatsapp_s2),
            ]:
                try:
                    counts = await client.get_country_counts(pid)
                    total  = sum(counts.values())
                    results.append(f"✅ {label}: <b>{total}</b> أرقام متاحة")
                except Exception as exc:
                    results.append(f"❌ {label}: {exc}")
            await bot.send_message(
                call.message.chat.id,
                "🧪 <b>نتيجة اختبار API</b>\n\n" + "\n".join(results),
                parse_mode="HTML",
            )

        # ── Backup ────────────────────────────────────────────────
        elif data == "admin:backup":
            await bot.answer_callback_query(call.id, "⏳ جارٍ إنشاء النسخة الاحتياطية...")
            await _send_backup(bot, call.message.chat.id)

        # ── Notification channel ──────────────────────────────────
        elif data == "admin:notif":
            ch_id   = await db.get_setting("notif_channel_id",   "")
            ch_link = await db.get_setting("notif_channel_link", "")
            await bot.edit_message_text(
                f"🔔 <b>قناة إشعارات التفعيل</b>\n\n"
                f"معرف القناة: <code>{ch_id or 'غير مضبوط'}</code>\n"
                f"رابط القناة: {ch_link or 'غير مضبوط'}\n\n"
                f"<i>تُرسل الإشعارات عند نجاح العملية فقط.</i>",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_notif(ch_id), parse_mode="HTML",
            )

        elif data in ("notif:set_id", "notif:set_link"):
            _NOTIF = {
                "notif:set_id":   ("notif_channel_id",   "📌 أرسل معرف القناة:\nمثال: <code>-1001234567890</code> أو <code>@mychannel</code>"),
                "notif:set_link": ("notif_channel_link",  "🔗 أرسل رابط القناة:\nمثال: <code>https://t.me/mychannel</code>"),
            }
            key, prompt = _NOTIF[data]
            await bot.edit_message_text(
                prompt, call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:notif"), parse_mode="HTML",
            )
            _set_state(uid, "set_notif_channel", {"notif_setting": key})

        elif data == "notif:disable":
            await db.set_setting("notif_channel_id", "")
            from notifier import init_notifier
            init_notifier(bot, "", "")
            await bot.answer_callback_query(call.id, "🔕 تم تعطيل إشعارات القناة")
            ch_id   = await db.get_setting("notif_channel_id",   "")
            ch_link = await db.get_setting("notif_channel_link", "")
            await bot.edit_message_text(
                f"🔔 <b>قناة إشعارات التفعيل</b>\n\n"
                f"معرف القناة: <code>{ch_id or 'غير مضبوط'}</code>\n"
                f"رابط القناة: {ch_link or 'غير مضبوط'}",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_notif(ch_id), parse_mode="HTML",
            )

        elif data == "notif:test":
            from notifier import get_notifier
            notifier = get_notifier()
            if not notifier:
                await bot.answer_callback_query(call.id, "❌ القناة غير مضبوطة", show_alert=True)
                return
            await bot.answer_callback_query(call.id, "⏳ جارٍ الإرسال...")
            await notifier.notify_success(
                service_key="tg", number="+966501234567",
                country_code="sa", country_flag="🇸🇦",
                country_name="السعودية", price=0.25,
            )
            await bot.answer_callback_query(call.id, "✅ تم إرسال رسالة تجريبية للقناة", show_alert=True)

        # ── Crypto settings ───────────────────────────────────────
        elif data == "admin:crypto":
            bep20_on   = await db.get_setting("pay_bep20") == "1"
            trc20_on   = await db.get_setting("pay_trc20") == "1"
            bep20_addr = await db.get_setting("bep20_address")
            trc20_addr = await db.get_setting("trc20_address")
            def short(a):
                return (a[:10] + "…" + a[-6:]) if len(a) > 16 else (a or "❌ غير مضبوط")
            await bot.edit_message_text(
                f"💳 <b>إعدادات الدفع</b>\n\n"
                f"<b>BEP20:</b> {'✅' if bep20_on else '❌'} | <code>{short(bep20_addr)}</code>\n"
                f"<b>TRC20:</b> {'✅' if trc20_on else '❌'} | <code>{short(trc20_addr)}</code>",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_admin_crypto(bep20_on, trc20_on), parse_mode="HTML",
            )

        elif data.startswith("crypto_adm:"):
            _CRYPTO_MAP = {
                "crypto_adm:toggle_bep20": ("pay_bep20",       None),
                "crypto_adm:toggle_trc20": ("pay_trc20",       None),
                "crypto_adm:bep20_addr":   ("bep20_address",   "📝 أرسل عنوان BEP20:"),
                "crypto_adm:bep20_rate":   ("bep20_usdt_rate", "💱 أرسل سعر صرف BEP20 (مثال: 1.00):"),
                "crypto_adm:bep20_min":    ("bep20_min_usdt",  "⬆️ أرسل الحد الأدنى BEP20 بـ USDT:"),
                "crypto_adm:trc20_addr":   ("trc20_address",   "📝 أرسل عنوان TRC20:"),
                "crypto_adm:trc20_key":    ("trc20_api_key",   "🔑 أرسل TronGrid API Key:"),
                "crypto_adm:trc20_rate":   ("trc20_usdt_rate", "💱 أرسل سعر صرف TRC20:"),
                "crypto_adm:trc20_min":    ("trc20_min_usdt",  "⬆️ أرسل الحد الأدنى TRC20 بـ USDT:"),
            }
            key, prompt = _CRYPTO_MAP.get(data, (None, None))
            if key and prompt is None:
                cur = await db.get_setting(key)
                await db.set_setting(key, "0" if cur == "1" else "1")
                await bot.answer_callback_query(call.id, "✅ تم التغيير")
                # refresh crypto panel
                bep20_on   = await db.get_setting("pay_bep20") == "1"
                trc20_on   = await db.get_setting("pay_trc20") == "1"
                bep20_addr = await db.get_setting("bep20_address")
                trc20_addr = await db.get_setting("trc20_address")
                def short(a):
                    return (a[:10] + "…" + a[-6:]) if len(a) > 16 else (a or "❌ غير مضبوط")
                await bot.edit_message_text(
                    f"💳 <b>إعدادات الدفع</b>\n\n"
                    f"<b>BEP20:</b> {'✅' if bep20_on else '❌'} | <code>{short(bep20_addr)}</code>\n"
                    f"<b>TRC20:</b> {'✅' if trc20_on else '❌'} | <code>{short(trc20_addr)}</code>",
                    call.message.chat.id, call.message.message_id,
                    reply_markup=kb_admin_crypto(bep20_on, trc20_on), parse_mode="HTML",
                )
            elif key and prompt:
                await bot.edit_message_text(
                    prompt, call.message.chat.id, call.message.message_id,
                    reply_markup=kb_back(lang, "admin:crypto"), parse_mode="HTML",
                )
                _set_state(uid, "set_crypto", {"crypto_setting": key})

        # ── Pricing ───────────────────────────────────────────────
        elif data == "admin:pricing":
            prices = await pricing.get_base_prices()
            await bot.edit_message_text(
                f"💵 <b>نظام التسعير</b>\n\n"
                f"✈️ Telegram: <code>${prices['tg']:.4f}</code>\n"
                f"💬 WhatsApp S1: <code>${prices['wa_s1']:.4f}</code>\n"
                f"💬 WhatsApp S2: <code>${prices['wa_s2']:.4f}</code>\n\n"
                f"<i>اختر الخدمة لتعديل سعرها:</i>",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_pricing(), parse_mode="HTML",
            )

        elif data.startswith("price:base:"):
            svc      = data.split(":")[2]
            cur      = (await pricing.get_base_prices()).get(svc, 0)
            svc_name = _SVC_NAMES.get(svc, svc)
            await bot.edit_message_text(
                f"💵 <b>تعديل السعر الموحد لـ {svc_name}</b>\n\n"
                f"السعر الحالي: <code>${cur:.4f}</code>\n\n"
                f"أرسل السعر الجديد (مثال: <code>0.25</code>):",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, "admin:pricing"), parse_mode="HTML",
            )
            _set_state(uid, "set_base_price", {"price_svc": svc})

        elif data.startswith("price:countries:"):
            svc      = data.split(":")[2]
            svc_name = _SVC_NAMES.get(svc, svc)
            prices   = await pricing.get_all_country_prices(svc)
            if not prices:
                text = (
                    f"🌍 <b>أسعار الدول الخاصة — {svc_name}</b>\n\n"
                    "<i>لا توجد أسعار خاصة بعد.\n"
                    "جميع الدول تستخدم السعر الموحد.</i>"
                )
            else:
                from countries_manager import countries_manager as cm
                lines = [f"🌍 <b>أسعار الدول الخاصة — {svc_name}</b>\n"]
                for cc, price in sorted(prices.items()):
                    c    = cm.get(cc)
                    flag = c.get("flag", "🏳️") if c else "🏳️"
                    name = c.get("name_ar", cc.upper()) if c else cc.upper()
                    lines.append(f"{flag} {name}: <code>${price:.4f}</code>")
                text = "\n".join(lines)
            await bot.edit_message_text(
                text, call.message.chat.id, call.message.message_id,
                reply_markup=kb_country_prices(svc, bool(prices)), parse_mode="HTML",
            )

        elif data.startswith("price:set_country:"):
            svc = data.split(":")[2]
            await bot.edit_message_text(
                f"🌍 <b>إضافة/تعديل سعر دولة</b>\n\n"
                f"أرسل بالتنسيق:\n<code>رمز_الدولة السعر</code>\n\n"
                f"مثال:\n<code>ru 0.30</code>\n<code>eg 0.20</code>",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, f"price:countries:{svc}"), parse_mode="HTML",
            )
            _set_state(uid, "set_country_price", {"price_svc": svc})

        elif data.startswith("price:del_country:"):
            svc = data.split(":")[2]
            await bot.edit_message_text(
                f"🗑 <b>حذف سعر دولة خاصة</b>\n\nأرسل رمز الدولة (مثال: <code>ru</code>):",
                call.message.chat.id, call.message.message_id,
                reply_markup=kb_back(lang, f"price:countries:{svc}"), parse_mode="HTML",
            )
            _set_state(uid, "del_country_price", {"price_svc": svc})

    # ── Message handler (FSM) ─────────────────────────────────────
    @bot.message_handler(func=lambda m: is_admin(m.from_user.id) and m.content_type in ("text", "document"))
    async def handle_admin_messages(message: Message):
        uid   = message.from_user.id
        state = _get_state(uid)
        if not state:
            return
        lang  = await db.get_user_lang(uid)
        st    = state.get("state", "")
        sdata = state.get("data", {})

        # ── set_margin ────────────────────────────────────────────
        if st == "set_margin":
            try:
                val = float(message.text.strip())
                assert 0 <= val <= 500
            except Exception:
                await bot.send_message(message.chat.id, t("invalid_input", lang))
                return
            await db.set_setting("profit_margin", str(val))
            config.profit_margin = val
            _clear_state(uid)
            await bot.send_message(
                message.chat.id,
                t("admin_margin_updated", lang, margin=val), parse_mode="HTML"
            )

        # ── search_user ───────────────────────────────────────────
        elif st == "search_user":
            user = await db.search_user(message.text.strip())
            if not user:
                await bot.send_message(message.chat.id, t("user_not_found", lang))
                _clear_state(uid)
                return
            orders = await db.count_orders_for_user(user["user_id"])
            await bot.send_message(
                message.chat.id,
                t("admin_user_info", lang,
                  uid=user["user_id"], name=user["full_name"],
                  balance=user["balance"], orders=orders,
                  banned="🚫" if user["is_banned"] else "✅"),
                reply_markup=kb_admin_user(user["user_id"], bool(user["is_banned"])),
                parse_mode="HTML",
            )
            _clear_state(uid)

        # ── user_add_bal ──────────────────────────────────────────
        elif st == "user_add_bal":
            try:
                amt = float(message.text.strip())
                assert amt > 0
            except Exception:
                await bot.send_message(message.chat.id, t("invalid_input", lang))
                return
            new_bal = await db.update_balance(sdata["target_uid"], +amt)
            await bot.send_message(
                message.chat.id,
                t("admin_balance_updated", lang, balance=new_bal), parse_mode="HTML"
            )
            _clear_state(uid)

        # ── user_deduct_bal ───────────────────────────────────────
        elif st == "user_deduct_bal":
            try:
                amt = float(message.text.strip())
                assert amt > 0
            except Exception:
                await bot.send_message(message.chat.id, t("invalid_input", lang))
                return
            new_bal = await db.update_balance(sdata["target_uid"], -amt)
            await bot.send_message(
                message.chat.id,
                t("admin_balance_updated", lang, balance=new_bal), parse_mode="HTML"
            )
            _clear_state(uid)

        # ── broadcast ─────────────────────────────────────────────
        elif st == "broadcast":
            _clear_state(uid)
            users = await db.get_all_users()
            sent  = 0
            for u in users:
                try:
                    if message.photo:
                        await bot.send_photo(
                            u["user_id"], photo=message.photo[-1].file_id,
                            caption=message.caption or "",
                        )
                    else:
                        await bot.send_message(
                            u["user_id"], text=message.text or "", parse_mode="HTML"
                        )
                    sent += 1
                except Exception:
                    pass
                await asyncio.sleep(0.05)
            await bot.send_message(
                message.chat.id,
                t("admin_broadcast_done", lang, count=sent), parse_mode="HTML"
            )

        # ── set_durian_key ────────────────────────────────────────
        elif st == "set_durian_key":
            setting_key = sdata.get("durian_setting", "")
            new_val     = message.text.strip()
            await db.set_setting(setting_key, new_val)
            if setting_key == "durian_name":       config.durian_name = new_val
            elif setting_key == "durian_api_key":  config.durian_api_key = new_val
            elif setting_key == "pid_tg":          config.pid_telegram = new_val
            elif setting_key == "pid_wa_s1":       config.pid_whatsapp_s1 = new_val
            elif setting_key == "pid_wa_s2":       config.pid_whatsapp_s2 = new_val
            await reload_client()
            _clear_state(uid)
            await bot.send_message(message.chat.id, t("admin_creds_updated", lang), parse_mode="HTML")

        # ── set_base_price ────────────────────────────────────────
        elif st == "set_base_price":
            svc = sdata.get("price_svc", "tg")
            try:
                val = float(message.text.strip())
                assert 0 < val < 1000
            except Exception:
                await bot.send_message(
                    message.chat.id,
                    "❌ قيمة غير صحيحة. أدخل رقماً مثل <code>0.25</code>", parse_mode="HTML"
                )
                return
            await pricing.set_base_price(svc, val)
            _clear_state(uid)
            await bot.send_message(
                message.chat.id,
                f"✅ <b>تم تحديث سعر {_SVC_NAMES.get(svc, svc)}</b>\n"
                f"السعر الجديد: <code>${val:.4f}</code>", parse_mode="HTML"
            )

        # ── set_country_price ─────────────────────────────────────
        elif st == "set_country_price":
            svc   = sdata.get("price_svc", "tg")
            parts = message.text.strip().split()
            if len(parts) != 2:
                await bot.send_message(
                    message.chat.id,
                    "❌ التنسيق الصحيح: <code>رمز_الدولة السعر</code>\nمثال: <code>ru 0.30</code>",
                    parse_mode="HTML"
                )
                return
            cc, price_str = parts[0].lower(), parts[1]
            try:
                price = float(price_str)
                assert 0 < price < 1000 and len(cc) >= 2
            except Exception:
                await bot.send_message(message.chat.id, "❌ قيمة غير صحيحة.", parse_mode="HTML")
                return
            await pricing.set_country_price(svc, cc, price)
            _clear_state(uid)
            from countries_manager import countries_manager as cm
            c    = cm.get(cc)
            flag = c.get("flag", "🏳️") if c else "🏳️"
            name = c.get("name_ar", cc.upper()) if c else cc.upper()
            await bot.send_message(
                message.chat.id,
                f"✅ <b>تم ضبط السعر الخاص</b>\n\n"
                f"الخدمة: {_SVC_NAMES.get(svc, svc)}\n"
                f"الدولة: {flag} {name}\n"
                f"السعر: <code>${price:.4f}</code>", parse_mode="HTML"
            )

        # ── del_country_price ─────────────────────────────────────
        elif st == "del_country_price":
            svc = sdata.get("price_svc", "tg")
            cc  = message.text.strip().lower()
            await pricing.delete_country_price(svc, cc)
            _clear_state(uid)
            await bot.send_message(
                message.chat.id,
                f"✅ تم حذف السعر الخاص لـ <code>{cc}</code> في {_SVC_NAMES.get(svc, svc)}.\n"
                f"سيُستخدم السعر الموحد الآن.", parse_mode="HTML"
            )

        # ── set_notif_channel ─────────────────────────────────────
        elif st == "set_notif_channel":
            key = sdata.get("notif_setting", "")
            val = message.text.strip()
            await db.set_setting(key, val)
            from notifier import init_notifier
            ch_id   = await db.get_setting("notif_channel_id",   "")
            ch_link = await db.get_setting("notif_channel_link", "")
            init_notifier(bot, ch_id, ch_link)
            _clear_state(uid)
            await bot.send_message(message.chat.id, f"✅ تم الحفظ: <code>{val}</code>", parse_mode="HTML")

        # ── set_crypto ────────────────────────────────────────────
        elif st == "set_crypto":
            key = sdata.get("crypto_setting", "")
            await db.set_setting(key, message.text.strip())
            _clear_state(uid)
            await bot.send_message(message.chat.id, "✅ تم الحفظ", parse_mode="HTML")

        # ── restore_db ────────────────────────────────────────────
        elif st == "restore_db":
            if message.content_type != "document":
                return
            doc = message.document
            if not doc.file_name.endswith(".db"):
                await bot.send_message(message.chat.id, "❌ يجب إرسال ملف .db")
                return
            _clear_state(uid)
            try:
                file_info = await bot.get_file(doc.file_id)
                downloaded = await bot.download_file(file_info.file_path)
                with open(config.database_path, "wb") as f:
                    f.write(downloaded)
                await bot.send_message(
                    message.chat.id,
                    "✅ تمت استعادة قاعدة البيانات بنجاح!\nأعد تشغيل البوت."
                )
            except Exception as exc:
                await bot.send_message(message.chat.id, f"❌ فشل الاستعادة: {exc}")


# ── Helper: send backup ───────────────────────────────────────────
async def _send_backup(bot, chat_id: int) -> None:
    try:
        with open(config.database_path, "rb") as f:
            data = f.read()
        await bot.send_document(
            chat_id,
            ("otp_bot_backup.db", data),
            caption=(
                "💾 <b>نسخة احتياطية من قاعدة البيانات</b>\n\n"
                "لاستعادتها:\n"
                "1. أرسل الملف للبوت\n"
                "2. أو استخدم /restore"
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        await bot.send_message(chat_id, f"❌ خطأ في إنشاء النسخة: {exc}")
