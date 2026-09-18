"""Створення рахунків Monobank з вебхуком на сайт."""
from __future__ import annotations

import time
import uuid

import httpx

from .settings import APP_URL, MONO_XTOKEN
HOST = "https://api.monobank.ua/"


class MonoError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def webhook_url() -> str:
    """Завжди на сайт: склад/автовидача, далі форвард у бота."""
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


async def fetch_invoice_status(invoice_id: str) -> dict | None:
    """Статус інвойсу в Mono (підстраховка, якщо вебхук не дійшов)."""
    import logging
    token = MONO_XTOKEN
    if not token or not invoice_id:
        return None
    headers = {"X-Token": token}
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.get(
                f"{HOST}api/merchant/invoice/status",
                params={"invoiceId": invoice_id},
                headers=headers,
            )
        except httpx.RequestError as e:
            logging.getLogger("flix.site.mono").warning("status check %s: %s", invoice_id, e)
            return None
    if res.status_code >= 400:
        return None
    try:
        return res.json()
    except Exception:
        return None
