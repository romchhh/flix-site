"""Створення рахунків Monobank з вебхуком на сайт."""
from __future__ import annotations

import time
import uuid

import httpx

from urllib.parse import urlparse

from .settings import APP_URL, BOT_API_URL, MONO_XTOKEN
HOST = "https://api.monobank.ua/"


class MonoError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def webhook_url() -> str:
    bot = (BOT_API_URL or "").rstrip("/")
    host = (urlparse(bot).hostname or "").lower()
    if bot and host not in ("127.0.0.1", "localhost", "::1"):
        return f"{bot}/api/v1/webhooks/mono"
    return f"{APP_URL.rstrip('/')}/api/webhooks/mono"


async def _post(path: str, payload: dict) -> dict:
    token = MONO_XTOKEN
    if not token:
        raise MonoError("Немає MONO_XTOKEN — неможливо створити рахунок", 503)
    headers = {"X-Token": token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(f"{HOST}{path}", json=payload, headers=headers)
        except httpx.RequestError as e:
            raise MonoError(f"Monobank недоступний: {e}") from e
    if res.status_code >= 400:
        raise MonoError(f"Monobank: {res.text}", min(res.status_code, 502))
    try:
        return res.json()
    except Exception as e:
        raise MonoError("Некоректна відповідь Monobank") from e


async def create_invoice(
    *,
    user_id: int,
    product_name: str,
    months: int,
    amount_uah: float,
    redirect_url: str,
    subscription: bool,
    payment_id: str | None = None,
) -> dict:
    amount_kop = int(round(float(amount_uah) * 100))
    hook = webhook_url()
    if subscription:
        local_id = payment_id or f"subscription_{user_id}_{int(time.time())}"
        wallet_id = f"wallet_{user_id}_{uuid.uuid4().hex[:8]}"
        payload = {
            "amount": amount_kop,
            "ccy": 980,
            "merchantPaymInfo": {
                "reference": local_id,
                "destination": f"Підписка на {product_name}",
                "comment": f"Підписка на {product_name} на {months} міс.",
                "basketOrder": [{
                    "name": product_name,
                    "qty": 1,
                    "sum": amount_kop,
                    "total": amount_kop,
                    "unit": "шт.",
                    "code": f"sub_{product_name}",
                }],
            },
            "redirectUrl": redirect_url,
            "webHookUrl": hook,
            "validity": 3600,
            "paymentType": "debit",
            "saveCardData": {"saveCard": True, "walletId": wallet_id},
        }
        result = await _post("api/merchant/invoice/create", payload)
        return {
            "payment_id": local_id,
            "invoice_id": result["invoiceId"],
            "page_url": result["pageUrl"],
            "wallet_id": wallet_id,
            "payment_type": "subscription",
        }

    local_id = payment_id or f"order_{user_id}_{int(time.time())}"
    payload = {
        "amount": amount_kop,
        "ccy": 980,
        "description": f"Оплата {product_name} на {months} міс.",
        "orderReference": local_id,
        "destination": "Оплата на сайті flixмаркет",
        "redirectUrl": redirect_url,
        "webHookUrl": hook,
        "merchantPaymInfo": {
            "basketOrder": [{
                "name": product_name,
                "qty": 1,
                "sum": amount_kop,
                "code": f"prod_{product_name}",
                "unit": "шт.",
            }],
        },
    }
    result = await _post("api/merchant/invoice/create", payload)
    return {
        "payment_id": local_id,
        "invoice_id": result["invoiceId"],
        "page_url": result["pageUrl"],
        "wallet_id": None,
        "payment_type": "one_time",
    }
