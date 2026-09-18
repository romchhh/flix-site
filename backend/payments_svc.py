"""Платежі сайту: Mono на сайті, синхронізація з ботом коли API доступне."""
from __future__ import annotations

import asyncio
import logging

from . import bot_client
from .bot_client import BotAPIError
from .db import db, now

log = logging.getLogger("flix.site.payments")

_PAID = frozenset({"success", "paid", "confirmed"})
_FAILED = frozenset({"failure", "failed", "expired", "reversed", "canceled", "cancelled"})


def save_site_payment(
    *,
    payment_id: str,
    invoice_id: str,
    site_user_id: str,
    bot_user_id: int,
    telegram_id: int | None,
    product_id: int,
    months: int,
    amount: float,
    payment_type: str,
    wallet_id: str | None,
    username: str | None,
) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO site_payments (
                payment_id, invoice_id, site_user_id, bot_user_id, telegram_id,
                product_id, months, amount, payment_type, wallet_id, username,
                status, mono_status, synced_to_bot, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, 0, ?, ?)
            ON CONFLICT(invoice_id) DO UPDATE SET
                payment_id = excluded.payment_id,
                bot_user_id = excluded.bot_user_id,
                amount = excluded.amount,
                updated_at = excluded.updated_at
            """,
            (
                payment_id,
                invoice_id,
                site_user_id,
                int(bot_user_id),
                telegram_id,
                int(product_id),
                int(months),
                float(amount),
                payment_type,
                wallet_id,
                username,
                now(),
                now(),
            ),
        )


def get_site_payment(ref: str) -> dict | None:
    clean = (ref or "").strip()
    if not clean:
        return None
    with db() as conn:
        row = conn.execute(
            """
            SELECT * FROM site_payments
            WHERE payment_id = ? OR invoice_id = ?
            LIMIT 1
            """,
            (clean, clean),
        ).fetchone()
    return dict(row) if row else None


def update_mono_status(invoice_id: str, mono_status: str) -> dict | None:
    status = (mono_status or "").strip().lower()
    payment_status = "pending"
    if status in _PAID:
        payment_status = "success"
    elif status in _FAILED:
        payment_status = "failed"
    with db() as conn:
        conn.execute(
            """
            UPDATE site_payments
            SET mono_status = ?, status = ?, updated_at = ?
            WHERE invoice_id = ?
            """,
            (status, payment_status, now(), invoice_id),
        )
        row = conn.execute(
            "SELECT * FROM site_payments WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()
    return dict(row) if row else None


def payment_public(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "payment_id": row.get("payment_id"),
        "invoice_id": row.get("invoice_id"),
        "status": row.get("status") or "pending",
        "product_id": row.get("product_id"),
        "amount": row.get("amount"),
        "months": row.get("months"),
    }


def list_unsynced(limit: int = 50) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM site_payments
            WHERE synced_to_bot = 0
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


async def sync_payment_to_bot(row: dict) -> bool:
    try:
        await bot_client.record_payment(
            user_id=int(row["bot_user_id"]),
            product_id=int(row["product_id"]),
            months=int(row["months"]),
            amount=float(row["amount"]),
            invoice_id=str(row["invoice_id"]),
            payment_id=str(row["payment_id"]),
            payment_type=str(row.get("payment_type") or "one_time"),
            wallet_id=row.get("wallet_id"),
            username=row.get("username"),
        )
    except BotAPIError as e:
        log.warning("sync payment %s to bot: %s", row.get("invoice_id"), e)
        return False
    with db() as conn:
        conn.execute(
            "UPDATE site_payments SET synced_to_bot = 1, updated_at = ? WHERE invoice_id = ?",
            (now(), row["invoice_id"]),
        )
    return True


async def sync_payment_to_bot_by_ref(ref: str) -> bool:
    row = get_site_payment(ref)
    if not row or row.get("synced_to_bot"):
        return bool(row and row.get("synced_to_bot"))
    return await sync_payment_to_bot(row)


async def forward_mono_to_bot(payload: dict) -> bool:
    try:
        await bot_client.forward_mono_webhook(payload)
        return True
    except BotAPIError as e:
        log.warning("mono webhook forward: %s", e)
        return False


async def handle_mono_webhook(payload: dict) -> None:
    invoice_id = str(payload.get("invoiceId") or payload.get("invoice_id") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    if invoice_id:
        update_mono_status(invoice_id, status)
        row = get_site_payment(invoice_id)
        if row and not row.get("synced_to_bot"):
            await sync_payment_to_bot(row)
    await forward_mono_to_bot(payload)


async def sync_pending_to_bot(limit: int = 50) -> int:
    rows = list_unsynced(limit)
    ok = 0
    for row in rows:
        if await sync_payment_to_bot(row):
            ok += 1
        await asyncio.sleep(0.15)
    if ok:
        log.info("synced %s pending payment(s) to bot", ok)
    return ok
