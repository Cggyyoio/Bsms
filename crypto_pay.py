"""
crypto_pay.py — BEP20 + TRC20 payment handler (telebot)
"""
from __future__ import annotations
import asyncio, hashlib, logging, time
from typing import Optional
import aiohttp
from telebot.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

API_TIMEOUT     = 20
SESSION_TIMEOUT = 600

BSC_NODES = [
    "https://rpc.ankr.com/bsc",
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.binance.org/",
]
USDT_BEP20     = "0x55d398326f99059ff775485246999027b3197955"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TRONGRID_API   = "https://api.trongrid.io"
USDT_TRC20     = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

_SESSIONS: dict = {}
_USED_TXIDS: set = set()


def _session_start(uid, network):
    _SESSIONS[uid] = {"step": "waiting_txid", "network": network, "started": time.time(), "task": None}

def _session_get(uid):
    s = _SESSIONS.get(uid)
    if s and time.time() - s["started"] > SESSION_TIMEOUT:
        _session_clear(uid); return None
    return s

def _session_clear(uid):
    s = _SESSIONS.pop(uid, None)
    if s and s.get("task"):
        s["task"].cancel()


class BEP20Client:
    def __init__(self, wallet: str, min_confirms: int = 3):
        self.wallet = wallet.strip().lower()
        self.min_confirms = min_confirms

    async def _rpc(self, method, params):
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        for node in BSC_NODES:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(node, json=payload,
                                      headers={"Content-Type": "application/json"},
                                      timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as r:
                        data = await r.json(content_type=None)
                if "result" in data:
                    return data
            except Exception as e:
                logger.warning("[BEP20] %s: %s", node, e)
        return {"result": None}

    async def verify(self, txid: str) -> dict:
        txid = txid.strip().lower()
        if not txid.startswith("0x") or len(txid) != 66:
            return {"success": False, "error": "❌ TXID خاطئ — يبدأ بـ 0x ويكون 66 حرفاً"}
        receipt = (await self._rpc("eth_getTransactionReceipt", [txid])).get("result")
        if not isinstance(receipt, dict):
            return {"success": False, "error": "❌ TXID غير موجود على الشبكة"}
        if receipt.get("status") != "0x1":
            return {"success": False, "error": "❌ المعاملة فاشلة"}
        block_hex = receipt.get("blockNumber", "0x0") or "0x0"
        tx_block  = int(block_hex, 16)
        latest    = int((await self._rpc("eth_blockNumber", [])).get("result", "0x0"), 16)
        confirms  = max(0, latest - tx_block)
        if confirms < self.min_confirms:
            return {"success": False, "error": f"⏳ تأكيدات غير كافية ({confirms}/{self.min_confirms})"}
        logs = [lg for lg in receipt.get("logs", [])
                if lg.get("address", "").lower() == USDT_BEP20
                and len(lg.get("topics", [])) >= 3
                and lg["topics"][0].lower() == TRANSFER_TOPIC]
        if not logs:
            return {"success": False, "error": "❌ لا يوجد تحويل USDT BEP20"}
        lg = logs[0]
        to_addr = "0x" + lg["topics"][2][-40:]
        if to_addr.lower() != self.wallet:
            return {"success": False, "error": "❌ العنوان غير صحيح"}
        try:
            amount = int(lg.get("data", "0x0"), 16) / 1e18
        except Exception:
            return {"success": False, "error": "❌ تعذّر قراءة المبلغ"}
        if amount <= 0:
            return {"success": False, "error": "❌ المبلغ صفر"}
        return {"success": True, "amount": round(amount, 6), "confirms": confirms, "network": "BEP20"}


class TRC20Client:
    def __init__(self, api_key: str, wallet: str, min_confirms: int = 19):
        self.api_key = api_key.strip()
        self.wallet  = wallet.strip()
        self.min_confirms = min_confirms

    def _h(self):
        return {"Content-Type": "application/json", "TRON-PRO-API-KEY": self.api_key}

    async def _post(self, endpoint, body):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(TRONGRID_API + endpoint, json=body, headers=self._h(),
                                  timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as r:
                    return await r.json(content_type=None)
        except Exception as e:
            logger.error("[TRC20] %s: %s", endpoint, e)
            return {}

    async def verify(self, txid: str) -> dict:
        txid = txid.strip().lstrip("0x").lstrip("0X")
        if not txid:
            return {"success": False, "error": "❌ TXID فارغ"}
        tx = await self._post("/wallet/gettransactionbyid", {"value": txid, "visible": True})
        if not tx or "txID" not in tx:
            return {"success": False, "error": "❌ TXID غير موجود"}
        ret = tx.get("ret", [{}])
        if (ret[0].get("contractRet", "") if ret else "") != "SUCCESS":
            return {"success": False, "error": "❌ المعاملة فاشلة"}
        info = await self._post("/wallet/gettransactioninfobyid", {"value": txid, "visible": True})
        if not info or "id" not in info:
            return {"success": False, "error": "❌ تعذّر جلب التفاصيل"}
        if info.get("contract_address", "") != USDT_TRC20:
            return {"success": False, "error": "❌ ليست معاملة USDT TRC20"}
        block_number = info.get("blockNumber", 0)
        confirms = await self._get_confirms(block_number)
        if confirms < self.min_confirms:
            return {"success": False, "error": f"⏳ تأكيدات غير كافية ({confirms}/{self.min_confirms})"}
        usdt_log = next(
            (lg for lg in info.get("log", [])
             if len(lg.get("topics", [])) >= 3
             and lg["topics"][0].lower() == "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"),
            None
        )
        if not usdt_log:
            return {"success": False, "error": "❌ لا يوجد تحويل USDT"}
        to_base58 = self._hex_to_base58("41" + usdt_log["topics"][2][-40:])
        if to_base58 != self.wallet:
            return {"success": False, "error": "❌ العنوان غير صحيح"}
        try:
            amount = int(usdt_log.get("data", "0"), 16) / 1e6
        except Exception:
            return {"success": False, "error": "❌ تعذّر قراءة المبلغ"}
        if amount <= 0:
            return {"success": False, "error": "❌ المبلغ صفر"}
        return {"success": True, "amount": round(amount, 6), "confirms": confirms, "network": "TRC20"}

    async def _get_confirms(self, block_number):
        if not block_number:
            return 0
        try:
            data = await self._post("/wallet/getnowblock", {"visible": True})
            latest = data.get("block_header", {}).get("raw_data", {}).get("number", block_number)
            return max(0, latest - block_number)
        except Exception:
            return 0

    @staticmethod
    def _hex_to_base58(hex_str):
        alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        try:
            payload  = bytes.fromhex(hex_str)
            checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
            full     = payload + checksum
            n = int.from_bytes(full, "big")
            result = ""
            while n:
                result = alphabet[n % 58] + result
                n //= 58
            for byte in full:
                if byte == 0:
                    result = "1" + result
                else:
                    break
            return result
        except Exception:
            return ""


class CryptoPayHandler:
    LABELS = {"bep20": "💎 USDT BEP20 (BSC)", "trc20": "🟣 USDT TRC20 (TRON)"}

    def __init__(self, db, bot):
        self.db  = db
        self.bot = bot

    async def is_bep20_enabled(self):
        return (await self.db.get_setting("pay_bep20") == "1"
                and bool((await self.db.get_setting("bep20_address", "")).strip()))

    async def is_trc20_enabled(self):
        return (await self.db.get_setting("pay_trc20") == "1"
                and bool((await self.db.get_setting("trc20_api_key", "")).strip())
                and bool((await self.db.get_setting("trc20_address", "")).strip()))

    async def show_pay_page(self, chat_id: int, user_id: int, network: str):
        from keyboards import kb_crypto_pay
        from strings import t
        lang = await self.db.get_user_lang(user_id)

        if network == "bep20":
            if not await self.is_bep20_enabled():
                await self.bot.send_message(chat_id, "⛔ BEP20 متوقف حالياً.")
                return
            address   = await self.db.get_setting("bep20_address", "")
            min_usdt  = await self.db.get_setting("bep20_min_usdt", "1.00")
            rate      = await self.db.get_setting("bep20_usdt_rate", "1.00")
            net_label = "BEP20 (BSC)"
        else:
            if not await self.is_trc20_enabled():
                await self.bot.send_message(chat_id, "⛔ TRC20 متوقف حالياً.")
                return
            address   = await self.db.get_setting("trc20_address", "")
            min_usdt  = await self.db.get_setting("trc20_min_usdt", "1.00")
            rate      = await self.db.get_setting("trc20_usdt_rate", "1.00")
            net_label = "TRC20 (TRON)"

        await self.bot.send_message(
            chat_id,
            t("pay_page", lang, network=net_label, address=address,
              min_usdt=min_usdt, rate=rate),
            reply_markup=kb_crypto_pay(network, lang),
            parse_mode="HTML",
        )

    async def prompt_txid(self, call: CallbackQuery, network: str):
        uid  = call.from_user.id
        cid  = call.message.chat.id
        lang = await self.db.get_user_lang(uid)
        _session_start(uid, network)
        await self.bot.send_message(cid, t("pay_send_txid", lang))
        from strings import t as _t  # already imported

    async def handle_copy_address(self, call: CallbackQuery, network: str):
        setting = "bep20_address" if network == "bep20" else "trc20_address"
        address = await self.db.get_setting(setting, "")
        await self.bot.send_message(
            call.message.chat.id,
            f"📋 <b>عنوان USDT:</b>\n\n<code>{address}</code>",
            parse_mode="HTML",
        )

    async def handle_crypto_message(self, message: Message) -> bool:
        uid   = message.from_user.id
        state = _session_get(uid)
        if not state or state.get("step") != "waiting_txid":
            return False
        return await self._handle_txid(message, state["network"])

    async def _handle_txid(self, message: Message, network: str) -> bool:
        from strings import t
        uid  = message.from_user.id
        cid  = message.chat.id
        txid = (message.text or "").strip()
        lang = await self.db.get_user_lang(uid)
        _session_clear(uid)

        if txid.lower() in _USED_TXIDS or await self.db.is_txid_used(txid):
            await self.bot.send_message(cid, "⛔ <b>هذا الـ TXID مستخدم مسبقاً!</b>",
                                        parse_mode="HTML")
            return True

        check_msg = await self.bot.send_message(cid, "🔍 <b>جارٍ التحقق من المعاملة...</b>",
                                                parse_mode="HTML")
        try:
            if network == "bep20":
                addr   = await self.db.get_setting("bep20_address", "")
                conf   = int(await self.db.get_setting("bep20_confirmations", "3"))
                client = BEP20Client(addr, conf)
            else:
                key    = await self.db.get_setting("trc20_api_key", "")
                addr   = await self.db.get_setting("trc20_address", "")
                conf   = int(await self.db.get_setting("trc20_confirmations", "19"))
                client = TRC20Client(key, addr, conf)

            result = await client.verify(txid)

            if not result.get("success"):
                await self.bot.edit_message_text(
                    f"❌ {result.get('error', 'خطأ')}",
                    cid, check_msg.message_id,
                )
                return True

            paid     = result["amount"]
            rate_key = "bep20_usdt_rate" if network == "bep20" else "trc20_usdt_rate"
            min_key  = "bep20_min_usdt"  if network == "bep20" else "trc20_min_usdt"
            rate     = float(await self.db.get_setting(rate_key, "1.00"))
            min_usdt = float(await self.db.get_setting(min_key, "1.00"))

            if paid < min_usdt:
                await self.bot.edit_message_text(
                    f"⚠️ المبلغ أقل من الحد الأدنى ({paid} < {min_usdt} USDT)",
                    cid, check_msg.message_id,
                )
                return True

            credit  = round(paid * rate, 4)
            new_bal = await self.db.update_balance(uid, credit)
            await self.db.save_crypto_payment(uid, txid, network, paid, credit)
            _USED_TXIDS.add(txid.lower())

            await self.bot.edit_message_text(
                t("pay_success", lang, amount=paid, credit=credit, balance=new_bal),
                cid, check_msg.message_id, parse_mode="HTML",
            )

            from config import config
            for admin_id in config.admin_ids:
                try:
                    await self.bot.send_message(
                        admin_id,
                        f"💰 دفعة جديدة\n👤 <code>{uid}</code>\n"
                        f"💵 {paid} USDT ({network.upper()})\n"
                        f"💰 ${credit:.2f} أُضيف\n🔗 <code>{txid}</code>",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.error("[Crypto] _handle_txid: %s", exc)
            await self.bot.edit_message_text(
                "❌ خطأ داخلي. أعد المحاولة.", cid, check_msg.message_id
            )
        return True
