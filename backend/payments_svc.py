"""Платежі сайту: Mono на сайті, синхронізація з ботом коли API доступне."""
from __future__ import annotations

import asyncio
import json
import logging

from . import bot_client, stock_svc
from .bot_client import BotAPIError
from .db import db, now

log = logging.getLogger("flix.site.payments")

_PAID = frozenset({"success", "paid", "confirmed"})
_FAILED = frozenset({"failure", "failed", "expired", "reversed", "canceled", "cancelled"})


def _ensure_webhook_col() -> None:
    with db() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(site_payments)").fetchall()}
        if "last_webhook" not in cols:
            conn.execute("ALTER TABLE site_payments ADD COLUMN last_webhook TEXT")


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
    _ensure_webhook_col()
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


def update_mono_status(invoice_id: str, mono_status: str, webhook: dict | None = None) -> dict | None:
    _ensure_webhook_col()
    status = (mono_status or "").strip().lower()
    payment_status = "pending"
    if status in _PAID:
        payment_status = "success"
    elif status in _FAILED:
        payment_status = "failed"
    payload = json.dumps(webhook, ensure_ascii=False, default=str) if webhook else None
    with db() as conn:
        if payload:
            conn.execute(
                """
                UPDATE site_payments
                SET mono_status = ?, status = ?, last_webhook = ?, updated_at = ?
                WHERE invoice_id = ?
                """,
                (status, payment_status, payload, now(), invoice_id),
            )
        else:
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


def unsynced_count() -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM site_payments WHERE synced_to_bot = 0"
        ).fetchone()
    return int(row["c"] if row else 0)


def _webhook_for_row(row: dict) -> dict:
    raw = row.get("last_webhook")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and (data.get("invoiceId") or data.get("invoice_id")):
                return data
        except (TypeError, json.JSONDecodeError):
            pass
    status = (row.get("mono_status") or row.get("status") or "success").lower()
    if status in _PAID:
        status = "success"
    return {
        "invoiceId": row["invoice_id"],
        "status": status,
        "reference": row.get("payment_id"),
    }


async def sync_payment_to_bot(row: dict) -> bool:
    """Записати платіж у бота; склад спочатку, потім форвард вебхука боту."""
    # Автовидача зі складу сайту — до повідомлень бота
    if (row.get("status") or "").lower() in _PAID:
        await stock_svc.process_paid_payment(row)

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

    mono = (row.get("mono_status") or "").lower()
    st = (row.get("status") or "").lower()
    if mono in _PAID or st in _PAID or mono == "success" or st == "success":
        ok = await forward_mono_to_bot(_webhook_for_row(row))
        if not ok:
            log.warning(
                "payment %s recorded in bot, webhook forward failed — bot cron should fulfill",
                row.get("invoice_id"),
            )

    with db() as conn:
        conn.execute(
            "UPDATE site_payments SET synced_to_bot = 1, updated_at = ? WHERE invoice_id = ?",
            (now(), row["invoice_id"]),
        )
    log.info("synced payment %s to bot (status=%s)", row.get("invoice_id"), row.get("status"))
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
        update_mono_status(invoice_id, status, webhook=payload)
        row = get_site_payment(invoice_id)
        if row:
            # Склад одразу після оплати, навіть якщо синк з ботом уже був
            if status in _PAID:
                await stock_svc.process_paid_payment(row)
            if not row.get("synced_to_bot"):
                await sync_payment_to_bot(get_site_payment(invoice_id) or row)
                return
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
    elif rows:
        log.warning("still %s unsynced payment(s); bot API may be offline", len(rows))
    return ok


def list_pending_site_payments(limit: int = 30) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM site_payments
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


async def refresh_payment_from_mono(ref: str) -> dict | None:
    """Підтягнути статус одного платежу з Mono і видати зі складу, якщо оплачено."""
    from . import monopay

    row = get_site_payment(ref)
    if not row:
        return None
    invoice_id = str(row.get("invoice_id") or "")
    status = (row.get("status") or "").lower()
    if status in _PAID:
        await stock_svc.process_paid_payment(row)
        return get_site_payment(invoice_id or ref)
    if not invoice_id:
        return row
    try:
        data = await monopay.fetch_invoice_status(invoice_id)
    except Exception:
        log.exception("mono status poll %s", invoice_id)
        return row
    if not data:
        return row
    mono_status = str(data.get("status") or "").strip().lower()
    if not mono_status:
        return row
    update_mono_status(invoice_id, mono_status, webhook=data)
    fresh = get_site_payment(invoice_id)
    if not fresh:
        return row
    if mono_status in _PAID:
        await stock_svc.process_paid_payment(fresh)
        if not fresh.get("synced_to_bot"):
            await sync_payment_to_bot(fresh)
        else:
            await forward_mono_to_bot(_webhook_for_row(fresh))
    return get_site_payment(invoice_id or ref)


async def refresh_user_payments(site_user_id: str) -> None:
    """Перевірити pending-платежі користувача і довидачу зі складу після оплати."""
    with db() as conn:
        pending = conn.execute(
            """
            SELECT payment_id FROM site_payments
            WHERE site_user_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 8
            """,
            (site_user_id,),
        ).fetchall()
        paid = conn.execute(
            """
            SELECT invoice_id, product_id FROM site_payments
            WHERE site_user_id = ? AND status = 'success'
            ORDER BY created_at DESC
            LIMIT 12
            """,
            (site_user_id,),
        ).fetchall()
    for row in pending:
        await refresh_payment_from_mono(str(row["payment_id"]))
        await asyncio.sleep(0.05)
    for row in paid:
        if not stock_svc.is_auto_issue(int(row["product_id"])):
            continue
        invoice_id = str(row["invoice_id"] or "")
        if stock_svc.get_delivery_by_payment(invoice_id):
            continue
        full = get_site_payment(invoice_id)
        if full:
            await stock_svc.process_paid_payment(full)


async def refresh_pending_from_mono(limit: int = 20) -> int:
    """Якщо вебхук не дійшов — підтягнути статус з Mono і видати зі складу."""
    ok = 0
    for row in list_pending_site_payments(limit):
        invoice_id = str(row.get("invoice_id") or "")
        if not invoice_id:
            continue
        fresh = await refresh_payment_from_mono(invoice_id)
        if fresh and (fresh.get("status") or "").lower() in _PAID:
            ok += 1
        await asyncio.sleep(0.1)
    if ok:
        log.info("refreshed %s pending payment(s) from Mono", ok)
    return ok


async def sync_loop(interval_s: float = 45.0) -> None:
    """Фоновий ретрай: синк з ботом + підстраховка статусу Mono."""
    await asyncio.sleep(3)
    while True:
        try:
            if unsynced_count() > 0:
                await sync_pending_to_bot()
            await refresh_pending_from_mono()
        except Exception:
            log.exception("payment sync loop")
        await asyncio.sleep(interval_s)
