"""keyboards.py — All InlineKeyboardMarkup builders (telebot)"""
from __future__ import annotations

import math
from typing import List, Tuple

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from strings import t

COUNTRIES_PER_PAGE = 12   # 2 columns × 6 rows


def _kb(*rows: list) -> InlineKeyboardMarkup:
    """Helper: بناء InlineKeyboardMarkup من صفوف أزرار."""
    kb = InlineKeyboardMarkup()
    for row in rows:
        kb.row(*row)
    return kb


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


# ── Language ───────────────────────────────────────────────────────
def kb_language() -> InlineKeyboardMarkup:
    return _kb([
        _btn("🇸🇦 العربية", "lang:ar"),
        _btn("🇬🇧 English", "lang:en"),
        _btn("🇮🇷 فارسی",   "lang:fa"),
    ])


# ── Main menu ──────────────────────────────────────────────────────
def kb_main_menu(lang: str) -> InlineKeyboardMarkup:
    return _kb(
        [_btn(t("btn_buy_number", lang), "menu:buy"),
         _btn(t("btn_my_orders",  lang), "menu:orders")],
        [_btn(t("btn_balance",    lang), "menu:balance"),
         _btn(t("btn_add_balance",lang), "menu:add_balance")],
        [_btn(t("btn_change_lang",lang), "menu:lang"),
         _btn(t("btn_help",       lang), "menu:help")],
    )


# ── Service selection ──────────────────────────────────────────────
def kb_select_service(lang: str) -> InlineKeyboardMarkup:
    return _kb(
        [_btn(t("btn_telegram", lang), "svc:tg"),
         _btn(t("btn_whatsapp", lang), "svc:wa")],
        [_btn(t("btn_back", lang), "menu:main")],
    )


# ── WhatsApp server selection ──────────────────────────────────────
def kb_wa_servers(lang: str) -> InlineKeyboardMarkup:
    return _kb(
        [_btn(t("btn_wa_s1", lang), "wa:s1")],
        [_btn(t("btn_wa_s2", lang), "wa:s2")],
        [_btn(t("btn_refresh", lang), "wa:refresh"),
         _btn(t("btn_back",    lang), "menu:buy")],
    )


