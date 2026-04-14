"""config.py — centralised config from .env"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

def _bool(v: str) -> bool:
    return v.strip().lower() in ("1", "true", "yes")

def _list(v: str) -> List[int]:
    return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]

@dataclass
class Config:
    # Telegram Bot
    bot_token:   str       = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_ids:   List[int] = field(default_factory=list)

    # Database
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "otp_bot.db"))

    # DurianRCS
    durian_name:    str = field(default_factory=lambda: os.getenv("DURIAN_NAME", ""))
    durian_api_key: str = field(default_factory=lambda: os.getenv("DURIAN_API_KEY", ""))

    # PIDs
    pid_telegram:    str = field(default_factory=lambda: os.getenv("PID_TELEGRAM",    "0257"))
    pid_whatsapp_s1: str = field(default_factory=lambda: os.getenv("PID_WHATSAPP_S1", "0107"))
    pid_whatsapp_s2: str = field(default_factory=lambda: os.getenv("PID_WHATSAPP_S2", "0528"))

    # Pricing defaults (يُستخدم عند أول تشغيل فقط — يُعدَّل من الأدمن)
    price_tg:    float = field(default_factory=lambda: float(os.getenv("PRICE_TG",    "0.25")))
    price_wa_s1: float = field(default_factory=lambda: float(os.getenv("PRICE_WA_S1", "0.35")))
    price_wa_s2: float = field(default_factory=lambda: float(os.getenv("PRICE_WA_S2", "0.40")))

    # Timings
    otp_timeout:   int  = field(default_factory=lambda: int(os.getenv("OTP_TIMEOUT",   "300")))
    cancel_delay:  int  = field(default_factory=lambda: int(os.getenv("CANCEL_DELAY",  "60")))
    refund_enabled:bool = field(default_factory=lambda: _bool(os.getenv("REFUND_ENABLED", "true")))

    # Activation notification channel
    notif_channel_id:   str = field(default_factory=lambda: os.getenv("NOTIF_CHANNEL_ID",   ""))
    notif_channel_link: str = field(default_factory=lambda: os.getenv("NOTIF_CHANNEL_LINK", ""))

    # Locale
    default_lang: str = field(default_factory=lambda: os.getenv("DEFAULT_LANG", "ar"))

    def __post_init__(self):
        self.admin_ids = _list(os.getenv("ADMIN_IDS", ""))

    def is_admin(self, uid: int) -> bool:
        return uid in self.admin_ids

config = Config()
