"""keyboards.py — All InlineKeyboardMarkup builders"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from strings import t

COUNTRIES_PER_PAGE = 12   # 2 columns × 6 rows


# ── Language ───────────────────────────────────────────────────────
def kb_language() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang:ar"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
        InlineKeyboardButton(text="🇮🇷 فارسی",   callback_data="lang:fa"),
    )
    return b.as_markup()


# ── Main menu ──────────────────────────────────────────────────────
def kb_main_menu(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=t("btn_buy_number", lang),  callback_data="menu:buy"),
        InlineKeyboardButton(text=t("btn_my_orders",  lang),  callback_data="menu:orders"),
    )
    b.row(
        InlineKeyboardButton(text=t("btn_balance",    lang),  callback_data="menu:balance"),
        InlineKeyboardButton(text=t("btn_add_balance",lang),  callback_data="menu:add_balance"),
    )
    b.row(
        InlineKeyboardButton(text=t("btn_change_lang",lang),  callback_data="menu:lang"),
        InlineKeyboardButton(text=t("btn_help",       lang),  callback_data="menu:help"),
    )
    return b.as_markup()


# ── Service selection: Telegram / WhatsApp ─────────────────────────
def kb_select_service(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=t("btn_telegram", lang), callback_data="svc:tg"),
        InlineKeyboardButton(text=t("btn_whatsapp", lang), callback_data="svc:wa"),
    )
    b.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data="menu:main"))
    return b.as_markup()


# ── WhatsApp server selection ──────────────────────────────────────
def kb_wa_servers(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t("btn_wa_s1", lang), callback_data="wa:s1"))
    b.row(InlineKeyboardButton(text=t("btn_wa_s2", lang), callback_data="wa:s2"))
    b.row(
        InlineKeyboardButton(text=t("btn_refresh", lang), callback_data="wa:refresh"),
        InlineKeyboardButton(text=t("btn_back",    lang), callback_data="menu:buy"),
    )
    return b.as_markup()


# ── Country list (paginated, with count) ───────────────────────────
def kb_countries(
    countries: List[Tuple[str, str, str, int]],  # (code, flag, name, count)
    page: int,
    service_key: str,   # "tg" | "wa_s1" | "wa_s2"
    lang: str,
) -> InlineKeyboardMarkup:
    """
    Builds paginated country buttons.
    Button label: {flag} {name} ({count})
    callback_data: buy:{service_key}:{code}
    """
    b = InlineKeyboardBuilder()
    total_pages = max(1, math.ceil(len(countries) / COUNTRIES_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    chunk = countries[page * COUNTRIES_PER_PAGE: (page + 1) * COUNTRIES_PER_PAGE]

    for i in range(0, len(chunk), 2):
        row_items = chunk[i: i + 2]
        buttons   = []
        for code, flag, name, count in row_items:
            label = f"{flag} {name} ({count})"
            buttons.append(InlineKeyboardButton(
                text=label,
                callback_data=f"buy:{service_key}:{code}",
            ))
        b.row(*buttons)

    # Pagination row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text=t("btn_prev", lang),
            callback_data=f"cpage:{service_key}:{page - 1}",
        ))
    nav.append(InlineKeyboardButton(
        text=t("page_indicator", lang, page=page + 1, total=total_pages),
        callback_data="noop",
    ))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text=t("btn_next", lang),
            callback_data=f"cpage:{service_key}:{page + 1}",
        ))
    if nav:
        b.row(*nav)

    # Refresh + Back
    back_cb = "menu:buy" if service_key == "tg" else "svc:wa"
    b.row(
        InlineKeyboardButton(
            text=t("btn_refresh", lang),
            callback_data=f"refresh_countries:{service_key}",
        ),
        InlineKeyboardButton(text=t("btn_back", lang), callback_data=back_cb),
    )
    return b.as_markup()


# ── Active order (cancel appears after delay) ──────────────────────
def kb_active_order(order_id: int, lang: str, show_cancel: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if show_cancel:
        b.row(InlineKeyboardButton(
            text=t("btn_cancel_order", lang),
            callback_data=f"cancel_order:{order_id}",
        ))
    return b.as_markup()


# ── Back button ────────────────────────────────────────────────────
def kb_back(lang: str, target: str = "menu:main") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data=target))
    return b.as_markup()


# ── Crypto deposit ─────────────────────────────────────────────────
def kb_charge_crypto(bep20_on: bool, trc20_on: bool, lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if bep20_on:
        b.row(InlineKeyboardButton(text="💎 USDT BEP20 (BSC)", callback_data="crypto:bep20"))
    if trc20_on:
        b.row(InlineKeyboardButton(text="🟣 USDT TRC20 (TRON)", callback_data="crypto:trc20"))
    b.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data="menu:main"))
    return b.as_markup()


def kb_crypto_pay(network: str, lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Sent", callback_data=f"crypto_sent:{network}"))
    b.row(InlineKeyboardButton(text="📋 Copy address", callback_data=f"crypto_copy:{network}"))
    b.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data="menu:add_balance"))
    return b.as_markup()


# ── Admin panel ────────────────────────────────────────────────────
def kb_admin(lang: str = "ar") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 الإحصائيات",       callback_data="admin:stats"),
        InlineKeyboardButton(text="👥 المستخدمون",        callback_data="admin:users"),
    )
    b.row(
        InlineKeyboardButton(text="💵 الأسعار",           callback_data="admin:pricing"),
        InlineKeyboardButton(text="📢 بث رسالة",          callback_data="admin:broadcast"),
    )
    b.row(
        InlineKeyboardButton(text="🔑 Durian API",         callback_data="admin:durian"),
        InlineKeyboardButton(text="🔔 قناة الإشعارات",    callback_data="admin:notif"),
    )
    b.row(
        InlineKeyboardButton(text="💳 إعدادات الدفع",     callback_data="admin:crypto"),
        InlineKeyboardButton(text="🧪 اختبار API",         callback_data="admin:test_api"),
    )
    b.row(
        InlineKeyboardButton(text="💾 نسخ احتياطي",        callback_data="admin:backup"),
    )
    return b.as_markup()


def kb_admin_user(uid: int, is_banned: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➕ إضافة رصيد",  callback_data=f"admu:add:{uid}"),
        InlineKeyboardButton(text="➖ خصم رصيد",    callback_data=f"admu:deduct:{uid}"),
    )
    ban_text = "✅ رفع الحظر" if is_banned else "🚫 حظر"
    ban_cb   = f"admu:unban:{uid}" if is_banned else f"admu:ban:{uid}"
    b.row(InlineKeyboardButton(text=ban_text, callback_data=ban_cb))
    b.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin:panel"))
    return b.as_markup()


def kb_admin_crypto(bep20_on: bool, trc20_on: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="✅ BEP20 مُفعَّل" if bep20_on else "❌ BEP20 موقوف",
        callback_data="crypto_adm:toggle_bep20",
    ))
    b.row(InlineKeyboardButton(text="📝 عنوان BEP20",   callback_data="crypto_adm:bep20_addr"))
    b.row(InlineKeyboardButton(text="💱 سعر BEP20",     callback_data="crypto_adm:bep20_rate"))
    b.row(InlineKeyboardButton(text="⬆️ حد أدنى BEP20",  callback_data="crypto_adm:bep20_min"))
    b.row(InlineKeyboardButton(
        text="✅ TRC20 مُفعَّل" if trc20_on else "❌ TRC20 موقوف",
        callback_data="crypto_adm:toggle_trc20",
    ))
    b.row(InlineKeyboardButton(text="📝 عنوان TRC20",   callback_data="crypto_adm:trc20_addr"))
    b.row(InlineKeyboardButton(text="🔑 TronGrid Key",  callback_data="crypto_adm:trc20_key"))
    b.row(InlineKeyboardButton(text="💱 سعر TRC20",     callback_data="crypto_adm:trc20_rate"))
    b.row(InlineKeyboardButton(text="⬆️ حد أدنى TRC20",  callback_data="crypto_adm:trc20_min"))
    b.row(InlineKeyboardButton(text="🔙 رجوع",          callback_data="admin:panel"))
    return b.as_markup()