# ── Country list (paginated) ───────────────────────────────────────
def kb_countries(
    countries: List[Tuple[str, str, str, int]],
    page: int,
    service_key: str,
    lang: str,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    total_pages = max(1, math.ceil(len(countries) / COUNTRIES_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    chunk = countries[page * COUNTRIES_PER_PAGE: (page + 1) * COUNTRIES_PER_PAGE]

    for i in range(0, len(chunk), 2):
        row_items = chunk[i: i + 2]
        buttons = []
        for code, flag, name, count in row_items:
            label = f"{flag} {name} ({count})"
            buttons.append(_btn(label, f"buy:{service_key}:{code}"))
        kb.row(*buttons)

    # Pagination
    nav = []
    if page > 0:
        nav.append(_btn(t("btn_prev", lang), f"cpage:{service_key}:{page - 1}"))
    nav.append(_btn(t("page_indicator", lang, page=page + 1, total=total_pages), "noop"))
    if page < total_pages - 1:
        nav.append(_btn(t("btn_next", lang), f"cpage:{service_key}:{page + 1}"))
    if nav:
        kb.row(*nav)

    back_cb = "menu:buy" if service_key == "tg" else "svc:wa"
    kb.row(
        _btn(t("btn_refresh", lang), f"refresh_countries:{service_key}"),
        _btn(t("btn_back",    lang), back_cb),
    )
    return kb


# ── Active order ───────────────────────────────────────────────────
def kb_active_order(order_id: int, lang: str, show_cancel: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    if show_cancel:
        kb.row(_btn(t("btn_cancel_order", lang), f"cancel_order:{order_id}"))
    return kb


# ── Back button ────────────────────────────────────────────────────
def kb_back(lang: str, target: str = "menu:main") -> InlineKeyboardMarkup:
    return _kb([_btn(t("btn_back", lang), target)])


# ── Crypto deposit ─────────────────────────────────────────────────
def kb_charge_crypto(bep20_on: bool, trc20_on: bool, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    if bep20_on:
        kb.row(_btn("💎 USDT BEP20 (BSC)",  "crypto:bep20"))
    if trc20_on:
        kb.row(_btn("🟣 USDT TRC20 (TRON)", "crypto:trc20"))
    kb.row(_btn(t("btn_back", lang), "menu:main"))
    return kb


def kb_crypto_pay(network: str, lang: str) -> InlineKeyboardMarkup:
    return _kb(
        [_btn("✅ أرسلت المبلغ", f"crypto_sent:{network}")],
        [_btn("📋 نسخ العنوان",  f"crypto_copy:{network}")],
        [_btn(t("btn_back", lang), "menu:add_balance")],
    )


# ── Admin panel ────────────────────────────────────────────────────
def kb_admin(lang: str = "ar") -> InlineKeyboardMarkup:
    return _kb(
        [_btn("📊 الإحصائيات",    "admin:stats"),
         _btn("👥 المستخدمون",     "admin:users")],
        [_btn("💵 الأسعار",        "admin:pricing"),
         _btn("📢 بث رسالة",       "admin:broadcast")],
        [_btn("🔑 Durian API",      "admin:durian"),
         _btn("🔔 قناة الإشعارات", "admin:notif")],
        [_btn("💳 إعدادات الدفع",  "admin:crypto"),
         _btn("🧪 اختبار API",      "admin:test_api")],
        [_btn("💾 نسخ احتياطي",    "admin:backup")],
    )


def kb_admin_user(uid: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_text = "✅ رفع الحظر" if is_banned else "🚫 حظر"
    ban_cb   = f"admu:unban:{uid}" if is_banned else f"admu:ban:{uid}"
    return _kb(
        [_btn("➕ إضافة رصيد", f"admu:add:{uid}"),
         _btn("➖ خصم رصيد",   f"admu:deduct:{uid}")],
        [_btn(ban_text, ban_cb)],
        [_btn("🔙 رجوع", "admin:panel")],
    )


def kb_admin_crypto(bep20_on: bool, trc20_on: bool) -> InlineKeyboardMarkup:
    return _kb(
        [_btn("✅ BEP20 مُفعَّل" if bep20_on else "❌ BEP20 موقوف", "crypto_adm:toggle_bep20")],
        [_btn("📝 عنوان BEP20",   "crypto_adm:bep20_addr")],
        [_btn("💱 سعر BEP20",     "crypto_adm:bep20_rate")],
        [_btn("⬆️ حد أدنى BEP20", "crypto_adm:bep20_min")],
        [_btn("✅ TRC20 مُفعَّل" if trc20_on else "❌ TRC20 موقوف", "crypto_adm:toggle_trc20")],
        [_btn("📝 عنوان TRC20",   "crypto_adm:trc20_addr")],
        [_btn("🔑 TronGrid Key",  "crypto_adm:trc20_key")],
        [_btn("💱 سعر TRC20",     "crypto_adm:trc20_rate")],
        [_btn("⬆️ حد أدنى TRC20", "crypto_adm:trc20_min")],
        [_btn("🔙 رجوع",          "admin:panel")],
    )


# ── Notif channel ──────────────────────────────────────────────────
def kb_notif(ch_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(_btn("📌 تعيين معرف القناة", "notif:set_id"))
    kb.row(_btn("🔗 تعيين رابط القناة", "notif:set_link"))
    if ch_id:
        kb.row(_btn("🧪 إرسال تجريبي",    "notif:test"))
        kb.row(_btn("🔕 تعطيل الإشعارات", "notif:disable"))
    kb.row(_btn("🔙 رجوع", "admin:panel"))
    return kb


def kb_pricing() -> InlineKeyboardMarkup:
    return _kb(
        [_btn("✈️ سعر Telegram الموحد",    "price:base:tg")],
        [_btn("💬 سعر WhatsApp S1 الموحد", "price:base:wa_s1")],
        [_btn("💬 سعر WhatsApp S2 الموحد", "price:base:wa_s2")],
        [_btn("─────────────────",          "noop")],
        [_btn("🌍 أسعار دول Telegram",      "price:countries:tg")],
        [_btn("🌍 أسعار دول WhatsApp S1",   "price:countries:wa_s1")],
        [_btn("🌍 أسعار دول WhatsApp S2",   "price:countries:wa_s2")],
        [_btn("🔙 رجوع", "admin:panel")],
    )


def kb_country_prices(svc: str, has_prices: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(_btn("➕ إضافة/تعديل سعر دولة", f"price:set_country:{svc}"))
    if has_prices:
        kb.row(_btn("🗑 حذف سعر دولة", f"price:del_country:{svc}"))
    kb.row(_btn("🔙 رجوع", "admin:pricing"))
    return kb


def kb_durian() -> InlineKeyboardMarkup:
    return _kb(
        [_btn("👤 تغيير اسم المستخدم", "durian:set_name")],
        [_btn("🔑 تغيير API Key",      "durian:set_key")],
        [_btn("✈️ تغيير PID Telegram", "durian:set_pid_tg")],
        [_btn("💬 تغيير PID WA S1",    "durian:set_pid_wa1")],
        [_btn("💬 تغيير PID WA S2",    "durian:set_pid_wa2")],
        [_btn("🔙 رجوع", "admin:panel")],
    )
