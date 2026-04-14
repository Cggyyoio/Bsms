"""
database.py — Async SQLite (aiosqlite)
جداول: users, orders, settings, rate_limits, crypto_payments
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiosqlite

from config import config

logger = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    full_name  TEXT,
    lang       TEXT    NOT NULL DEFAULT 'ar',
    balance    REAL    NOT NULL DEFAULT 0.0,
    is_banned  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    service      TEXT    NOT NULL,   -- 'tg' | 'wa_s1' | 'wa_s2'
    pid          TEXT    NOT NULL,
    country      TEXT    NOT NULL DEFAULT '',
    number       TEXT    NOT NULL,
    price        REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    sms_code     TEXT,
    sms_text     TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_limits (
    user_id    INTEGER NOT NULL,
    action     TEXT    NOT NULL,
    ts         TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, action, ts)
);

CREATE TABLE IF NOT EXISTS crypto_payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    txid       TEXT    NOT NULL UNIQUE,
    network    TEXT    NOT NULL,
    amount     REAL    NOT NULL,
    credit     REAL    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_date   ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_rate_user     ON rate_limits(user_id, action);
"""

_DEFAULTS = {
    # DurianRCS
    "durian_name":     config.durian_name,
    "durian_api_key":  config.durian_api_key,
    "pid_tg":          config.pid_telegram,
    "pid_wa_s1":       config.pid_whatsapp_s1,
    "pid_wa_s2":       config.pid_whatsapp_s2,
    # Unified pricing
    "price_tg":        str(config.price_tg),
    "price_wa_s1":     str(config.price_wa_s1),
    "price_wa_s2":     str(config.price_wa_s2),
    # Timings
    "otp_timeout":     str(config.otp_timeout),
    "cancel_delay":    str(config.cancel_delay),
    "refund_enabled":  "1",
    # Notification channel
    "notif_channel_id":   config.notif_channel_id,
    "notif_channel_link": config.notif_channel_link,
    # BEP20
    "pay_bep20":       "0",
    "bep20_address":   "",
    "bep20_min_usdt":  "1.00",
    "bep20_usdt_rate": "1.00",
    "bep20_confirmations": "3",
    # TRC20
    "pay_trc20":       "0",
    "trc20_address":   "",
    "trc20_api_key":   "",
    "trc20_min_usdt":  "1.00",
    "trc20_usdt_rate": "1.00",
    "trc20_confirmations": "19",
}


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        for k, v in _DEFAULTS.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )
        await self._conn.commit()
        logger.info("DB connected: %s", self.path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── Raw ────────────────────────────────────
    async def fetchone(self, sql: str, p: tuple = ()) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(sql, p) as c:
            return await c.fetchone()

    async def fetchall(self, sql: str, p: tuple = ()) -> List[aiosqlite.Row]:
        async with self._conn.execute(sql, p) as c:
            return await c.fetchall()

    async def execute(self, sql: str, p: tuple = ()) -> int:
        async with self._conn.execute(sql, p) as c:
            await self._conn.commit()
            return c.lastrowid

    # ── Settings ───────────────────────────────
    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetchone("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # ── Users ──────────────────────────────────
    async def upsert_user(self, user_id: int, username: Optional[str],
                          full_name: str, lang: str = "ar") -> None:
        await self.execute(
            "INSERT INTO users(user_id,username,full_name,lang) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (user_id, username, full_name, lang),
        )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = await self.fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
        return dict(row) if row else None

    async def get_user_lang(self, user_id: int) -> str:
        row = await self.fetchone("SELECT lang FROM users WHERE user_id=?", (user_id,))
        return row["lang"] if row else config.default_lang

    async def set_user_lang(self, user_id: int, lang: str) -> None:
        await self.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))

    async def get_balance(self, user_id: int) -> float:
        row = await self.fetchone("SELECT balance FROM users WHERE user_id=?", (user_id,))
        return float(row["balance"]) if row else 0.0

    async def update_balance(self, user_id: int, delta: float) -> float:
        await self.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (delta, user_id))
        return await self.get_balance(user_id)

    async def is_banned(self, user_id: int) -> bool:
        row = await self.fetchone("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
        return bool(row["is_banned"]) if row else False

    async def set_ban(self, user_id: int, banned: bool) -> None:
        await self.execute("UPDATE users SET is_banned=? WHERE user_id=?", (int(banned), user_id))

    async def count_users(self) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS c FROM users")
        return row["c"] if row else 0

    async def get_all_users(self) -> List[Dict]:
        rows = await self.fetchall("SELECT user_id, lang FROM users WHERE is_banned=0")
        return [dict(r) for r in rows]

    async def search_user(self, query: str) -> Optional[Dict]:
        q = query.lstrip("@")
        if q.isdigit():
            row = await self.fetchone("SELECT * FROM users WHERE user_id=?", (int(q),))
        else:
            row = await self.fetchone("SELECT * FROM users WHERE username=?", (q,))
        return dict(row) if row else None

    # ── Orders ─────────────────────────────────
    async def create_order(self, user_id: int, service: str, pid: str,
                           country: str, number: str, price: float) -> int:
        return await self.execute(
            "INSERT INTO orders(user_id,service,pid,country,number,price) VALUES(?,?,?,?,?,?)",
            (user_id, service, pid, country, number, price),
        )

    async def get_order(self, order_id: int) -> Optional[Dict]:
        row = await self.fetchone("SELECT * FROM orders WHERE id=?", (order_id,))
        return dict(row) if row else None

    async def update_order(self, order_id: int, status: str,
                           sms_code: str = None, sms_text: str = None) -> None:
        await self.execute(
            "UPDATE orders SET status=?, sms_code=COALESCE(?,sms_code), "
            "sms_text=COALESCE(?,sms_text), updated_at=datetime('now') WHERE id=?",
            (status, sms_code, sms_text, order_id),
        )

    async def get_user_orders(self, user_id: int, limit: int = 15) -> List[Dict]:
        rows = await self.fetchall(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return [dict(r) for r in rows]

    async def has_pending_order(self, user_id: int) -> bool:
        row = await self.fetchone(
            "SELECT id FROM orders WHERE user_id=? AND status='pending' LIMIT 1", (user_id,)
        )
        return row is not None

    async def count_orders(self) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS c FROM orders")
        return row["c"] if row else 0

    async def count_orders_for_user(self, user_id: int) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS c FROM orders WHERE user_id=?", (user_id,))
        return row["c"] if row else 0

    async def count_completed(self) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS c FROM orders WHERE status='completed'")
        return row["c"] if row else 0

    async def get_total_profit(self) -> float:
        row = await self.fetchone("SELECT SUM(price) AS s FROM orders WHERE status='completed'")
        return float(row["s"]) if row and row["s"] else 0.0

    async def get_today_orders(self) -> int:
        row = await self.fetchone(
            "SELECT COUNT(*) AS c FROM orders WHERE date(created_at)=date('now')"
        )
        return row["c"] if row else 0

    async def get_today_profit(self) -> float:
        row = await self.fetchone(
            "SELECT SUM(price) AS s FROM orders WHERE status='completed' AND date(created_at)=date('now')"
        )
        return float(row["s"]) if row and row["s"] else 0.0

    async def get_top_service(self) -> str:
        row = await self.fetchone(
            "SELECT service, COUNT(*) AS c FROM orders GROUP BY service ORDER BY c DESC LIMIT 1"
        )
        return row["service"] if row else "—"

    async def get_top_country(self) -> str:
        row = await self.fetchone(
            "SELECT country, COUNT(*) AS c FROM orders WHERE country!='' "
            "GROUP BY country ORDER BY c DESC LIMIT 1"
        )
        return row["country"] if row else "—"

    async def get_top_countries(self, limit: int = 10) -> List[Dict]:
        rows = await self.fetchall(
            "SELECT country, COUNT(*) AS cnt FROM orders WHERE country!='' "
            "GROUP BY country ORDER BY cnt DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    # ── Rate limiting ──────────────────────────
    async def check_rate_limit(self, user_id: int, action: str,
                               max_count: int, window_sec: int) -> bool:
        """يرجع True إذا المستخدم لم يتجاوز الحد."""
        row = await self.fetchone(
            "SELECT COUNT(*) AS c FROM rate_limits WHERE user_id=? AND action=? "
            "AND ts > datetime('now', ? || ' seconds')",
            (user_id, action, f"-{window_sec}"),
        )
        return (row["c"] if row else 0) < max_count

    async def record_rate(self, user_id: int, action: str) -> None:
        await self.execute(
            "INSERT INTO rate_limits(user_id, action) VALUES(?,?)", (user_id, action)
        )

    async def clean_rate_limits(self) -> None:
        await self.execute(
            "DELETE FROM rate_limits WHERE ts < datetime('now', '-1 hour')"
        )

    # ── Crypto payments ────────────────────────
    async def is_txid_used(self, txid: str) -> bool:
        row = await self.fetchone("SELECT id FROM crypto_payments WHERE txid=?", (txid.lower(),))
        return row is not None

    async def save_crypto_payment(self, user_id: int, txid: str, network: str,
                                  amount: float, credit: float) -> None:
        await self.execute(
            "INSERT OR IGNORE INTO crypto_payments(user_id,txid,network,amount,credit) VALUES(?,?,?,?,?)",
            (user_id, txid.lower(), network, amount, credit),
        )


db = Database(config.database_path)
