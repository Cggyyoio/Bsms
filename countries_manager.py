"""
countries_manager.py — إدارة ذكية للدول
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• تحميل countries.json مرة واحدة في الذاكرة
• ترتيب الدول بناءً على الوقت المحلي وساعات الذروة (9ص-9م)
• عرض عدد الأرقام المتاحة لكل دولة
• قائمة الدول الأكثر مبيعاً من قاعدة البيانات
• دعم خدمتين فقط: Telegram (tg) و WhatsApp (wa)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── خريطة الخدمات المسموحة فقط ────────────────
ALLOWED_SERVICES = {
    "tg": {"icon": "✈️", "name_en": "Telegram", "name_ar": "تيليغرام", "name_fa": "تلگرام",
           "codes": ["tg", "telegram"]},
    "wa": {"icon": "💬", "name_en": "WhatsApp", "name_ar": "واتساب",   "name_fa": "واتساپ",
           "codes": ["wa", "whatsapp"]},
}

SERVICE_DISPLAY = {
    "tg": {"en": "✈️ Telegram", "ar": "✈️ تيليغرام", "fa": "✈️ تلگرام"},
    "wa": {"en": "💬 WhatsApp", "ar": "💬 واتساب",   "fa": "💬 واتساپ"},
}

# ── ساعات الذروة (بالتوقيت المحلي للدولة) ───────
PEAK_START = 9    # 9 صباحاً
PEAK_END   = 21   # 9 مساءً


class CountriesManager:
    """يدير بيانات الدول والترتيب الذكي."""

    def __init__(self):
        self._countries: List[dict] = []
        self._loaded = False

    def load(self, path: str = "countries.json") -> None:
        """تحميل ملف JSON مرة واحدة عند بدء البوت."""
        try:
            p = Path(path)
            if not p.exists():
                # fallback relative to this file
                p = Path(__file__).parent / path
            with open(p, encoding="utf-8") as f:
                self._countries = json.load(f)
            self._loaded = True
            logger.info("CountriesManager: loaded %d countries", len(self._countries))
        except Exception as exc:
            logger.error("CountriesManager: failed to load %s: %s", path, exc)
            self._countries = []

    def all(self) -> List[dict]:
        return self._countries

    def get(self, code: str) -> Optional[dict]:
        return next((c for c in self._countries if c["code"] == code), None)

    # ── حساب الوقت المحلي للدولة ────────────────
    def _local_hour(self, time_offset: float) -> float:
        """يحسب الساعة الحالية في الدولة بناءً على فارق التوقيت UTC."""
        utc_now = datetime.now(timezone.utc)
        offset  = timedelta(hours=time_offset)
        local   = utc_now + offset
        return local.hour + local.minute / 60

    def _is_peak(self, time_offset: float) -> bool:
        """هل الدولة الآن في ساعات الذروة (9ص-9م محلي)؟"""
        local_h = self._local_hour(time_offset)
        return PEAK_START <= local_h < PEAK_END

    def _peak_score(self, time_offset: float) -> float:
        """
        يحسب درجة النشاط (0-1) بناءً على القرب من منتصف الذروة (14:00 محلي).
        كلما اقترب الوقت من 2 ظهراً كلما ارتفعت الدرجة.
        """
        local_h = self._local_hour(time_offset)
        if not (PEAK_START <= local_h < PEAK_END):
            return 0.0
        mid = (PEAK_START + PEAK_END) / 2  # 15:00
        dist = abs(local_h - mid)
        max_dist = (PEAK_END - PEAK_START) / 2
        return 1.0 - (dist / max_dist)

    # ── ترتيب ذكي بناءً على الوقت ────────────────
    def sort_by_activity(
        self,
        countries: List[dict],
        top_codes: List[str] = None,
    ) -> List[dict]:
        """
        يرتب الدول بالترتيب التالي:
        1. الدول في ساعات الذروة → مرتبة حسب درجة النشاط
        2. الدول الأكثر مبيعاً (إن وُجدت)
        3. باقي الدول أبجدياً
        """
        top_codes = top_codes or []

        def sort_key(c: dict) -> Tuple:
            offset = c.get("time", 0)
            peak   = self._is_peak(offset)
            score  = self._peak_score(offset)
            is_top = c["code"] in top_codes
            # ترتيب تنازلي: peak أولاً، ثم top sellers، ثم score
            return (0 if peak else 1, 0 if is_top else 1, -score, c["name_en"])

        return sorted(countries, key=sort_key)

    # ── تصفية دول للخدمة المحددة ─────────────────
    def get_countries_for_service(
        self,
        service: str,
        count_map: Dict[str, int] = None,
        top_codes: List[str] = None,
    ) -> List[dict]:
        """
        يرجع الدول المتاحة لخدمة معينة (tg أو wa)
        مع إضافة عدد الأرقام المتاحة.
        """
        count_map = count_map or {}
        result = []
        for c in self._countries:
            code = c["code"]
            count = count_map.get(code, -1)
            entry = dict(c)
            entry["available_count"] = count
            result.append(entry)

        # ترتيب ذكي
        return self.sort_by_activity(result, top_codes or [])

    # ── تحديد كود الدولة للمورد المحدد ──────────
    def get_provider_code(self, country_code: str, provider: str) -> Optional[str]:
        """يحول كود ISO إلى كود مورد مخصص."""
        c = self.get(country_code)
        if not c:
            return None
        return c.get(provider) or country_code

    # ── عرض الوقت المحلي للدولة ──────────────────
    def get_local_time_str(self, country_code: str) -> str:
        c = self.get(country_code)
        if not c:
            return ""
        offset = c.get("time", 0)
        local_h = self._local_hour(offset)
        h = int(local_h)
        m = int((local_h - h) * 60)
        period = "🌙" if local_h < 6 or local_h >= 21 else ("🌅" if local_h < 9 else "☀️")
        return f"{period} {h:02d}:{m:02d}"

    # ── بيانات الدولة للعرض ───────────────────────
    def format_country_btn(
        self,
        c: dict,
        lang: str = "ar",
        service: str = "tg",
    ) -> str:
        """
        صيغة زر الدولة:
        🇩🇪 ألمانيا - $0.25 (3 أرقام) ☀️
        """
        flag  = c.get("flag", "🏳️")
        name  = c.get("name_ar", c.get("name_en", "")) if lang == "ar" else c.get("name_en", "")
        count = c.get("available_count", -1)
        offset = c.get("time", 0)
        local_h = self._local_hour(offset)
        
        # أيقونة الوقت
        if local_h < 6 or local_h >= 21:
            time_icon = "🌙"
        elif PEAK_START <= local_h < PEAK_END:
            time_icon = "☀️"
        else:
            time_icon = "🌅"

        count_str = f"({count})" if count >= 0 else ""
        return f"{flag} {name} {count_str} {time_icon}".strip()


# Singleton
countries_manager = CountriesManager()
