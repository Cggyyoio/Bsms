"""strings.py — AR / EN / FA translation system"""
from __future__ import annotations
from typing import Any, Dict

STRINGS: Dict[str, Dict[str, str]] = {

    # ── Language ───────────────────────────────────────────────────
    "choose_language": {
        "en": "🌐 Please choose your language:",
        "ar": "🌐 يرجى اختيار لغتك:",
        "fa": "🌐 لطفاً زبان خود را انتخاب کنید:",
    },
    "lang_set": {
        "en": "✅ Language set to English.",
        "ar": "✅ تم تعيين اللغة إلى العربية.",
        "fa": "✅ زبان به فارسی تنظیم شد.",
    },

    # ── Main menu ──────────────────────────────────────────────────
    "main_menu": {
        "en": "👋 Welcome, <b>{name}</b>!\n\n💰 Balance: <code>${balance:.2f}</code>\n\nChoose an option:",
        "ar": "👋 مرحباً، <b>{name}</b>!\n\n💰 رصيدك: <code>${balance:.2f}</code>\n\nاختر خياراً:",
        "fa": "👋 خوش آمدید، <b>{name}</b>!\n\n💰 موجودی: <code>${balance:.2f}</code>\n\nیک گزینه انتخاب کنید:",
    },

    # ── Buttons ────────────────────────────────────────────────────
    "btn_buy_number":  {"en": "📲 Buy Number",   "ar": "📲 شراء رقم",   "fa": "📲 خرید شماره"},
    "btn_my_orders":   {"en": "📦 My Orders",    "ar": "📦 طلباتي",    "fa": "📦 سفارش‌ها"},
    "btn_balance":     {"en": "💰 Balance",       "ar": "💰 الرصيد",    "fa": "💰 موجودی"},
    "btn_add_balance": {"en": "➕ Add Balance",   "ar": "➕ شحن رصيد",  "fa": "➕ شارژ کیف‌پول"},
    "btn_change_lang": {"en": "🌐 Language",      "ar": "🌐 اللغة",     "fa": "🌐 زبان"},
    "btn_help":        {"en": "❓ Help",           "ar": "❓ المساعدة",  "fa": "❓ راهنما"},
    "btn_back":        {"en": "🔙 Back",          "ar": "🔙 رجوع",     "fa": "🔙 بازگشت"},
    "btn_cancel_order":{"en": "❌ Cancel Order",  "ar": "❌ إلغاء الطلب","fa": "❌ لغو سفارش"},
    "btn_refresh":     {"en": "🔄 Refresh",       "ar": "🔄 تحديث",    "fa": "🔄 بازنشانی"},

    # ── Service selection ──────────────────────────────────────────
    "select_service": {
        "en": "📱 <b>Choose a service:</b>",
        "ar": "📱 <b>اختر الخدمة:</b>",
        "fa": "📱 <b>سرویس را انتخاب کنید:</b>",
    },
    "btn_telegram": {"en": "✈️ Telegram", "ar": "✈️ تيليغرام", "fa": "✈️ تلگرام"},
    "btn_whatsapp": {"en": "💬 WhatsApp", "ar": "💬 واتساب",    "fa": "💬 واتساپ"},

    # ── WhatsApp server ────────────────────────────────────────────
    "select_wa_server": {
        "en": "💬 <b>WhatsApp — Choose a server:</b>",
        "ar": "💬 <b>واتساب — اختر السيرفر:</b>",
        "fa": "💬 <b>واتساپ — سرور را انتخاب کنید:</b>",
    },
    "btn_wa_s1": {"en": "Server 1 (0107)", "ar": "سيرفر 1 (0107)", "fa": "سرور ۱ (0107)"},
    "btn_wa_s2": {"en": "Server 2 (0528)", "ar": "سيرفر 2 (0528)", "fa": "سرور ۲ (0528)"},

    # ── Country selection ──────────────────────────────────────────
    "select_country_tg": {
        "en": "✈️ <b>Telegram — Choose a country:</b>\n<i>🔢 = available numbers</i>",
        "ar": "✈️ <b>تيليغرام — اختر الدولة:</b>\n<i>🔢 = عدد الأرقام المتاحة</i>",
        "fa": "✈️ <b>تلگرام — کشور را انتخاب کنید:</b>\n<i>🔢 = شماره‌های موجود</i>",
    },
    "select_country_wa": {
        "en": "💬 <b>WhatsApp — Choose a country:</b>\n<i>🔢 = available numbers</i>",
        "ar": "💬 <b>واتساب — اختر الدولة:</b>\n<i>🔢 = عدد الأرقام المتاحة</i>",
        "fa": "💬 <b>واتساپ — کشور را انتخاب کنید:</b>\n<i>🔢 = شماره‌های موجود</i>",
    },
    "no_countries": {
        "en": "⚠️ No numbers available right now. Try again later.",
        "ar": "⚠️ لا توجد أرقام متاحة الآن. حاول لاحقاً.",
        "fa": "⚠️ در حال حاضر شماره‌ای موجود نیست.",
    },
    "loading_countries": {
        "en": "⏳ Loading available countries...",
        "ar": "⏳ جارٍ تحميل الدول المتاحة...",
        "fa": "⏳ در حال بارگذاری کشورها...",
    },
    "page_indicator": {
        "en": "📄 {page}/{total}",
        "ar": "📄 {page}/{total}",
        "fa": "📄 {page}/{total}",
    },
    "btn_prev": {"en": "◀️", "ar": "◀️", "fa": "◀️"},
    "btn_next": {"en": "▶️", "ar": "▶️", "fa": "▶️"},

    # ── Purchase flow ──────────────────────────────────────────────
    "insufficient_balance": {
        "en": "❌ Insufficient balance.\nNeed: <code>${needed:.2f}</code> | Have: <code>${have:.2f}</code>",
        "ar": "❌ رصيد غير كافٍ.\nالمطلوب: <code>${needed:.2f}</code> | لديك: <code>${have:.2f}</code>",
        "fa": "❌ موجودی کافی نیست.\nنیاز: <code>${needed:.2f}</code> | دارید: <code>${have:.2f}</code>",
    },
    "buying_number": {
        "en": "⏳ <b>Buying number...</b>\nService: {service} {flag} {country}\n💰 Price: <code>${price:.2f}</code>\nPlease wait.",
        "ar": "⏳ <b>جارٍ شراء الرقم...</b>\nالخدمة: {service} {flag} {country}\n💰 السعر: <code>${price:.2f}</code>\nيرجى الانتظار.",
        "fa": "⏳ <b>در حال خرید شماره...</b>\nسرویس: {service} {flag} {country}\n💰 قیمت: <code>${price:.2f}</code>\nلطفاً صبر کنید.",
    },
    "buy_failed_no_numbers": {
        "en": "⚠️ No numbers available for this country right now.\nTry another country.",
        "ar": "⚠️ لا توجد أرقام متاحة لهذه الدولة الآن.\nجرب دولة أخرى.",
        "fa": "⚠️ شماره‌ای برای این کشور موجود نیست.\nکشور دیگری انتخاب کنید.",
    },
    "buy_failed_balance": {
        "en": "❌ Insufficient balance in provider account.\nContact admin.",
        "ar": "❌ رصيد المزود غير كافٍ.\nتواصل مع الأدمن.",
        "fa": "❌ موجودی سرویس‌دهنده کافی نیست.\nبا ادمین تماس بگیرید.",
    },
    "buy_failed_generic": {
        "en": "❌ Failed to get number. Try again.",
        "ar": "❌ فشل في الحصول على الرقم. حاول مجدداً.",
        "fa": "❌ دریافت شماره ناموفق بود. دوباره تلاش کنید.",
    },
    "already_has_order": {
        "en": "⚠️ You already have an active order. Wait for it to finish or cancel it.",
        "ar": "⚠️ لديك طلب نشط. انتظر حتى ينتهي أو ألغِه.",
        "fa": "⚠️ سفارش فعالی دارید. صبر کنید یا آن را لغو کنید.",
    },

    # ── Active order ───────────────────────────────────────────────
    "order_active": {
        "en": (
            "✅ <b>Number ready!</b>\n\n"
            "📞 Number: <code>{number}</code>\n"
            "🛎 Service: {service}\n"
            "{country_line}"
            "💰 Price: <code>${price:.2f}</code>\n\n"
            "⏳ Waiting for SMS code...\n"
            "<i>Code will appear here automatically.</i>"
        ),
        "ar": (
            "✅ <b>الرقم جاهز!</b>\n\n"
            "📞 الرقم: <code>{number}</code>\n"
            "🛎 الخدمة: {service}\n"
            "{country_line}"
            "💰 السعر: <code>${price:.2f}</code>\n\n"
            "⏳ في انتظار كود التحقق...\n"
            "<i>سيظهر الكود هنا تلقائياً.</i>"
        ),
        "fa": (
            "✅ <b>شماره آماده است!</b>\n\n"
            "📞 شماره: <code>{number}</code>\n"
            "🛎 سرویس: {service}\n"
            "{country_line}"
            "💰 قیمت: <code>${price:.2f}</code>\n\n"
            "⏳ در انتظار کد تأیید...\n"
            "<i>کد به صورت خودکار نمایش داده می‌شود.</i>"
        ),
    },
    "order_country_line": {
        "en": "🌍 Country: {flag} {country}\n",
        "ar": "🌍 الدولة: {flag} {country}\n",
        "fa": "🌍 کشور: {flag} {country}\n",
    },

    # ── SMS received ───────────────────────────────────────────────
    "sms_received": {
        "en": (
            "🎉 <b>Code received!</b>\n\n"
            "📞 Number: <code>{number}</code>\n"
            "🔑 <b>Code: <code>{code}</code></b>\n"
            "📝 Message: <i>{text}</i>"
        ),
        "ar": (
            "🎉 <b>تم استلام الكود!</b>\n\n"
            "📞 الرقم: <code>{number}</code>\n"
            "🔑 <b>الكود: <code>{code}</code></b>\n"
            "📝 الرسالة: <i>{text}</i>"
        ),
        "fa": (
            "🎉 <b>کد دریافت شد!</b>\n\n"
            "📞 شماره: <code>{number}</code>\n"
            "🔑 <b>کد: <code>{code}</code></b>\n"
            "📝 پیام: <i>{text}</i>"
        ),
    },

    # ── Timeout / Cancel ───────────────────────────────────────────
    "order_timeout": {
        "en": "⏰ <b>Order expired</b>\nNo code received for order <code>#{order_id}</code>.\n💰 <code>${refund:.2f}</code> refunded.",
        "ar": "⏰ <b>انتهت مدة الطلب</b>\nلم يصل كود للطلب <code>#{order_id}</code>.\n💰 تم استرداد <code>${refund:.2f}</code>.",
        "fa": "⏰ <b>سفارش منقضی شد</b>\nکدی برای سفارش <code>#{order_id}</code> دریافت نشد.\n💰 <code>${refund:.2f}</code> بازگردانده شد.",
    },
    "order_cancelled": {
        "en": "❌ Order <code>#{order_id}</code> cancelled.\n💰 <code>${refund:.2f}</code> refunded.",
        "ar": "❌ تم إلغاء الطلب <code>#{order_id}</code>.\n💰 تم استرداد <code>${refund:.2f}</code>.",
        "fa": "❌ سفارش <code>#{order_id}</code> لغو شد.\n💰 <code>${refund:.2f}</code> بازگردانده شد.",
    },
    "cancel_too_early": {
        "en": "⏳ You can cancel after {remaining} seconds.",
        "ar": "⏳ يمكنك الإلغاء بعد {remaining} ثانية.",
        "fa": "⏳ پس از {remaining} ثانیه می‌توانید لغو کنید.",
    },

    # ── Retry message ──────────────────────────────────────────────
    "retrying_number": {
        "en": "🔁 <b>Retrying with a new number...</b>",
        "ar": "🔁 <b>جارٍ المحاولة برقم جديد...</b>",
        "fa": "🔁 <b>تلاش مجدد با شماره جدید...</b>",
    },

    # ── My orders ──────────────────────────────────────────────────
    "my_orders_empty": {
        "en": "📭 No orders yet.",
        "ar": "📭 لا توجد طلبات بعد.",
        "fa": "📭 هنوز سفارشی ندارید.",
    },
    "my_orders_header": {
        "en": "📦 <b>Your Orders ({count})</b>",
        "ar": "📦 <b>طلباتك ({count})</b>",
        "fa": "📦 <b>سفارش‌های شما ({count})</b>",
    },

    # ── Balance & Add ──────────────────────────────────────────────
    "balance_info": {
        "en": "💰 Your balance: <code>${balance:.2f}</code>",
        "ar": "💰 رصيدك: <code>${balance:.2f}</code>",
        "fa": "💰 موجودی شما: <code>${balance:.2f}</code>",
    },
    "add_balance_select": {
        "en": "➕ <b>Add Balance</b>\n\nChoose payment method:",
        "ar": "➕ <b>شحن الرصيد</b>\n\nاختر طريقة الدفع:",
        "fa": "➕ <b>افزودن موجودی</b>\n\nروش پرداخت را انتخاب کنید:",
    },
    "no_payment_methods": {
        "en": "⛔ No payment methods available. Contact admin.",
        "ar": "⛔ لا توجد طرق دفع متاحة. تواصل مع الأدمن.",
        "fa": "⛔ روش پرداختی موجود نیست. با ادمین تماس بگیرید.",
    },

    # ── Help ───────────────────────────────────────────────────────
    "help_text": {
        "en": (
            "❓ <b>How it works:</b>\n\n"
            "1️⃣ Press 📲 Buy Number\n"
            "2️⃣ Choose Telegram or WhatsApp\n"
            "3️⃣ Select a country\n"
            "4️⃣ Get your number & wait for the code\n\n"
            "⏱ Code timeout: 5 minutes\n"
            "🔄 Auto-refund if no code arrives\n\n"
            "❓ Contact admin for support."
        ),
        "ar": (
            "❓ <b>كيف يعمل البوت:</b>\n\n"
            "1️⃣ اضغط 📲 شراء رقم\n"
            "2️⃣ اختر تيليغرام أو واتساب\n"
            "3️⃣ اختر الدولة\n"
            "4️⃣ استلم رقمك وانتظر الكود\n\n"
            "⏱ مهلة الكود: 5 دقائق\n"
            "🔄 استرداد تلقائي إذا لم يصل الكود\n\n"
            "❓ تواصل مع الأدمن للمساعدة."
        ),
        "fa": (
            "❓ <b>نحوه استفاده:</b>\n\n"
            "1️⃣ روی 📲 خرید شماره بزنید\n"
            "2️⃣ تلگرام یا واتساپ انتخاب کنید\n"
            "3️⃣ کشور را انتخاب کنید\n"
            "4️⃣ شماره دریافت کنید و منتظر کد باشید\n\n"
            "⏱ مهلت کد: ۵ دقیقه\n"
            "🔄 در صورت عدم دریافت کد، بازپرداخت خودکار\n\n"
            "❓ برای پشتیبانی با ادمین تماس بگیرید."
        ),
    },

    # ── Errors ─────────────────────────────────────────────────────
    "error_generic": {
        "en": "⚠️ An error occurred. Please try again.",
        "ar": "⚠️ حدث خطأ. حاول مجدداً.",
        "fa": "⚠️ خطایی رخ داد. دوباره تلاش کنید.",
    },
    "banned": {
        "en": "🚫 You are banned from this bot.",
        "ar": "🚫 أنت محظور من هذا البوت.",
        "fa": "🚫 شما از این ربات مسدود شده‌اید.",
    },

    # ── Admin panel ────────────────────────────────────────────────
    "admin_panel": {
        "en": (
            "🛡 <b>Admin Panel</b>\n\n"
            "📊 <b>Today:</b>\n"
            "  📦 Orders: <code>{orders_today}</code>\n"
            "  💵 Profit: <code>${profit_today:.2f}</code>\n\n"
            "📈 <b>Total:</b>\n"
            "  👥 Users: <code>{users}</code>\n"
            "  📦 Orders: <code>{orders_total}</code>\n"
            "  ✅ Completed: <code>{completed}</code>\n"
            "  💵 Profit: <code>${profit_total:.2f}</code>\n\n"
            "🏆 Top service: <code>{top_service}</code>\n"
            "🌍 Top country: <code>{top_country}</code>\n"
            "💰 Durian balance: <code>${balance:.2f}</code>"
        ),
        "ar": (
            "🛡 <b>لوحة الإدارة</b>\n\n"
            "📊 <b>اليوم:</b>\n"
            "  📦 الطلبات: <code>{orders_today}</code>\n"
            "  💵 الأرباح: <code>${profit_today:.2f}</code>\n\n"
            "📈 <b>الإجمالي:</b>\n"
            "  👥 المستخدمون: <code>{users}</code>\n"
            "  📦 الطلبات: <code>{orders_total}</code>\n"
            "  ✅ مكتملة: <code>{completed}</code>\n"
            "  💵 الأرباح: <code>${profit_total:.2f}</code>\n\n"
            "🏆 الخدمة الأعلى: <code>{top_service}</code>\n"
            "🌍 الدولة الأعلى: <code>{top_country}</code>\n"
            "💰 رصيد Durian: <code>${balance:.2f}</code>"
        ),
        "fa": (
            "🛡 <b>پنل ادمین</b>\n\n"
            "📊 <b>امروز:</b>\n"
            "  📦 سفارشات: <code>{orders_today}</code>\n"
            "  💵 سود: <code>${profit_today:.2f}</code>\n\n"
            "📈 <b>کل:</b>\n"
            "  👥 کاربران: <code>{users}</code>\n"
            "  📦 سفارشات: <code>{orders_total}</code>\n"
            "  ✅ تکمیل شده: <code>{completed}</code>\n"
            "  💵 سود: <code>${profit_total:.2f}</code>\n\n"
            "🏆 برترین سرویس: <code>{top_service}</code>\n"
            "🌍 برترین کشور: <code>{top_country}</code>\n"
            "💰 موجودی Durian: <code>${balance:.2f}</code>"
        ),
    },
    "admin_only": {
        "en": "🚫 Admin only.",
        "ar": "🚫 للأدمن فقط.",
        "fa": "🚫 فقط ادمین.",
    },
    "admin_search_user":   {"en": "🔍 Send user ID or username:", "ar": "🔍 أرسل معرف أو اسم المستخدم:", "fa": "🔍 شناسه یا نام کاربری را ارسال کنید:"},
    "user_not_found":      {"en": "❌ User not found.",         "ar": "❌ المستخدم غير موجود.",       "fa": "❌ کاربر یافت نشد."},
    "invalid_input":       {"en": "❌ Invalid input.",          "ar": "❌ إدخال غير صحيح.",           "fa": "❌ ورودی نامعتبر."},
    "admin_balance_updated":{"en":"✅ Balance updated: <code>${balance:.2f}</code>","ar":"✅ تم تحديث الرصيد: <code>${balance:.2f}</code>","fa":"✅ موجودی به‌روز شد: <code>${balance:.2f}</code>"},
    "admin_user_banned":   {"en": "🚫 User <code>{uid}</code> banned.",   "ar": "🚫 تم حظر <code>{uid}</code>.",   "fa": "🚫 کاربر <code>{uid}</code> مسدود شد."},
    "admin_user_unbanned": {"en": "✅ User <code>{uid}</code> unbanned.", "ar": "✅ تم رفع حظر <code>{uid}</code>.", "fa": "✅ مسدودی <code>{uid}</code> رفع شد."},
    "admin_broadcast_prompt":{"en":"📢 Send message (text/photo) to broadcast:", "ar":"📢 أرسل الرسالة للبث:", "fa":"📢 پیام را برای ارسال همگانی بفرستید:"},
    "admin_broadcast_done":{"en":"✅ Sent to <code>{count}</code> users.","ar":"✅ أُرسل إلى <code>{count}</code> مستخدم.","fa":"✅ به <code>{count}</code> کاربر ارسال شد."},
    "admin_enter_amount":  {"en":"💵 Enter amount:", "ar":"💵 أدخل المبلغ:", "fa":"💵 مبلغ را وارد کنید:"},
    "admin_margin_updated":{"en":"✅ Margin: <code>{margin}%</code>","ar":"✅ الهامش: <code>{margin}%</code>","fa":"✅ حاشیه: <code>{margin}%</code>"},
    "admin_creds_updated": {"en":"✅ Credentials updated and reloaded.","ar":"✅ تم تحديث البيانات وإعادة التحميل.","fa":"✅ اطلاعات به‌روز و مجدداً بارگذاری شد."},
    "admin_price_updated": {"en":"✅ Price updated.","ar":"✅ تم تحديث السعر.","fa":"✅ قیمت به‌روز شد."},
    "admin_user_info": {
        "en": "👤 <b>User Info</b>\nID: <code>{uid}</code>\nName: {name}\nBalance: <code>${balance:.2f}</code>\nOrders: {orders}\nBanned: {banned}",
        "ar": "👤 <b>معلومات المستخدم</b>\nالمعرف: <code>{uid}</code>\nالاسم: {name}\nالرصيد: <code>${balance:.2f}</code>\nالطلبات: {orders}\nمحظور: {banned}",
        "fa": "👤 <b>اطلاعات کاربر</b>\nشناسه: <code>{uid}</code>\nنام: {name}\nموجودی: <code>${balance:.2f}</code>\nسفارشات: {orders}\nمسدود: {banned}",
    },

    # ── Crypto deposit ─────────────────────────────────────────────
    "pay_page": {
        "en": (
            "💳 <b>Add Balance — {network}</b>\n\n"
            "Send USDT to this address:\n"
            "<code>{address}</code>\n\n"
            "Network: <b>{network}</b>\n"
            "Min: <b>{min_usdt} USDT</b>\n"
            "Rate: 1 USDT = <b>${rate}</b>\n\n"
            "After sending, press <b>Sent ✅</b>."
        ),
        "ar": (
            "💳 <b>شحن الرصيد — {network}</b>\n\n"
            "أرسل USDT إلى هذا العنوان:\n"
            "<code>{address}</code>\n\n"
            "الشبكة: <b>{network}</b>\n"
            "الحد الأدنى: <b>{min_usdt} USDT</b>\n"
            "سعر الصرف: 1 USDT = <b>${rate}</b>\n\n"
            "بعد الإرسال، اضغط <b>أرسلت ✅</b>."
        ),
        "fa": (
            "💳 <b>شارژ کیف‌پول — {network}</b>\n\n"
            "USDT را به این آدرس بفرستید:\n"
            "<code>{address}</code>\n\n"
            "شبکه: <b>{network}</b>\n"
            "حداقل: <b>{min_usdt} USDT</b>\n"
            "نرخ: 1 USDT = <b>${rate}</b>\n\n"
            "پس از ارسال، <b>ارسال کردم ✅</b> را بزنید."
        ),
    },
    "pay_send_txid": {
        "en": "📋 Send your Transaction ID (TxID):",
        "ar": "📋 أرسل معرف المعاملة (TxID):",
        "fa": "📋 شناسه تراکنش (TxID) را ارسال کنید:",
    },
    "pay_success": {
        "en": "✅ <b>Balance charged!</b>\n💵 Received: <b>{amount} USDT</b>\n💰 Added: <code>${credit:.2f}</code>\n💳 New balance: <code>${balance:.2f}</code>",
        "ar": "✅ <b>تم شحن الرصيد!</b>\n💵 المُستلَم: <b>{amount} USDT</b>\n💰 المضاف: <code>${credit:.2f}</code>\n💳 الرصيد الجديد: <code>${balance:.2f}</code>",
        "fa": "✅ <b>موجودی شارژ شد!</b>\n💵 دریافتی: <b>{amount} USDT</b>\n💰 افزوده شد: <code>${credit:.2f}</code>\n💳 موجودی جدید: <code>${balance:.2f}</code>",
    },
}


def t(key: str, lang: str, **kwargs: Any) -> str:
    entry = STRINGS.get(key, {})
    text  = entry.get(lang) or entry.get("ar") or entry.get("en") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
