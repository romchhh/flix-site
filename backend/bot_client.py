from __future__ import annotations

import logging

import httpx

from .settings import BOT_API_KEY, BOT_API_URL

log = logging.getLogger(__name__)


class BotAPIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


async def bot_request(method: str, path: str, json: dict | None = None, params: dict | None = None):
    url = f"{BOT_API_URL}{path}"
    headers = {"X-API-Key": BOT_API_KEY}
    async with httpx.AsyncClient(timeout=40.0) as client:
        try:
            res = await client.request(method, url, headers=headers, json=json, params=params)
        except httpx.RequestError as e:
            raise BotAPIError(502, f"Бот API недоступне: {e}") from e
    if res.status_code >= 400:
        try:
            data = res.json()
            message = data.get("error") or res.text
        except Exception:
            message = res.text
        raise BotAPIError(res.status_code, message)
    if res.status_code == 204 or not res.content:
        return {}
    return res.json()


async def catalog():
    return await bot_request("GET", "/api/v1/catalog")


async def start_web_login(origin: str = ""):
    payload = {"origin": origin} if origin else None
    return await bot_request("POST", "/api/v1/web-login", json=payload)


async def web_login_status(token: str):
    return await bot_request("GET", f"/api/v1/web-login/{token}")


async def product(product_id: str):
    return await bot_request("GET", f"/api/v1/products/{product_id}")


async def ensure_user(*, email: str | None = None, telegram_id: int | None = None, username: str | None = None):
    payload: dict = {}
    if email:
        payload["email"] = email
    if telegram_id:
        payload["telegram_id"] = telegram_id
    if username:
        payload["username"] = username
    return await bot_request("POST", "/api/v1/users", json=payload)


async def consume_link_code(code: str):
    return await bot_request("POST", "/api/v1/link-codes/consume", json={"code": code})


async def link_user(site_user_id: int, telegram_id: int, username: str | None = None, email: str | None = None):
    return await bot_request(
        "POST",
        "/api/v1/users/link",
        json={
            "site_user_id": site_user_id,
            "telegram_id": telegram_id,
            "username": username,
            "email": email,
        },
    )


async def subscriptions(user_id: int):
    return await bot_request("GET", f"/api/v1/users/{user_id}/subscriptions")


async def user_payments(user_id: int):
    return await bot_request("GET", f"/api/v1/users/{user_id}/payments")


async def record_payment(
    *,
    user_id: int,
    product_id: int,
    months: int,
    amount: float,
    invoice_id: str,
    payment_id: str,
    payment_type: str,
    wallet_id: str | None = None,
    username: str | None = None,
):
    payload = {
        "user_id": user_id,
        "product_id": product_id,
        "months": months,
        "amount": amount,
        "invoice_id": invoice_id,
        "payment_id": payment_id,
        "payment_type": payment_type,
        "source": "site",
        "username": username,
    }
    if wallet_id:
        payload["wallet_id"] = wallet_id
    return await bot_request("POST", "/api/v1/payments/record", json=payload)


async def forward_mono_webhook(payload: dict):
    return await bot_request("POST", "/api/v1/webhooks/mono", json=payload)


async def fulfill_site_payment(
    *,
    invoice_id: str,
    auto_issue: bool,
    delivery: dict,
):
    return await bot_request(
        "POST",
        "/api/v1/payments/site-fulfill",
        json={
            "invoice_id": invoice_id,
            "autoIssue": auto_issue,
            "delivery": delivery,
        },
    )


async def get_payment(invoice_id: str):
    return await bot_request("GET", f"/api/v1/payments/{invoice_id}")


async def cancel_recurring(user_id: int, sub_id: int):
    return await bot_request("POST", f"/api/v1/users/{user_id}/recurring/{sub_id}/cancel")


async def admin_stats():
    return await bot_request("GET", "/api/v1/admin/stats")


async def admin_payments():
    return await bot_request("GET", "/api/v1/admin/payments")


async def admin_users(limit: int = 100):
    return await bot_request("GET", "/api/v1/admin/users", params={"limit": str(limit)})


async def bot_user(user_id: int):
    return await bot_request("GET", f"/api/v1/users/{user_id}")
