"""
api_manager.py — Modular, async SMS provider integrations.

Supported providers:
  • SMSHub        (smshub.org)          — عام، أسعار جيدة
  • 5SIM          (5sim.net)            — سريع، API نظيف
  • SMS-Activate  (sms-activate.org)    — الأكبر، تغطية واسعة
  • GrizzlySMS    (grizzlysms.com)      — رخيص جداً، دولي
  • VakSMS        (vak-sms.com)         — سريع، روسي/دولي
  • OnlineSim     (onlinesim.io)        — إيراني/دولي، موثوق
  • SMS-Man       (sms-man.com)         — تغطية إيرانية ممتازة

v2.0 — إضافة:
  • get_balance() لكل مورد
  • تفعيل/تعطيل الموردين من DB
  • Auto Provider Selection (أرخص مورد متاح)
  • Smart Retry (يجرب مورد آخر عند الفشل)
  • Cache للخدمات
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Data classes
# ──────────────────────────────────────────────
@dataclass
class Country:
    code: str
    name: str
    flag: str = "🏳️"


@dataclass
class Service:
    code: str
    name: str
    icon: str = "📱"
    price_raw: float = 0.0
    count: int = 0


@dataclass
class ActivationResult:
    success: bool
    order_id: str = ""
    number: str = ""
    error: str = ""
    provider_used: str = ""


@dataclass
class SMSResult:
    received: bool = False
    code: str = ""
    full_text: str = ""
    status: str = "WAITING"


# ──────────────────────────────────────────────
#  Base provider
# ──────────────────────────────────────────────
class BaseProvider:
    name: str = "base"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _session_get(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self._session

    async def _get(self, url: str, params: Dict[str, Any] = None) -> Any:
        sess = await self._session_get()
        try:
            async with sess.get(url, params=params or {}) as resp:
                resp.raise_for_status()
                ct = resp.content_type
                if "json" in ct:
                    return await resp.json()
                return await resp.text()
        except aiohttp.ClientError as exc:
            logger.error("[%s] HTTP error: %s", self.name, exc)
            raise

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    # ── Abstract interface ────────────────────────
    async def get_countries(self) -> List[Country]:
        raise NotImplementedError

    async def get_services(self, country_code: str) -> List[Service]:
        raise NotImplementedError

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        raise NotImplementedError

    async def get_sms(self, order_id: str) -> SMSResult:
        raise NotImplementedError

    async def cancel(self, order_id: str) -> bool:
        raise NotImplementedError

    async def finish(self, order_id: str) -> bool:
        raise NotImplementedError

    async def get_balance(self) -> float:
        """يجلب رصيد الحساب. يُنفَّذ في كل مورد."""
        return -1.0  # -1 = غير مدعوم


# ──────────────────────────────────────────────
#  SMSHub provider
# ──────────────────────────────────────────────
class SMSHubProvider(BaseProvider):
    name = "smshub"
    BASE = "https://smshub.org/stubs/handler_api.php"

    COUNTRIES = {
        "russia": ("Russia", "🇷🇺"), "ukraine": ("Ukraine", "🇺🇦"),
        "usa": ("USA", "🇺🇸"), "england": ("UK", "🇬🇧"),
        "germany": ("Germany", "🇩🇪"), "france": ("France", "🇫🇷"),
        "china": ("China", "🇨🇳"), "india": ("India", "🇮🇳"),
        "brazil": ("Brazil", "🇧🇷"), "egypt": ("Egypt", "🇪🇬"),
        "saudi": ("Saudi Arabia", "🇸🇦"), "uae": ("UAE", "🇦🇪"),
        "turkey": ("Turkey", "🇹🇷"), "iran": ("Iran", "🇮🇷"),
        "pakistan": ("Pakistan", "🇵🇰"), "indonesia": ("Indonesia", "🇮🇩"),
        "mexico": ("Mexico", "🇲🇽"), "nigeria": ("Nigeria", "🇳🇬"),
        "vietnam": ("Vietnam", "🇻🇳"), "philippines": ("Philippines", "🇵🇭"),
    }

    SERVICE_NAMES = {
        "wa": ("WhatsApp", "💬"), "tg": ("Telegram", "✈️"),
        "go": ("Google", "🔵"), "fb": ("Facebook", "📘"),
        "tw": ("Twitter/X", "🐦"), "ig": ("Instagram", "📸"),
        "vi": ("Viber", "💜"), "si": ("Signal", "🔒"),
        "ub": ("Uber", "🚗"), "mm": ("Mail.ru", "📩"),
        "ya": ("Yandex", "🟡"), "tt": ("TikTok", "🎵"),
        "am": ("Amazon", "📦"), "ms": ("Microsoft", "🪟"),
    }

    async def get_balance(self) -> float:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key,
                "action": "getBalance",
            })).strip()
            # Response: ACCESS_BALANCE:12.50
            if resp.startswith("ACCESS_BALANCE"):
                return float(resp.split(":")[1])
        except Exception as exc:
            logger.error("[smshub] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        return [Country(code=k, name=v[0], flag=v[1]) for k, v in self.COUNTRIES.items()]

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(self.BASE, {
                "api_key": self.api_key,
                "action": "getPrices",
                "country": country_code,
            })
            if not isinstance(data, dict):
                return []
            country_data = data.get(country_code, {})
            services: List[Service] = []
            for svc_code, info in country_data.items():
                name_info = self.SERVICE_NAMES.get(svc_code, (svc_code.upper(), "📱"))
                cost = float(info.get("cost", 0))
                count = int(info.get("count", 0))
                if count > 0:
                    services.append(Service(
                        code=svc_code, name=name_info[0], icon=name_info[1],
                        price_raw=cost / 100, count=count,
                    ))
            return sorted(services, key=lambda s: s.price_raw)
        except Exception as exc:
            logger.error("[smshub] get_services: %s", exc)
            return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            resp = await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getNumber",
                "service": service_code, "country": country_code,
            })
            text = str(resp).strip()
            if text.startswith("ACCESS_NUMBER"):
                _, order_id, number = text.split(":")
                return ActivationResult(success=True, order_id=order_id, number=number, provider_used=self.name)
            return ActivationResult(success=False, error=text)
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getStatus", "id": order_id,
            })).strip()
            if resp.startswith("STATUS_OK"):
                code = resp.split(":")[1]
                return SMSResult(received=True, code=code, full_text=code, status="RECEIVED")
            if resp in ("STATUS_WAIT_CODE", "STATUS_WAIT_RETRY"):
                return SMSResult(status="WAITING")
            if resp == "STATUS_CANCEL":
                return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[smshub] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        resp = str(await self._get(self.BASE, {
            "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 8,
        })).strip()
        return resp == "ACCESS_CANCEL"

    async def finish(self, order_id: str) -> bool:
        resp = str(await self._get(self.BASE, {
            "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 6,
        })).strip()
        return resp == "ACCESS_ACTIVATION"


# ──────────────────────────────────────────────
#  5SIM provider
# ──────────────────────────────────────────────
class FiveSimProvider(BaseProvider):
    name = "fivesim"
    BASE = "https://5sim.net/v1"

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

    async def _get_json(self, path: str, params: Dict = None) -> Any:
        sess = await self._session_get()
        url = self.BASE + path
        async with sess.get(url, headers=self._headers(), params=params or {}) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_balance(self) -> float:
        try:
            data = await self._get_json("/user/profile")
            return float(data.get("balance", -1))
        except Exception as exc:
            logger.error("[5sim] get_balance: %s", exc)
            return -1.0

    async def get_countries(self) -> List[Country]:
        try:
            data = await self._get_json("/guest/countries")
            return [Country(code=k, name=v.get("text_en", k), flag="🏳️") for k, v in data.items()][:50]
        except Exception as exc:
            logger.error("[5sim] get_countries: %s", exc)
            return []

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get_json(f"/guest/products/{country_code}/any")
            return [
                Service(code=c, name=c.capitalize(), price_raw=float(i.get("Price", 0)), count=int(i.get("Qty", 0)))
                for c, i in data.items() if int(i.get("Qty", 0)) > 0
            ]
        except Exception as exc:
            logger.error("[5sim] get_services: %s", exc)
            return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            data = await self._get_json(f"/user/buy/activation/{country_code}/any/{service_code}")
            if "id" in data:
                return ActivationResult(success=True, order_id=str(data["id"]), number=data.get("phone", ""), provider_used=self.name)
            return ActivationResult(success=False, error=str(data))
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            sess = await self._session_get()
            async with sess.get(f"{self.BASE}/user/check/{order_id}", headers=self._headers()) as resp:
                data = await resp.json()
            sms_list = data.get("sms", [])
            if sms_list:
                sms = sms_list[-1]
                return SMSResult(received=True, code=sms.get("code", ""), full_text=sms.get("text", ""), status="RECEIVED")
            if data.get("status", "") in ("CANCELED", "BANNED"):
                return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[5sim] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        try:
            sess = await self._session_get()
            async with sess.get(f"{self.BASE}/user/cancel/{order_id}", headers=self._headers()) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def finish(self, order_id: str) -> bool:
        try:
            sess = await self._session_get()
            async with sess.get(f"{self.BASE}/user/finish/{order_id}", headers=self._headers()) as resp:
                return resp.status == 200
        except Exception:
            return False


# ──────────────────────────────────────────────
#  SMS-Activate provider
# ──────────────────────────────────────────────
class SMSActivateProvider(BaseProvider):
    name = "smsactivate"
    BASE = "https://api.sms-activate.org/stubs/handler_api.php"

    async def get_balance(self) -> float:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getBalance",
            })).strip()
            if resp.startswith("ACCESS_BALANCE"):
                return float(resp.split(":")[1])
        except Exception as exc:
            logger.error("[smsactivate] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        try:
            data = await self._get(self.BASE, {"api_key": self.api_key, "action": "getCountries"})
            if not isinstance(data, dict):
                return []
            return [Country(code=str(cid), name=info.get("eng", f"Country {cid}"), flag="🏳️") for cid, info in data.items()]
        except Exception as exc:
            logger.error("[smsactivate] get_countries: %s", exc)
            return []

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(self.BASE, {"api_key": self.api_key, "action": "getPrices", "country": country_code})
            if not isinstance(data, dict):
                return []
            services = []
            for svc, countries in data.items():
                info = countries.get(country_code, {})
                cost = float(info.get("cost", 0))
                count = int(info.get("count", 0))
                if count > 0:
                    services.append(Service(code=svc, name=svc.upper(), price_raw=cost, count=count))
            return services
        except Exception as exc:
            logger.error("[smsactivate] get_services: %s", exc)
            return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getNumber",
                "service": service_code, "country": country_code,
            })).strip()
            if resp.startswith("ACCESS_NUMBER"):
                _, order_id, number = resp.split(":")
                return ActivationResult(success=True, order_id=order_id, number=number, provider_used=self.name)
            return ActivationResult(success=False, error=resp)
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getStatus", "id": order_id,
            })).strip()
            if resp.startswith("STATUS_OK"):
                code = resp.split(":")[1]
                return SMSResult(received=True, code=code, full_text=code, status="RECEIVED")
            if resp == "STATUS_CANCEL":
                return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[smsactivate] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        resp = str(await self._get(self.BASE, {
            "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 8,
        })).strip()
        return resp == "ACCESS_CANCEL"

    async def finish(self, order_id: str) -> bool:
        resp = str(await self._get(self.BASE, {
            "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 6,
        })).strip()
        return resp == "ACCESS_ACTIVATION"


# ──────────────────────────────────────────────
#  GrizzlySMS provider
# ──────────────────────────────────────────────
class GrizzlySMSProvider(BaseProvider):
    name = "grizzlysms"
    BASE = "https://api.grizzlysms.com/stubs/handler_api.php"

    COUNTRY_MAP = {
        "0": ("Russia","🇷🇺"), "1": ("Ukraine","🇺🇦"), "6": ("Indonesia","🇮🇩"),
        "9": ("USA","🇺🇸"), "10": ("UK","🇬🇧"), "12": ("Germany","🇩🇪"),
        "14": ("India","🇮🇳"), "22": ("Egypt","🇪🇬"), "24": ("Saudi Arabia","🇸🇦"),
        "31": ("Iran","🇮🇷"), "34": ("UAE","🇦🇪"), "62": ("Turkey","🇹🇷"),
        "88": ("Pakistan","🇵🇰"), "4": ("Philippines","🇵🇭"), "13": ("France","🇫🇷"),
        "82": ("Nigeria","🇳🇬"), "15": ("Brazil","🇧🇷"), "3": ("China","🇨🇳"),
    }

    async def get_balance(self) -> float:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getBalance",
            })).strip()
            if resp.startswith("ACCESS_BALANCE"):
                return float(resp.split(":")[1])
        except Exception as exc:
            logger.error("[grizzlysms] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        return [Country(code=k, name=v[0], flag=v[1]) for k, v in self.COUNTRY_MAP.items()]

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getPrices", "country": country_code,
            })
            if not isinstance(data, dict):
                return []
            services = []
            for svc, countries_info in data.items():
                info = countries_info.get(country_code, {}) if isinstance(countries_info, dict) else {}
                cost = float(info.get("cost", 0))
                count = int(info.get("count", 0))
                if count > 0:
                    services.append(Service(code=svc, name=svc.upper(), price_raw=cost, count=count))
            return sorted(services, key=lambda s: s.price_raw)
        except Exception as exc:
            logger.error("[grizzlysms] get_services: %s", exc)
            return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getNumber",
                "service": service_code, "country": country_code,
            })).strip()
            if resp.startswith("ACCESS_NUMBER"):
                _, order_id, number = resp.split(":")
                return ActivationResult(success=True, order_id=order_id, number=number, provider_used=self.name)
            return ActivationResult(success=False, error=resp)
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "getStatus", "id": order_id,
            })).strip()
            if resp.startswith("STATUS_OK"):
                code = resp.split(":")[1]
                return SMSResult(received=True, code=code, full_text=code, status="RECEIVED")
            if resp == "STATUS_CANCEL":
                return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[grizzlysms] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 8,
            })).strip()
            return resp == "ACCESS_CANCEL"
        except Exception:
            return False

    async def finish(self, order_id: str) -> bool:
        try:
            resp = str(await self._get(self.BASE, {
                "api_key": self.api_key, "action": "setStatus", "id": order_id, "status": 6,
            })).strip()
            return resp == "ACCESS_ACTIVATION"
        except Exception:
            return False


# ──────────────────────────────────────────────
#  VakSMS provider
# ──────────────────────────────────────────────
class VakSMSProvider(BaseProvider):
    name = "vaksms"
    BASE = "https://vak-sms.com/api"

    async def get_balance(self) -> float:
        try:
            data = await self._get(f"{self.BASE}/getBalance/", {"apiKey": self.api_key})
            if isinstance(data, dict):
                return float(data.get("balance", -1))
        except Exception as exc:
            logger.error("[vaksms] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        try:
            data = await self._get(f"{self.BASE}/getCountryList/", {"apiKey": self.api_key})
            if isinstance(data, list):
                return [Country(code=c.get("countryCode", ""), name=c.get("countryName", ""), flag="🏳️") for c in data]
        except Exception as exc:
            logger.error("[vaksms] get_countries: %s", exc)
        return []

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(f"{self.BASE}/getServiceList/", {
                "apiKey": self.api_key, "country": country_code,
            })
            if isinstance(data, list):
                return [
                    Service(code=s.get("service",""), name=s.get("service","").upper(),
                            price_raw=float(s.get("price",0)), count=int(s.get("count",0)))
                    for s in data if int(s.get("count",0)) > 0
                ]
        except Exception as exc:
            logger.error("[vaksms] get_services: %s", exc)
        return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            data = await self._get(f"{self.BASE}/getSim/", {
                "apiKey": self.api_key, "service": service_code, "country": country_code,
            })
            if isinstance(data, dict) and "tel" in data:
                return ActivationResult(success=True, order_id=str(data.get("idNum","")), number=str(data["tel"]), provider_used=self.name)
            return ActivationResult(success=False, error=str(data))
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            data = await self._get(f"{self.BASE}/getSmsCode/", {
                "apiKey": self.api_key, "idNum": order_id,
            })
            if isinstance(data, dict):
                code = data.get("smsCode")
                if code:
                    return SMSResult(received=True, code=str(code), full_text=str(code), status="RECEIVED")
                if data.get("status") == "cancel":
                    return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[vaksms] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/setStatus/", {
                "apiKey": self.api_key, "idNum": order_id, "status": "cancel",
            })
            return isinstance(data, dict) and not data.get("error")
        except Exception:
            return False

    async def finish(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/setStatus/", {
                "apiKey": self.api_key, "idNum": order_id, "status": "end",
            })
            return isinstance(data, dict) and not data.get("error")
        except Exception:
            return False


# ──────────────────────────────────────────────
#  OnlineSim provider
# ──────────────────────────────────────────────
class OnlineSimProvider(BaseProvider):
    name = "onlinesim"
    BASE = "https://onlinesim.io/api"

    async def get_balance(self) -> float:
        try:
            data = await self._get(f"{self.BASE}/getBalance.php", {"apikey": self.api_key})
            if isinstance(data, dict):
                return float(data.get("balance", -1))
        except Exception as exc:
            logger.error("[onlinesim] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        try:
            data = await self._get(f"{self.BASE}/getCountries.php", {"apikey": self.api_key})
            if isinstance(data, dict) and "countries" in data:
                return [Country(code=str(cid), name=info.get("name_en", str(cid)), flag="🏳️")
                        for cid, info in data["countries"].items()]
        except Exception as exc:
            logger.error("[onlinesim] get_countries: %s", exc)
        return []

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(f"{self.BASE}/getTariffs.php", {
                "apikey": self.api_key, "country": country_code,
            })
            if isinstance(data, dict) and "response" in data:
                return [
                    Service(code=s.get("service",""), name=s.get("service","").upper(),
                            price_raw=float(s.get("price",0)), count=int(s.get("count",0)))
                    for s in data["response"] if int(s.get("count",0)) > 0
                ]
        except Exception as exc:
            logger.error("[onlinesim] get_services: %s", exc)
        return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            data = await self._get(f"{self.BASE}/getNum.php", {
                "apikey": self.api_key, "service": service_code, "country": country_code,
            })
            if isinstance(data, dict) and data.get("response") == 1:
                return ActivationResult(success=True, order_id=str(data.get("tzid","")), number=str(data.get("number","")), provider_used=self.name)
            return ActivationResult(success=False, error=str(data))
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            data = await self._get(f"{self.BASE}/getState.php", {
                "apikey": self.api_key, "tzid": order_id,
            })
            if isinstance(data, dict):
                if data.get("response") == 1:
                    code = data.get("msg", "")
                    return SMSResult(received=True, code=str(code), full_text=str(code), status="RECEIVED")
                if data.get("response") in (8, 9):
                    return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[onlinesim] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/setOperationRevise.php", {
                "apikey": self.api_key, "tzid": order_id,
            })
            return isinstance(data, dict) and data.get("response") == 1
        except Exception:
            return False

    async def finish(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/setOperationOk.php", {
                "apikey": self.api_key, "tzid": order_id,
            })
            return isinstance(data, dict) and data.get("response") == 1
        except Exception:
            return False


# ──────────────────────────────────────────────
#  SMS-Man provider
# ──────────────────────────────────────────────
class SMSManProvider(BaseProvider):
    name = "smsman"
    BASE = "https://api.sms-man.com/control"

    COUNTRY_IDS = {
        "1": ("Russia","🇷🇺"), "2": ("Ukraine","🇺🇦"), "3": ("Kazakhstan","🇰🇿"),
        "4": ("China","🇨🇳"), "5": ("Philippines","🇵🇭"), "7": ("Indonesia","🇮🇩"),
        "10": ("USA","🇺🇸"), "11": ("UK","🇬🇧"), "12": ("Germany","🇩🇪"),
        "13": ("France","🇫🇷"), "14": ("India","🇮🇳"), "22": ("Egypt","🇪🇬"),
        "24": ("Saudi Arabia","🇸🇦"), "31": ("Iran","🇮🇷"), "34": ("UAE","🇦🇪"),
        "62": ("Turkey","🇹🇷"), "82": ("Nigeria","🇳🇬"), "88": ("Pakistan","🇵🇰"),
    }

    async def get_balance(self) -> float:
        try:
            data = await self._get(f"{self.BASE}/get-balance", {"token": self.api_key})
            if isinstance(data, dict):
                return float(data.get("balance", -1))
        except Exception as exc:
            logger.error("[smsman] get_balance: %s", exc)
        return -1.0

    async def get_countries(self) -> List[Country]:
        try:
            data = await self._get(f"{self.BASE}/countries", {"token": self.api_key})
            if isinstance(data, list):
                return [Country(code=str(c.get("id","")), name=c.get("title_en","Unknown"), flag="🏳️") for c in data]
        except Exception as exc:
            logger.error("[smsman] get_countries: %s", exc)
        return [Country(code=k, name=v[0], flag=v[1]) for k, v in self.COUNTRY_IDS.items()]

    async def get_services(self, country_code: str) -> List[Service]:
        try:
            data = await self._get(f"{self.BASE}/prices", {
                "token": self.api_key, "country_id": country_code,
            })
            if not isinstance(data, dict):
                return []
            services = []
            for app_id, info in data.items():
                count = int(info.get("count", 0))
                price = float(info.get("price", 0))
                if count > 0:
                    services.append(Service(code=app_id, name=info.get("application_name", app_id), price_raw=price, count=count))
            return sorted(services, key=lambda s: s.price_raw)
        except Exception as exc:
            logger.error("[smsman] get_services: %s", exc)
            return []

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        try:
            data = await self._get(f"{self.BASE}/get-number", {
                "token": self.api_key, "country_id": country_code, "application_id": service_code,
            })
            if isinstance(data, dict) and "number" in data:
                return ActivationResult(success=True, order_id=str(data.get("request_id","")), number=str(data["number"]), provider_used=self.name)
            return ActivationResult(success=False, error=str(data))
        except Exception as exc:
            return ActivationResult(success=False, error=str(exc))

    async def get_sms(self, order_id: str) -> SMSResult:
        try:
            data = await self._get(f"{self.BASE}/get-sms", {
                "token": self.api_key, "request_id": order_id,
            })
            if isinstance(data, dict):
                sms_code = data.get("sms_code")
                if sms_code:
                    return SMSResult(received=True, code=str(sms_code), full_text=str(sms_code), status="RECEIVED")
                err = str(data.get("error_code", "")).lower()
                if "cancel" in err or "ban" in err:
                    return SMSResult(status="CANCELLED")
            return SMSResult(status="WAITING")
        except Exception as exc:
            logger.error("[smsman] get_sms: %s", exc)
            return SMSResult(status="WAITING")

    async def cancel(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/set-status", {
                "token": self.api_key, "request_id": order_id, "status": "cancel",
            })
            return isinstance(data, dict) and not data.get("error_code")
        except Exception:
            return False

    async def finish(self, order_id: str) -> bool:
        try:
            data = await self._get(f"{self.BASE}/set-status", {
                "token": self.api_key, "request_id": order_id, "status": "finish",
            })
            return isinstance(data, dict) and not data.get("error_code")
        except Exception:
            return False


# ──────────────────────────────────────────────
#  Provider registry
# ──────────────────────────────────────────────
PROVIDER_CLASSES = {
    "smshub":       SMSHubProvider,
    "fivesim":      FiveSimProvider,
    "smsactivate":  SMSActivateProvider,
    "grizzlysms":   GrizzlySMSProvider,
    "vaksms":       VakSMSProvider,
    "onlinesim":    OnlineSimProvider,
    "smsman":       SMSManProvider,
}

PROVIDER_LABELS = {
    "smshub":      "SMSHub",
    "fivesim":     "5SIM",
    "smsactivate": "SMS-Activate",
    "grizzlysms":  "GrizzlySMS 🐻",
    "vaksms":      "VakSMS ⚡",
    "onlinesim":   "OnlineSim 🌐",
    "smsman":      "SMS-Man 🇮🇷",
}


# ──────────────────────────────────────────────
#  API Manager
# ──────────────────────────────────────────────
class APIManager:
    """
    Wraps all providers.
    v2.0:
      • يستخدم فقط الموردين المفعَّلين (enabled)
      • Auto-select: يختار أرخص مورد متاح
      • Smart Retry: يجرب مورد آخر عند الفشل
      • Cache للخدمات
    """

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        self._enabled: Dict[str, bool] = {}
        self._active: Optional[str] = None
        self._margin: float = 20.0
        self._db = None

    async def init(self, db) -> None:
        self._db = db
        self._margin = float(await db.get_setting("profit_margin", "20"))
        active = await db.get_setting("active_provider", "smsman")
        for name, cls in PROVIDER_CLASSES.items():
            key = await db.get_setting(f"{name}_api_key", "")
            self._providers[name] = cls(api_key=key)
            enabled_val = await db.get_setting(f"{name}_enabled", "0")
            self._enabled[name] = enabled_val == "1"
        self._active = active
        enabled_list = [n for n, e in self._enabled.items() if e]
        logger.info("APIManager ready | active=%s enabled=%s margin=%.1f%%", active, enabled_list, self._margin)

    def provider(self, name: Optional[str] = None) -> BaseProvider:
        return self._providers[name or self._active]

    @property
    def active_name(self) -> str:
        return self._active

    def is_enabled(self, name: str) -> bool:
        return self._enabled.get(name, False)

    def get_enabled_providers(self) -> List[str]:
        return [n for n, e in self._enabled.items() if e and self._providers[n].api_key]

    async def reload(self, db) -> None:
        await self.init(db)

    def apply_margin(self, raw_price: float) -> float:
        return round(raw_price * (1 + self._margin / 100), 2)

    # ── Auto Provider Selection ──────────────────
    async def get_cheapest_provider(self, country_code: str, service_code: str) -> Optional[str]:
        """يختار أرخص مورد مفعَّل يملك الخدمة المطلوبة."""
        enabled = self.get_enabled_providers()
        if not enabled:
            return self._active  # Fallback

        best_provider = None
        best_price = float("inf")

        for name in enabled:
            try:
                services = await self._providers[name].get_services(country_code)
                for svc in services:
                    if svc.code == service_code and svc.count > 0:
                        if svc.price_raw < best_price:
                            best_price = svc.price_raw
                            best_provider = name
                        break
            except Exception:
                continue

        return best_provider or self._active

    # ── Smart Retry ──────────────────────────────
    async def buy_number_with_retry(self, country_code: str, service_code: str) -> ActivationResult:
        """يحاول الشراء من أفضل مورد، وعند الفشل يجرب الموردين الآخرين."""
        enabled = self.get_enabled_providers()

        # إذا لم يكن هناك موردون مفعَّلون، استخدم المورد النشط
        if not enabled:
            enabled = [self._active]

        # البدء بالمورد النشط أولاً إن كان مفعَّلاً
        if self._active in enabled:
            enabled = [self._active] + [p for p in enabled if p != self._active]

        last_error = "No providers available"
        for provider_name in enabled:
            try:
                result = await self._providers[provider_name].buy_number(country_code, service_code)
                if result.success:
                    result.provider_used = provider_name
                    logger.info("buy_number success via %s", provider_name)
                    return result
                last_error = result.error
                logger.warning("buy_number failed via %s: %s", provider_name, result.error)
            except Exception as exc:
                last_error = str(exc)
                logger.error("buy_number exception via %s: %s", provider_name, exc)
                continue

        return ActivationResult(success=False, error=last_error)

    # ── Convenience wrappers ─────────────────────
    async def get_countries(self) -> List[Country]:
        return await self.provider().get_countries()

    async def get_services(self, country_code: str) -> List[Service]:
        # جرب cache أولاً
        if self._db:
            cache_key = f"services:{self._active}:{country_code}"
            cached = await self._db.get_cache(cache_key)
            if cached:
                try:
                    raw = json.loads(cached)
                    return [Service(**s) for s in raw]
                except Exception:
                    pass

        svcs = await self.provider().get_services(country_code)
        for s in svcs:
            s.price_raw = self.apply_margin(s.price_raw)

        # احفظ في cache لمدة 5 دقائق
        if self._db and svcs:
            cache_key = f"services:{self._active}:{country_code}"
            await self._db.set_cache(
                cache_key,
                json.dumps([{"code": s.code, "name": s.name, "icon": s.icon, "price_raw": s.price_raw, "count": s.count} for s in svcs]),
                ttl_seconds=300
            )
        return svcs

    async def buy_number(self, country_code: str, service_code: str) -> ActivationResult:
        return await self.buy_number_with_retry(country_code, service_code)

    async def get_sms(self, order_id: str, provider_name: Optional[str] = None) -> SMSResult:
        return await self.provider(provider_name).get_sms(order_id)

    async def cancel(self, order_id: str, provider_name: Optional[str] = None) -> bool:
        return await self.provider(provider_name).cancel(order_id)

    async def finish(self, order_id: str, provider_name: Optional[str] = None) -> bool:
        return await self.provider(provider_name).finish(order_id)

    async def get_balance(self, provider_name: str) -> float:
        return await self._providers[provider_name].get_balance()

    async def close(self) -> None:
        for p in self._providers.values():
            await p.close()


# Singleton
api_manager = APIManager()
