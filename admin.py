"""
handlers/admin.py — Admin panel
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Commands:
  /admin   — لوحة الإدارة الرئيسية
  /stats   — إحصائيات سريعة
  /backup  — نسخ احتياطي من DB

Features:
  • إحصائيات اليوم + الإجمالي + أفضل خدمة/دولة
  • إدارة المستخدمين (بحث، رصيد، حظر)
  • نظام التسعير الكامل (موحد + خاص بالدول)
  • إعدادات قناة الإشعارات
  • تعديل Durian credentials
  • إعدادات الدفع (BEP20/TRC20)
  • اختبار API الفوري
  • نسخ + استعادة DB
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Document, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import config
from database import db
from durian_api import get_client, reload_client
from keyboards import kb_admin, kb_admin_crypto, kb_admin_user, kb_back
from pricing import pricing
from strings import t

logger = logging.getLogger(__name__)
router = Router()


def is_admin(uid: int) -> bool:
    return config.is_admin(uid)


# ── FSM ───────────────────────────────────────────────────────────
class AdminState(StatesGroup):
    # Stats / margin
    set_margin        = State()
    # User management
    search_user       = State()
    user_add_bal      = State()
    user_deduct_bal   = State()
    # Broadcast
    broadcast         = State()
    # Durian
    set_durian_key    = State()
    # Pricing
    set_base_price    = State()   # سعر موحد
    set_country_price = State()   # سعر دولة
    del_country_price = State()   # حذف سعر دولة
    # Notification channel
    set_notif_channel = State()
    # Crypto
    set_crypto        = State()
    # Restore DB
    restore_db        = State()


# ═══════════════════════════════════════════════════════════════════
#  /admin
# ═══════════════════════════════════════════════════════════════════
@router.message(Command("admin"))
async def cmd_admin(message: Message, lang: str) -> None:
    if not is_admin(message.from_user.id):
        return
    await _show_panel(message, lang)


@router.callback_query(F.data == "admin:panel")
async def cb_panel(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    await _show_panel(call, lang)


async def _show_panel(target: Message | CallbackQuery, lang: str) -> None:
    text = await _build_stats(lang)
    kb   = kb_admin(lang)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


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


# ═══════════════════════════════════════════════════════════════════
#  /stats — Quick stats command
# ═══════════════════════════════════════════════════════════════════
@router.message(Command("stats"))
async def cmd_stats(message: Message, lang: str) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(await _build_stats(lang), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  Refresh stats
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        await _build_stats(lang), reply_markup=kb_admin(lang), parse_mode="HTML"
    )
    await call.answer("✅")


# ═══════════════════════════════════════════════════════════════════
#  Profit Margin
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:margin")
async def cb_margin(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    margin = await db.get_setting("profit_margin", "30")
    await call.message.edit_text(
        f"📈 <b>الهامش الحالي: <code>{margin}%</code></b>\n\nأرسل النسبة الجديدة:",
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )
    await state.set_state(AdminState.set_margin)


@router.message(AdminState.set_margin)
async def msg_margin(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        val = float(message.text.strip())
        assert 0 <= val <= 500
    except Exception:
        await message.answer(t("invalid_input", lang))
        return
    await db.set_setting("profit_margin", str(val))
    config.profit_margin = val
    await state.clear()
    await message.answer(t("admin_margin_updated", lang, margin=val), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  User management
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:users")
async def cb_users(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        t("admin_search_user", lang),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )
    await state.set_state(AdminState.search_user)


@router.message(AdminState.search_user)
async def msg_search(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    user = await db.search_user(message.text.strip())
    if not user:
        await message.answer(t("user_not_found", lang))
        await state.clear()
        return
    orders = await db.count_orders_for_user(user["user_id"])
    await message.answer(
        t("admin_user_info", lang,
          uid=user["user_id"], name=user["full_name"],
          balance=user["balance"], orders=orders,
          banned="🚫" if user["is_banned"] else "✅"),
        reply_markup=kb_admin_user(user["user_id"], bool(user["is_banned"])),
        parse_mode="HTML",
    )
    await state.clear()


async def _balance_change(message: Message, lang: str, state: FSMContext, sign: float) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    uid  = data.get("target_uid")
    try:
        amt = float(message.text.strip())
        assert amt > 0
    except Exception:
        await message.answer(t("invalid_input", lang))
        return
    new_bal = await db.update_balance(uid, sign * amt)
    await message.answer(t("admin_balance_updated", lang, balance=new_bal), parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("admu:add:"))
async def cb_add_bal(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await state.update_data(target_uid=uid)
    await call.message.edit_text(
        t("admin_enter_amount", lang),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )
    await state.set_state(AdminState.user_add_bal)


@router.callback_query(F.data.startswith("admu:deduct:"))
async def cb_deduct_bal(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await state.update_data(target_uid=uid)
    await call.message.edit_text(
        t("admin_enter_amount", lang),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )
    await state.set_state(AdminState.user_deduct_bal)


@router.message(AdminState.user_add_bal)
async def msg_add(message: Message, lang: str, state: FSMContext) -> None:
    await _balance_change(message, lang, state, +1)


@router.message(AdminState.user_deduct_bal)
async def msg_deduct(message: Message, lang: str, state: FSMContext) -> None:
    await _balance_change(message, lang, state, -1)


@router.callback_query(F.data.startswith("admu:ban:"))
async def cb_ban(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await db.set_ban(uid, True)
    await call.message.edit_text(
        t("admin_user_banned", lang, uid=uid),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admu:unban:"))
async def cb_unban(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    uid = int(call.data.split(":")[2])
    await db.set_ban(uid, False)
    await call.message.edit_text(
        t("admin_user_unbanned", lang, uid=uid),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════════════════
#  Broadcast
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    await call.message.edit_text(
        t("admin_broadcast_prompt", lang),
        reply_markup=kb_back(lang, "admin:panel"), parse_mode="HTML",
    )
    await state.set_state(AdminState.broadcast)


@router.message(AdminState.broadcast)
async def msg_broadcast(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = await db.get_all_users()
    sent  = 0
    for u in users:
        try:
            if message.photo:
                await message.bot.send_photo(
                    u["user_id"], photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                )
            else:
                await message.bot.send_message(
                    u["user_id"], text=message.text or "", parse_mode="HTML"
                )
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await message.answer(t("admin_broadcast_done", lang, count=sent), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  Durian API credentials
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:durian")
async def cb_durian(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    name = await db.get_setting("durian_name", config.durian_name)
    key  = await db.get_setting("durian_api_key", config.durian_api_key)
    pid_tg   = await db.get_setting("pid_tg",   config.pid_telegram)
    pid_wa1  = await db.get_setting("pid_wa_s1", config.pid_whatsapp_s1)
    pid_wa2  = await db.get_setting("pid_wa_s2", config.pid_whatsapp_s2)
    key_disp = (key[:6] + "…" + key[-4:]) if len(key) > 10 else ("✅ Set" if key else "❌ Not set")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👤 تغيير اسم المستخدم", callback_data="durian:set_name"))
    b.row(InlineKeyboardButton(text="🔑 تغيير API Key",      callback_data="durian:set_key"))
    b.row(InlineKeyboardButton(text="✈️ تغيير PID Telegram", callback_data="durian:set_pid_tg"))
    b.row(InlineKeyboardButton(text="💬 تغيير PID WA S1",    callback_data="durian:set_pid_wa1"))
    b.row(InlineKeyboardButton(text="💬 تغيير PID WA S2",    callback_data="durian:set_pid_wa2"))
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await call.message.edit_text(
        f"🔑 <b>إعدادات Durian API</b>\n\n"
        f"👤 Username: <code>{name}</code>\n"
        f"🔑 API Key: <code>{key_disp}</code>\n\n"
        f"✈️ PID Telegram: <code>{pid_tg}</code>\n"
        f"💬 PID WA S1: <code>{pid_wa1}</code>\n"
        f"💬 PID WA S2: <code>{pid_wa2}</code>",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )


_DURIAN_STATES = {
    "durian:set_name":    ("durian_name",    "👤 أرسل اسم المستخدم الجديد:"),
    "durian:set_key":     ("durian_api_key", "🔑 أرسل API Key الجديد:"),
    "durian:set_pid_tg":  ("pid_tg",         "✈️ أرسل PID تيليغرام الجديد:"),
    "durian:set_pid_wa1": ("pid_wa_s1",      "💬 أرسل PID WhatsApp Server 1 الجديد:"),
    "durian:set_pid_wa2": ("pid_wa_s2",      "💬 أرسل PID WhatsApp Server 2 الجديد:"),
}


@router.callback_query(F.data.in_(set(_DURIAN_STATES.keys())))
async def cb_durian_set(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    setting_key, prompt = _DURIAN_STATES[call.data]
    await state.update_data(durian_setting=setting_key)
    await call.message.edit_text(prompt, reply_markup=kb_back(lang, "admin:durian"),
                                  parse_mode="HTML")
    await state.set_state(AdminState.set_durian_key)


@router.message(AdminState.set_durian_key)
async def msg_durian_key(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data        = await state.get_data()
    setting_key = data.get("durian_setting", "")
    new_val     = message.text.strip()
    await db.set_setting(setting_key, new_val)
    # Update config live
    if setting_key == "durian_name":
        config.durian_name = new_val
    elif setting_key == "durian_api_key":
        config.durian_api_key = new_val
    elif setting_key == "pid_tg":
        config.pid_telegram = new_val
    elif setting_key == "pid_wa_s1":
        config.pid_whatsapp_s1 = new_val
    elif setting_key == "pid_wa_s2":
        config.pid_whatsapp_s2 = new_val
    await reload_client()
    await state.clear()
    await message.answer(t("admin_creds_updated", lang), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  Test API
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:test_api")
async def cb_test_api(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    await call.answer("⏳ اختبار API...")
    client = get_client()

    results = []
    # Test balance
    try:
        bal = await client.get_balance()
        results.append(f"✅ الاتصال ناجح\n💰 الرصيد: <b>{bal}</b>")
    except Exception as exc:
        results.append(f"❌ فشل الاتصال: {exc}")

    # Test each PID counts
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

    await call.message.answer(
        "🧪 <b>نتيجة اختبار API</b>\n\n" + "\n".join(results),
        parse_mode="HTML",
    )


# ═══════════════════════════════════════════════════════════════════
#  Backup & Restore
# ═══════════════════════════════════════════════════════════════════
@router.message(Command("backup"))
async def cmd_backup(message: Message, lang: str) -> None:
    if not is_admin(message.from_user.id):
        return
    await _send_backup(message)


@router.callback_query(F.data == "admin:backup")
async def cb_backup(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    await call.answer("⏳ جارٍ إنشاء النسخة الاحتياطية...")
    await _send_backup(call.message)


async def _send_backup(message: Message) -> None:
    try:
        with open(config.database_path, "rb") as f:
            data = f.read()
        doc = BufferedInputFile(data, filename="otp_bot_backup.db")
        await message.answer_document(
            doc,
            caption=(
                "💾 <b>نسخة احتياطية من قاعدة البيانات</b>\n\n"
                "لاستعادتها:\n"
                "1. أرسل الملف للبوت\n"
                "2. أو استخدم /restore"
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        await message.answer(f"❌ خطأ في إنشاء النسخة: {exc}")


@router.message(Command("restore"))
async def cmd_restore(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "⚠️ <b>استعادة قاعدة البيانات</b>\n\n"
        "أرسل ملف <code>.db</code> الذي تريد استعادته.\n"
        "<b>تحذير: سيتم استبدال قاعدة البيانات الحالية!</b>",
        parse_mode="HTML",
    )
    await state.set_state(AdminState.restore_db)


@router.message(AdminState.restore_db, F.document)
async def msg_restore(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    doc: Document = message.document
    if not doc.file_name.endswith(".db"):
        await message.answer("❌ يجب إرسال ملف .db")
        return

    await state.clear()
    try:
        file = await message.bot.download(doc)
        content = file.read()
        with open(config.database_path, "wb") as f:
            f.write(content)
        await message.answer("✅ تمت استعادة قاعدة البيانات بنجاح!\nأعد تشغيل البوت.")
    except Exception as exc:
        await message.answer(f"❌ فشل الاستعادة: {exc}")


# ═══════════════════════════════════════════════════════════════════
#  Crypto settings
# ═══════════════════════════════════════════════════════════════════
@router.callback_query(F.data == "admin:crypto")
async def cb_crypto(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    bep20_on  = await db.get_setting("pay_bep20") == "1"
    trc20_on  = await db.get_setting("pay_trc20") == "1"
    bep20_addr= await db.get_setting("bep20_address")
    trc20_addr= await db.get_setting("trc20_address")

    def short(a):
        return (a[:10] + "…" + a[-6:]) if len(a) > 16 else (a or "❌ غير مضبوط")

    await call.message.edit_text(
        f"💳 <b>إعدادات الدفع</b>\n\n"
        f"<b>BEP20:</b> {'✅' if bep20_on else '❌'} | <code>{short(bep20_addr)}</code>\n"
        f"<b>TRC20:</b> {'✅' if trc20_on else '❌'} | <code>{short(trc20_addr)}</code>",
        reply_markup=kb_admin_crypto(bep20_on, trc20_on),
        parse_mode="HTML",
    )


_CRYPTO_ADM_MAP = {
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


@router.callback_query(F.data.in_(set(_CRYPTO_ADM_MAP.keys())))
async def cb_crypto_adm(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    key, prompt = _CRYPTO_ADM_MAP[call.data]
    if prompt is None:
        # toggle
        cur = await db.get_setting(key)
        await db.set_setting(key, "0" if cur == "1" else "1")
        await call.answer("✅ تم التغيير")
        await cb_crypto(call, lang)
        return
    await state.update_data(crypto_setting=key)
    await call.message.edit_text(
        prompt, reply_markup=kb_back(lang, "admin:crypto"), parse_mode="HTML"
    )
    await state.set_state(AdminState.set_crypto)


@router.message(AdminState.set_crypto)
async def msg_set_crypto(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key  = data.get("crypto_setting", "")
    await db.set_setting(key, message.text.strip())
    await state.clear()
    await message.answer("✅ تم الحفظ", parse_mode="HTML")


# ═══════════════════════════════════════════════════════════════════
#  💵 نظام التسعير
# ═══════════════════════════════════════════════════════════════════

_SVC_NAMES = {
    "tg":    "✈️ Telegram",
    "wa_s1": "💬 WhatsApp Server 1",
    "wa_s2": "💬 WhatsApp Server 2",
}


def _build_pricing_keyboard() -> "InlineKeyboardMarkup":
    b = InlineKeyboardBuilder()
    # أسعار موحدة
    b.row(InlineKeyboardButton(text="✈️ سعر Telegram الموحد",    callback_data="price:base:tg"))
    b.row(InlineKeyboardButton(text="💬 سعر WhatsApp S1 الموحد", callback_data="price:base:wa_s1"))
    b.row(InlineKeyboardButton(text="💬 سعر WhatsApp S2 الموحد", callback_data="price:base:wa_s2"))
    # أسعار خاصة بالدول
    b.row(InlineKeyboardButton(text="─────────────────", callback_data="noop"))
    b.row(InlineKeyboardButton(text="🌍 أسعار دول Telegram",       callback_data="price:countries:tg"))
    b.row(InlineKeyboardButton(text="🌍 أسعار دول WhatsApp S1",    callback_data="price:countries:wa_s1"))
    b.row(InlineKeyboardButton(text="🌍 أسعار دول WhatsApp S2",    callback_data="price:countries:wa_s2"))
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))
    return b.as_markup()


@router.callback_query(F.data == "admin:pricing")
async def cb_pricing(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    prices = await pricing.get_base_prices()
    text = (
        "💵 <b>نظام التسعير</b>\n\n"
        f"✈️ Telegram: <code>${prices['tg']:.4f}</code>\n"
        f"💬 WhatsApp S1: <code>${prices['wa_s1']:.4f}</code>\n"
        f"💬 WhatsApp S2: <code>${prices['wa_s2']:.4f}</code>\n\n"
        "<i>اختر الخدمة لتعديل سعرها:</i>"
    )
    await call.message.edit_text(text, reply_markup=_build_pricing_keyboard(), parse_mode="HTML")


# ── تعديل السعر الموحد ────────────────────────────────────────────
@router.callback_query(F.data.startswith("price:base:"))
async def cb_price_base(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    svc = call.data.split(":")[2]   # tg | wa_s1 | wa_s2
    cur = (await pricing.get_base_prices()).get(svc, 0)
    svc_name = _SVC_NAMES.get(svc, svc)
    await state.update_data(price_svc=svc)
    await call.message.edit_text(
        f"💵 <b>تعديل السعر الموحد لـ {svc_name}</b>\n\n"
        f"السعر الحالي: <code>${cur:.4f}</code>\n\n"
        f"أرسل السعر الجديد (مثال: <code>0.25</code>):",
        reply_markup=kb_back(lang, "admin:pricing"), parse_mode="HTML",
    )
    await state.set_state(AdminState.set_base_price)


@router.message(AdminState.set_base_price)
async def msg_set_base_price(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    svc  = data.get("price_svc", "tg")
    try:
        val = float(message.text.strip())
        assert 0 < val < 1000
    except Exception:
        await message.answer("❌ قيمة غير صحيحة. أدخل رقماً مثل <code>0.25</code>",
                             parse_mode="HTML")
        return
    await pricing.set_base_price(svc, val)
    await state.clear()
    svc_name = _SVC_NAMES.get(svc, svc)
    await message.answer(
        f"✅ <b>تم تحديث سعر {svc_name}</b>\n"
        f"السعر الجديد: <code>${val:.4f}</code>",
        parse_mode="HTML",
    )


# ── عرض وتعديل أسعار الدول ───────────────────────────────────────
@router.callback_query(F.data.startswith("price:countries:"))
async def cb_price_countries(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    svc      = call.data.split(":")[2]
    svc_name = _SVC_NAMES.get(svc, svc)
    prices   = await pricing.get_all_country_prices(svc)

    if not prices:
        text = (
            f"🌍 <b>أسعار الدول الخاصة — {svc_name}</b>\n\n"
            "<i>لا توجد أسعار خاصة بعد.\n"
            "جميع الدول تستخدم السعر الموحد.</i>"
        )
    else:
        lines = [f"🌍 <b>أسعار الدول الخاصة — {svc_name}</b>\n"]
        for cc, price in sorted(prices.items()):
            from countries_manager import countries_manager
            c    = countries_manager.get(cc)
            flag = c.get("flag", "🏳️") if c else "🏳️"
            name = c.get("name_ar", cc.upper()) if c else cc.upper()
            lines.append(f"{flag} {name}: <code>${price:.4f}</code>")
        text = "\n".join(lines)

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="➕ إضافة/تعديل سعر دولة",
        callback_data=f"price:set_country:{svc}",
    ))
    if prices:
        b.row(InlineKeyboardButton(
            text="🗑 حذف سعر دولة",
            callback_data=f"price:del_country:{svc}",
        ))
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:pricing"))

    await call.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="HTML")


# ── ضبط سعر دولة خاصة ────────────────────────────────────────────
@router.callback_query(F.data.startswith("price:set_country:"))
async def cb_price_set_country(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    svc = call.data.split(":")[2]
    await state.update_data(price_svc=svc)
    await call.message.edit_text(
        f"🌍 <b>إضافة/تعديل سعر دولة</b>\n\n"
        f"أرسل بالتنسيق:\n"
        f"<code>رمز_الدولة السعر</code>\n\n"
        f"مثال:\n"
        f"<code>ru 0.30</code>\n"
        f"<code>eg 0.20</code>\n"
        f"<code>sa 0.28</code>",
        reply_markup=kb_back(lang, f"price:countries:{svc}"),
        parse_mode="HTML",
    )
    await state.set_state(AdminState.set_country_price)


@router.message(AdminState.set_country_price)
async def msg_set_country_price(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    svc  = data.get("price_svc", "tg")
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer(
            "❌ التنسيق الصحيح: <code>رمز_الدولة السعر</code>\n"
            "مثال: <code>ru 0.30</code>", parse_mode="HTML"
        )
        return
    cc, price_str = parts[0].lower(), parts[1]
    try:
        price = float(price_str)
        assert 0 < price < 1000 and len(cc) >= 2
    except Exception:
        await message.answer("❌ قيمة غير صحيحة.", parse_mode="HTML")
        return

    await pricing.set_country_price(svc, cc, price)
    await state.clear()

    from countries_manager import countries_manager
    c    = countries_manager.get(cc)
    flag = c.get("flag", "🏳️") if c else "🏳️"
    name = c.get("name_ar", cc.upper()) if c else cc.upper()
    svc_name = _SVC_NAMES.get(svc, svc)

    await message.answer(
        f"✅ <b>تم ضبط السعر الخاص</b>\n\n"
        f"الخدمة: {svc_name}\n"
        f"الدولة: {flag} {name}\n"
        f"السعر: <code>${price:.4f}</code>",
        parse_mode="HTML",
    )


# ── حذف سعر دولة خاصة ────────────────────────────────────────────
@router.callback_query(F.data.startswith("price:del_country:"))
async def cb_price_del_country(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    svc = call.data.split(":")[2]
    await state.update_data(price_svc=svc)
    await call.message.edit_text(
        f"🗑 <b>حذف سعر دولة خاصة</b>\n\n"
        f"أرسل رمز الدولة (مثال: <code>ru</code>):",
        reply_markup=kb_back(lang, f"price:countries:{svc}"),
        parse_mode="HTML",
    )
    await state.set_state(AdminState.del_country_price)


@router.message(AdminState.del_country_price)
async def msg_del_country_price(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    svc  = data.get("price_svc", "tg")
    cc   = message.text.strip().lower()
    await pricing.delete_country_price(svc, cc)
    await state.clear()
    svc_name = _SVC_NAMES.get(svc, svc)
    await message.answer(
        f"✅ تم حذف السعر الخاص لـ <code>{cc}</code> في {svc_name}.\n"
        f"سيُستخدم السعر الموحد الآن.",
        parse_mode="HTML",
    )


# ── إضافة noop handler (للفاصل في القائمة) ───────────────────────
@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery) -> None:
    await call.answer()


# ═══════════════════════════════════════════════════════════════════
#  🔔 قناة الإشعارات
# ═══════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:notif")
async def cb_notif(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return

    ch_id   = await db.get_setting("notif_channel_id",   "")
    ch_link = await db.get_setting("notif_channel_link", "")

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📌 تعيين معرف القناة",  callback_data="notif:set_id"))
    b.row(InlineKeyboardButton(text="🔗 تعيين رابط القناة",  callback_data="notif:set_link"))
    if ch_id:
        b.row(InlineKeyboardButton(text="🧪 إرسال تجريبي",   callback_data="notif:test"))
        b.row(InlineKeyboardButton(text="🔕 تعطيل الإشعارات",callback_data="notif:disable"))
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))

    await call.message.edit_text(
        f"🔔 <b>قناة إشعارات التفعيل</b>\n\n"
        f"معرف القناة: <code>{ch_id or 'غير مضبوط'}</code>\n"
        f"رابط القناة: {ch_link or 'غير مضبوط'}\n\n"
        f"<i>تُرسل الإشعارات عند نجاح العملية فقط.</i>",
        reply_markup=b.as_markup(), parse_mode="HTML",
    )


_NOTIF_PROMPTS = {
    "notif:set_id":   ("notif_channel_id",   "📌 أرسل معرف القناة:\nمثال: <code>-1001234567890</code> أو <code>@mychannel</code>"),
    "notif:set_link": ("notif_channel_link",  "🔗 أرسل رابط القناة:\nمثال: <code>https://t.me/mychannel</code>"),
}


@router.callback_query(F.data.in_(set(_NOTIF_PROMPTS.keys())))
async def cb_notif_set(call: CallbackQuery, lang: str, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        return
    key, prompt = _NOTIF_PROMPTS[call.data]
    await state.update_data(notif_setting=key)
    await call.message.edit_text(
        prompt, reply_markup=kb_back(lang, "admin:notif"), parse_mode="HTML"
    )
    await state.set_state(AdminState.set_notif_channel)


@router.message(AdminState.set_notif_channel)
async def msg_notif_set(message: Message, lang: str, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key  = data.get("notif_setting", "")
    val  = message.text.strip()
    await db.set_setting(key, val)

    # إعادة تهيئة الـ notifier
    from notifier import init_notifier
    ch_id   = await db.get_setting("notif_channel_id",   "")
    ch_link = await db.get_setting("notif_channel_link", "")
    init_notifier(message.bot, ch_id, ch_link)

    await state.clear()
    await message.answer(f"✅ تم الحفظ: <code>{val}</code>", parse_mode="HTML")


@router.callback_query(F.data == "notif:disable")
async def cb_notif_disable(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    await db.set_setting("notif_channel_id", "")
    from notifier import init_notifier
    init_notifier(call.bot, "", "")
    await call.answer("🔕 تم تعطيل إشعارات القناة")
    await cb_notif(call, lang)


@router.callback_query(F.data == "notif:test")
async def cb_notif_test(call: CallbackQuery, lang: str) -> None:
    if not is_admin(call.from_user.id):
        return
    from notifier import get_notifier
    notifier = get_notifier()
    if not notifier:
        await call.answer("❌ القناة غير مضبوطة", show_alert=True)
        return
    await call.answer("⏳ جارٍ الإرسال...")
    await notifier.notify_success(
        service_key  = "tg",
        number       = "+966501234567",
        country_code = "sa",
        country_flag = "🇸🇦",
        country_name = "السعودية",
        price        = 0.25,
    )
    await call.answer("✅ تم إرسال رسالة تجريبية للقناة", show_alert=True)
