"""
durian_api.py — DurianRCS API Client
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Base URL: https://api.durianrcs.com/out/ext_api/

Endpoints used:
  getUserInfo        → رصيد الحساب
  getMobile          → شراء رقم (single, serial=2)
  getMsg             → استقبال كود SMS
  passMobile         → تحرير/إلغاء رقم
  addBlack           → إضافة لقائمة سوداء
  getCountryPhoneNum → عدد الأرقام لكل دولة
  getStatus          → حالة الرقم
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE = "https://api.durianrcs.com/out/ext_api"
TIMEOUT = aiohttp.ClientTimeout(total=15)


@dataclass
class GetNumberResult:
    ok: bool
    number: str = ""
    error:  str = ""
    code:   int = 0


@dataclass
class GetSMSResult:
    ok:      bool = False
    code:    str  = ""     # كود التحقق
    message: str  = ""     # النص الكامل
    status:  int  = 908    # 200=وصل, 908=لم يصل, 405=فشل


class DurianAPI:
    """
    عميل async لـ DurianRCS.
    يستخدم serial=2 (single) في كل الطلبات.
    """

    def __init__(self, name: str, api_key: str):
        self.name    = name
        self.api_key = api_key
        self._sess: Optional[aiohttp.ClientSession] = None

    async def _s(self) -> aiohttp.ClientSession:
        if not self._sess or self._sess.closed:
            self._sess = aiohttp.ClientSession(timeout=TIMEOUT)
        return self._sess

    async def _get(self, endpoint: str, params: dict) -> dict:
        """يرسل GET ويرجع الـ JSON، أو dict فارغ عند الخطأ."""
        params.update({"name": self.name, "ApiKey": self.api_key})
        url = f"{BASE}/{endpoint}"
        try:
            s = await self._s()
            async with s.get(url, params=params) as r:
                data = await r.json(content_type=None)
                logger.debug("[Durian] %s → %s", endpoint, str(data)[:200])
                return data
        except Exception as exc:
            logger.error("[Durian] %s error: %s", endpoint, exc)
            return {"code": 400, "msg": str(exc), "data": ""}

    async def close(self):
        if self._sess:
            await self._sess.close()

    # ══════════════════════════════════════════════
    #  1. رصيد الحساب
    # ══════════════════════════════════════════════
    async def get_balance(self) -> float:
        """يرجع رصيد الحساب (score)."""
        data = await self._get("getUserInfo", {})
        try:
            if data.get("code") == 200:
                return float(data["data"].get("score", 0))
        except Exception:
            pass
        return 0.0

    # ══════════════════════════════════════════════
    #  2.1 شراء رقم (getMobile) — serial=2 (single)
    # ══════════════════════════════════════════════
    async def get_mobile(
        self,
        pid: str,
        country: str = "",
        noblack: int = 0,
    ) -> GetNumberResult:
        """
        يشتري رقماً واحداً.
        country: رمز ISO ثنائي (مثل "ru", "tr") أو "" لأي دولة.
        noblack: 0=فلتر blacklist الشخصي, 1=فلتر الكل.
        Returns: GetNumberResult
        """
        params = {
            "pid":     pid,
            "num":     1,
            "noblack": noblack,
            "serial":  2,
        }
        if country:
            params["cuy"] = country.lower()

        data = await self._get("getMobile", params)
        code = data.get("code", 400)

        if code == 200:
            number = str(data.get("data", "")).strip()
            if number:
                return GetNumberResult(ok=True, number=number, code=200)
            return GetNumberResult(ok=False, error="Empty number returned", code=code)

        error_map = {
            403: "رصيد غير كافٍ",
            406: "تجاوزت حد 24 ساعة — تواصل مع الأدمن",
            409: "طلبات كثيرة — أبطئ من الطلبات",
            906: "لا توجد أرقام متاحة حالياً",
            903: "رمز الدولة غير صحيح",
            904: "PID غير صحيح",
            800: "الحساب محظور",
            802: "API Key خاطئ",
        }
        msg = error_map.get(code, data.get("msg", f"خطأ {code}"))
        return GetNumberResult(ok=False, error=msg, code=code)

    # ══════════════════════════════════════════════
    #  3. استقبال كود SMS (getMsg)
    # ══════════════════════════════════════════════
    async def get_msg(self, pid: str, number: str) -> GetSMSResult:
        """
        يطلب كود SMS للرقم.
        code 200 → وصل الكود
        code 908 → لم يصل بعد (أعد المحاولة)
        code 405 → فشل نهائي
        """
        data = await self._get("getMsg", {
            "pid":    pid,
            "pn":     number,
            "serial": 2,
        })
        api_code = data.get("code", 908)

        if api_code == 200:
            return GetSMSResult(
                ok=True,
                code=str(data.get("data", "")).strip(),
                message=str(data.get("data", "")).strip(),
                status=200,
            )
        if api_code in (405, 407):
            return GetSMSResult(ok=False, status=405)   # فشل نهائي
        # 908 أو غيرها → لم يصل بعد
        return GetSMSResult(ok=False, status=908)

    # ══════════════════════════════════════════════
    #  4. تحرير رقم / إلغاؤه (passMobile)
    # ══════════════════════════════════════════════
    async def pass_mobile(self, pid: str, number: str) -> bool:
        """يحرر الرقم من النظام (إلغاء)."""
        data = await self._get("passMobile", {
            "pid":    pid,
            "pn":     number,
            "serial": 2,
        })
        return data.get("code") == 200

    # ══════════════════════════════════════════════
    #  5. إضافة لـ blacklist (addBlack)
    # ══════════════════════════════════════════════
    async def add_black(self, pid: str, number: str) -> bool:
        """يضيف الرقم لقائمة الأرقام المرفوضة."""
        data = await self._get("addBlack", {
            "pid": pid,
            "pn":  number,
        })
        code = data.get("code")
        return code in (200, 912)   # 912 = already blacklisted

    # ══════════════════════════════════════════════
    #  6. حالة الرقم (getStatus)
    # ══════════════════════════════════════════════
    async def get_status(self, pid: str, number: str) -> int:
        """
        201 → SMS وصل
        202 → محجوز، لم يصل SMS
        203 → غير محجوز، لم يصل SMS
        """
        data = await self._get("getStatus", {"pid": pid, "pn": number})
        return data.get("code", 203)

    # ══════════════════════════════════════════════
    #  8. عدد الأرقام لكل دولة (getCountryPhoneNum)
    # ══════════════════════════════════════════════
    async def get_country_counts(self, pid: str) -> Dict[str, int]:
        """
        يرجع dict مثل {"th": 5, "id": 12, "ru": 3}.
        المفاتيح: ISO 2-letter lowercase.
        """
        data = await self._get("getCountryPhoneNum", {"pid": pid})
        if data.get("code") == 200 and isinstance(data.get("data"), dict):
            return {k.lower(): int(v) for k, v in data["data"].items() if int(v) > 0}
        return {}


# ── Singleton factory (يُستخدم من api_manager) ──
_client: Optional[DurianAPI] = None

def get_client() -> DurianAPI:
    global _client
    if _client is None:
        from config import config
        _client = DurianAPI(config.durian_name, config.durian_api_key)
    return _client

async def reload_client():
    """يُعيد إنشاء العميل بعد تغيير الـ credentials."""
    global _client
    if _client:
        await _client.close()
    _client = None
    get_client()
