"""
pricing.py — Pricing Manager
━━━━━━━━━━━━━━━━━━━━━━━━━━━
هيكل الأسعار:
  Telegram:
    └── سعر موحد (price_tg)             افتراضي: 0.25
    └── سعر خاص بالدولة (price_tg_{cc}) إن وُجد يأخذ الأولوية

  WhatsApp Server 1:
    └── سعر موحد (price_wa_s1)           افتراضي: 0.35
    └── سعر خاص بالدولة (price_wa_s1_{cc}) إن وُجد يأخذ الأولوية

  WhatsApp Server 2:
    └── سعر موحد (price_wa_s2)           افتراضي: 0.40
    └── سعر خاص بالدولة (price_wa_s2_{cc}) إن وُجد يأخذ الأولوية

أولوية التسعير:
  سعر الدولة الخاص > السعر الموحد للخدمة
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ── المفاتيح في settings ─────────────────────────────────────────
PRICE_KEYS = {
    "tg":    "price_tg",
    "wa_s1": "price_wa_s1",
    "wa_s2": "price_wa_s2",
}

DEFAULT_PRICES = {
    "tg":    0.25,
    "wa_s1": 0.35,
    "wa_s2": 0.40,
}

COUNTRY_PRICE_KEY = "price_{svc}_{cc}"  # مثال: price_tg_ru


class PricingManager:
    """
    يدير نظام التسعير بالكامل.
    يقرأ ويكتب مباشرة في settings بقاعدة البيانات.
    """

    def __init__(self):
        self._db = None

    def init(self, db) -> None:
        self._db = db

    # ══════════════════════════════════════════════════════
    #  الحصول على السعر
    # ══════════════════════════════════════════════════════
    async def get_price(self, service_key: str, country_code: str = "") -> float:
        """
        يرجع السعر المناسب حسب الأولوية:
        1. سعر الدولة الخاص (إن وُجد)
        2. السعر الموحد للخدمة
        """
        # 1. سعر الدولة الخاص
        if country_code:
            cc  = country_code.lower().strip()
            key = COUNTRY_PRICE_KEY.format(svc=service_key, cc=cc)
            val = await self._db.get_setting(key)
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass

        # 2. السعر الموحد
        base_key = PRICE_KEYS.get(service_key, "price_tg")
        val      = await self._db.get_setting(base_key)
        if val:
            try:
                return float(val)
            except ValueError:
                pass

        # 3. الافتراضي
        return DEFAULT_PRICES.get(service_key, 0.25)

    # ══════════════════════════════════════════════════════
    #  الأسعار الموحدة
    # ══════════════════════════════════════════════════════
    async def get_base_prices(self) -> Dict[str, float]:
        """يرجع الأسعار الموحدة للخدمات الثلاث."""
        result = {}
        for svc, db_key in PRICE_KEYS.items():
            val = await self._db.get_setting(db_key)
            try:
                result[svc] = float(val) if val else DEFAULT_PRICES[svc]
            except ValueError:
                result[svc] = DEFAULT_PRICES[svc]
        return result

    async def set_base_price(self, service_key: str, price: float) -> None:
        """يعدّل السعر الموحد للخدمة."""
        db_key = PRICE_KEYS.get(service_key)
        if db_key:
            await self._db.set_setting(db_key, str(round(price, 4)))
            logger.info("Base price updated: %s = %.4f", service_key, price)

    # ══════════════════════════════════════════════════════
    #  أسعار الدول الخاصة
    # ══════════════════════════════════════════════════════
    async def get_country_price(
        self, service_key: str, country_code: str
    ) -> Optional[float]:
        """يرجع السعر الخاص للدولة إن وُجد، وإلا None."""
        key = COUNTRY_PRICE_KEY.format(svc=service_key, cc=country_code.lower())
        val = await self._db.get_setting(key)
        if val:
            try:
                return float(val)
            except ValueError:
                pass
        return None

    async def set_country_price(
        self, service_key: str, country_code: str, price: float
    ) -> None:
        """يضبط سعراً خاصاً لدولة في خدمة معينة."""
        key = COUNTRY_PRICE_KEY.format(svc=service_key, cc=country_code.lower())
        await self._db.set_setting(key, str(round(price, 4)))
        logger.info("Country price set: %s/%s = %.4f", service_key, country_code, price)

    async def delete_country_price(
        self, service_key: str, country_code: str
    ) -> None:
        """يحذف السعر الخاص للدولة (يعود للسعر الموحد)."""
        key = COUNTRY_PRICE_KEY.format(svc=service_key, cc=country_code.lower())
        await self._db.set_setting(key, "")
        logger.info("Country price deleted: %s/%s", service_key, country_code)

    async def get_all_country_prices(self, service_key: str) -> Dict[str, float]:
        """يرجع كل الأسعار الخاصة لخدمة معينة."""
        prefix = f"price_{service_key}_"
        rows   = await self._db.fetchall(
            "SELECT key, value FROM settings WHERE key LIKE ? AND value != ''",
            (f"{prefix}%",),
        )
        result = {}
        for row in rows:
            cc = row["key"].replace(prefix, "")
            if len(cc) >= 2:   # تجاهل المفاتيح غير الصحيحة
                try:
                    result[cc] = float(row["value"])
                except ValueError:
                    pass
        return result

    # ══════════════════════════════════════════════════════
    #  Seed defaults في قاعدة البيانات
    # ══════════════════════════════════════════════════════
    async def seed_defaults(self) -> None:
        for svc, key in PRICE_KEYS.items():
            existing = await self._db.get_setting(key)
            if not existing:
                await self._db.set_setting(key, str(DEFAULT_PRICES[svc]))
        logger.info("Pricing defaults seeded.")


# Singleton
pricing = PricingManager()
