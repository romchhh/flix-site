"""Склад акаунтів і автовидача після оплати на сайті."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from . import bot_client
from .bot_client import BotAPIError
from .crypto import decrypt, encrypt
from .db import db, new_id, now
from .totp import generate as totp_generate

log = logging.getLogger("flix.site.stock")

_CODE_LIMIT = 12
_CODE_WINDOW_MIN = 60


def init_stock_tables(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_settings (
            product_id INTEGER PRIMARY KEY,
            auto_issue INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS credentials (
            id TEXT PRIMARY KEY,
            product_id INTEGER NOT NULL,
            login TEXT NOT NULL,
            secret_enc TEXT NOT NULL,
            totp_enc TEXT,
            slots_total INTEGER NOT NULL DEFAULT 1,
            slots_used INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_credentials_product ON credentials(product_id, active);
        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            site_user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            credential_id TEXT NOT NULL,
            payment_id TEXT UNIQUE,
            bot_sub_id INTEGER,
            bot_sub_kind TEXT,
            profile_name TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (credential_id) REFERENCES credentials(id)
        );
        CREATE INDEX IF NOT EXISTS idx_deliveries_user ON deliveries(site_user_id);
        CREATE INDEX IF NOT EXISTS idx_deliveries_bot ON deliveries(bot_sub_kind, bot_sub_id);
        CREATE TABLE IF NOT EXISTS code_logs (
            id TEXT PRIMARY KEY,
            delivery_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            ip TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_code_logs_delivery ON code_logs(delivery_id, created_at);
        """
    )
    _ensure_profile_columns(conn)


def _ensure_profile_columns(conn) -> None:
    cred_cols = {row[1] for row in conn.execute("PRAGMA table_info(credentials)").fetchall()}
    if "profile_slots_enc" not in cred_cols:
        conn.execute("ALTER TABLE credentials ADD COLUMN profile_slots_enc TEXT")
    del_cols = {row[1] for row in conn.execute("PRAGMA table_info(deliveries)").fetchall()}
    if "profile_pin_enc" not in del_cols:
        conn.execute("ALTER TABLE deliveries ADD COLUMN profile_pin_enc TEXT")


def product_needs_profile_pin(product_name: str | None) -> bool:
    return bool(product_name and "hbo" in product_name.lower())


def _encode_profile_slots(slots: list[dict] | None) -> str | None:
    if not slots:
        return None
    clean: list[dict] = []
    for slot in slots:
        num = str(slot.get("num") or "").strip()
        pin = str(slot.get("pin") or "").strip()
        if num or pin:
            clean.append({"num": num, "pin": pin})
    if not clean:
        return None
    return encrypt(json.dumps(clean, ensure_ascii=False))


def _decode_profile_slots(enc: str | None) -> list[dict]:
    if not enc:
        return []
    try:
        data = json.loads(decrypt(enc))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _profile_for_slot(cred: dict, slot_index: int) -> tuple[str, str | None]:
    slots = _decode_profile_slots(cred.get("profile_slots_enc"))
    if slot_index < len(slots):
        entry = slots[slot_index]
        num = str(entry.get("num") or "").strip() or str(slot_index + 1)
        pin = str(entry.get("pin") or "").strip() or None
        profile_name = f"Профіль {num}" if num.isdigit() else num
        return profile_name, pin
    return f"Профіль {slot_index + 1}", None


def is_auto_issue(product_id: int) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT auto_issue FROM product_settings WHERE product_id = ?",
            (int(product_id),),
        ).fetchone()
    return bool(row and row["auto_issue"])


def set_auto_issue(product_id: int, enabled: bool) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO product_settings (product_id, auto_issue, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                auto_issue = excluded.auto_issue,
                updated_at = excluded.updated_at
            """,
            (int(product_id), 1 if enabled else 0, now()),
        )


def list_product_settings(product_ids: list[int]) -> dict[int, bool]:
    if not product_ids:
        return {}
    placeholders = ",".join("?" * len(product_ids))
    with db() as conn:
        rows = conn.execute(
            f"SELECT product_id, auto_issue FROM product_settings WHERE product_id IN ({placeholders})",
            [int(x) for x in product_ids],
        ).fetchall()
    return {int(r["product_id"]): bool(r["auto_issue"]) for r in rows}


def credential_public(row: dict) -> dict:
    free = max(0, int(row.get("slots_total") or 0) - int(row.get("slots_used") or 0))
    profile_slots = [
        {"num": str(s.get("num") or "").strip()}
        for s in _decode_profile_slots(row.get("profile_slots_enc"))
        if str(s.get("num") or "").strip()
    ]
    return {
        "id": row["id"],
        "productId": str(row["product_id"]),
        "login": row["login"],
        "hasTotp": bool(row.get("totp_enc")),
        "slotsTotal": int(row.get("slots_total") or 0),
        "slotsUsed": int(row.get("slots_used") or 0),
        "slotsFree": free,
        "note": row.get("note") or "",
        "active": bool(row.get("active")),
        "createdAt": row.get("created_at"),
        "profileSlots": profile_slots,
    }


def list_credentials(product_id: int | None = None) -> list[dict]:
    with db() as conn:
        if product_id is not None:
            rows = conn.execute(
                """
                SELECT * FROM credentials
                WHERE product_id = ?
                ORDER BY active DESC, slots_used DESC, created_at ASC
                """,
                (int(product_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM credentials ORDER BY product_id, active DESC, created_at ASC"
            ).fetchall()
    return [credential_public(dict(r)) for r in rows]


def add_credential(
    *,
    product_id: int,
    login: str,
    password: str,
    totp_secret: str | None = None,
    slots_total: int = 1,
    note: str = "",
    profile_slots: list[dict] | None = None,
) -> dict:
    cid = new_id()
    slots_n = max(1, int(slots_total))
    profile_enc = _encode_profile_slots(profile_slots)
    with db() as conn:
        conn.execute(
            """
            INSERT INTO credentials (
                id, product_id, login, secret_enc, totp_enc,
                slots_total, slots_used, note, active, created_at, profile_slots_enc
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1, ?, ?)
            """,
            (
                cid,
                int(product_id),
                login.strip(),
                encrypt(password),
                encrypt(totp_secret.strip()) if totp_secret and totp_secret.strip() else None,
                slots_n,
                (note or "").strip(),
                now(),
                profile_enc,
            ),
        )
        row = conn.execute("SELECT * FROM credentials WHERE id = ?", (cid,)).fetchone()
    return credential_public(dict(row))


def update_credential(
    cred_id: str,
    *,
    login: str | None = None,
    password: str | None = None,
    totp_secret: str | None = None,
    clear_totp: bool = False,
    slots_total: int | None = None,
    note: str | None = None,
    active: bool | None = None,
) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM credentials WHERE id = ?", (cred_id,)).fetchone()
        if not row:
            return None
        fields: list[str] = []
        values: list[object] = []
        if login is not None:
            fields.append("login = ?")
            values.append(login.strip())
        if password is not None and password != "":
            fields.append("secret_enc = ?")
            values.append(encrypt(password))
        if clear_totp:
            fields.append("totp_enc = ?")
            values.append(None)
        elif totp_secret is not None and totp_secret.strip():
            fields.append("totp_enc = ?")
            values.append(encrypt(totp_secret.strip()))
        if slots_total is not None:
            fields.append("slots_total = ?")
            values.append(max(int(row["slots_used"] or 0), int(slots_total)))
        if note is not None:
            fields.append("note = ?")
            values.append(note.strip())
        if active is not None:
            fields.append("active = ?")
            values.append(1 if active else 0)
        if fields:
            values.append(cred_id)
            conn.execute(f"UPDATE credentials SET {', '.join(fields)} WHERE id = ?", values)
        updated = conn.execute("SELECT * FROM credentials WHERE id = ?", (cred_id,)).fetchone()
    return credential_public(dict(updated)) if updated else None


def delete_credential(cred_id: str) -> bool:
    with db() as conn:
        used = conn.execute(
            "SELECT COUNT(*) AS c FROM deliveries WHERE credential_id = ?",
            (cred_id,),
        ).fetchone()
        if used and int(used["c"]) > 0:
            conn.execute("UPDATE credentials SET active = 0 WHERE id = ?", (cred_id,))
            return True
        cur = conn.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
    return cur.rowcount > 0


def get_delivery_by_payment(payment_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM deliveries WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()
    return dict(row) if row else None


def get_delivery_access_for_payment(site_user_id: str, payment_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            """
            SELECT d.*, c.login, c.secret_enc, c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.payment_id = ? AND d.site_user_id = ?
            LIMIT 1
            """,
            (payment_id, site_user_id),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    if not _delivery_active(data):
        return None
    return _delivery_access(data)


def totp_code_for_payment(site_user_id: str, payment_id: str, ip: str = "") -> dict:
    access = get_delivery_access_for_payment(site_user_id, payment_id)
    if not access:
        return {"ok": False, "error": "Доступ недоступний"}
    return totp_code_for_delivery(site_user_id, access["id"], ip=ip)


def totp_code_for_delivery(site_user_id: str, delivery_id: str, ip: str = "") -> dict:
    with db() as conn:
        row = conn.execute(
            """
            SELECT d.*, c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.id = ? AND d.site_user_id = ?
            LIMIT 1
            """,
            (delivery_id, site_user_id),
        ).fetchone()
        if not row or not row["totp_enc"]:
            return {"ok": False, "error": "Для цього доступу немає 2FA"}
        data = dict(row)
        if not _delivery_active(data):
            return {"ok": False, "error": "Підписка закінчилась"}
        # rate limit reuse via existing logs
        since = (datetime.utcnow() - timedelta(minutes=_CODE_WINDOW_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent = conn.execute(
            """
            SELECT COUNT(*) AS c FROM code_logs
            WHERE delivery_id = ? AND created_at >= ?
            """,
            (delivery_id, since),
        ).fetchone()
        if recent and int(recent["c"]) >= _CODE_LIMIT:
            return {"ok": False, "error": "Забагато запитів. Спробуй пізніше або напиши менеджеру."}
        conn.execute(
            "INSERT INTO code_logs (id, delivery_id, user_id, ip, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), delivery_id, site_user_id, ip or "", now()),
        )
    secret = decrypt(row["totp_enc"])
    data = totp_generate(secret)
    return {"ok": True, "code": data["code"], "secondsLeft": data["secondsLeft"]}


def append_orphan_deliveries(site_user_id: str, subs: dict) -> dict:
    """Додає в кабінет видачі без привʼязки до підписки бота (гостьові покупки)."""
    deliveries = list_deliveries_for_user(site_user_id)
    linked_ids = {
        str(sub.get("deliveryId"))
        for bucket in (subs.get("oneTime") or [], subs.get("recurring") or [])
        for sub in bucket
        if sub.get("deliveryId")
    }

    extras = []
    for row in deliveries:
        if str(row["id"]) in linked_ids:
            continue
        if not _delivery_active(row):
            continue
        access = _delivery_access(row)
        pid = access["productId"]
        extras.append({
            "id": f"del-{access['id']}",
            "botId": None,
            "productId": pid,
            "name": access.get("profileName") or f"Підписка #{pid}",
            "kind": "one_time",
            "status": "active",
            "source": "site",
            "autoIssue": is_auto_issue(int(pid)),
            "startsAt": row.get("created_at"),
            "expiresAt": access.get("expiresAt"),
            "login": access["login"],
            "password": access["password"],
            "hasTotp": access["hasTotp"],
            "deliveryId": access["id"],
            "profileName": access.get("profileName"),
            "pin": access.get("pin"),
            "photoUrl": f"/api/media/product/{access['productId']}",
        })
        linked_ids.add(str(row["id"]))
    if extras:
        subs.setdefault("oneTime", [])
        subs["oneTime"] = extras + list(subs["oneTime"])
    return subs


def list_deliveries_for_user(site_user_id: str) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT d.*, c.login, c.secret_enc, c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.site_user_id = ?
            ORDER BY d.created_at DESC
            """,
            (site_user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _delivery_active(row: dict) -> bool:
    exp = _parse_iso(row.get("expires_at"))
    if not exp:
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc)


def _sub_active(sub: dict) -> bool:
    """Доступ активний, поки не минув expiresAt (скасоване автосписання не ховає дані)."""
    exp = _parse_iso(sub.get("expiresAt"))
    if not exp:
        status = (sub.get("status") or "").lower()
        if status and status not in ("active", "cancelled", "canceled", "inactive"):
            return False
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > datetime.now(timezone.utc)


def _delivery_access(row: dict) -> dict:
    pin = None
    if row.get("profile_pin_enc"):
        try:
            pin = decrypt(row["profile_pin_enc"])
        except Exception:
            pin = None
    return {
        "id": row["id"],
        "productId": str(row["product_id"]),
        "login": row["login"],
        "password": decrypt(row["secret_enc"]),
        "hasTotp": bool(row.get("totp_enc")),
        "profileName": row.get("profile_name"),
        "pin": pin,
        "botSubId": row.get("bot_sub_id"),
        "botSubKind": row.get("bot_sub_kind"),
        "paymentId": row.get("payment_id"),
        "expiresAt": row.get("expires_at"),
    }


def delivery_for_sub(site_user_id: str, sub_id: str, sub: dict | None = None) -> dict | None:
    if sub and not _sub_active(sub):
        return None
    if (sub_id or "").startswith("del-"):
        delivery_id = sub_id[4:]
        with db() as conn:
            row = conn.execute(
                """
                SELECT d.*, c.login, c.secret_enc, c.totp_enc
                FROM deliveries d
                JOIN credentials c ON c.id = d.credential_id
                WHERE d.id = ? AND d.site_user_id = ?
                LIMIT 1
                """,
                (delivery_id, site_user_id),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        return _delivery_access(data) if _delivery_active(data) else None
    raw = (sub_id or "").replace("rec-", "").replace("one-", "")
    kind = "recurring" if sub_id.startswith("rec-") else "one_time"
    try:
        bot_sub_id = int(raw)
    except ValueError:
        return None
    with db() as conn:
        row = conn.execute(
            """
            SELECT d.*, c.login, c.secret_enc, c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.site_user_id = ? AND d.bot_sub_id = ? AND d.bot_sub_kind = ?
            LIMIT 1
            """,
            (site_user_id, bot_sub_id, kind),
        ).fetchone()
        if row:
            data = dict(row)
            if _delivery_active(data):
                return _delivery_access(data)
            return None
        row = conn.execute(
            """
            SELECT d.*, c.login, c.secret_enc, c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.site_user_id = ? AND d.bot_sub_id IS NULL
            ORDER BY d.created_at DESC
            """,
            (site_user_id,),
        ).fetchall()
    for candidate in row:
        data = dict(candidate)
        if str(data.get("bot_sub_kind") or "") == kind or not data.get("bot_sub_kind"):
            if _delivery_active(data):
                return _delivery_access(data)
    return None


def totp_code_for_sub(site_user_id: str, sub_id: str, ip: str = "", sub: dict | None = None) -> dict:
    delivery = delivery_for_sub(site_user_id, sub_id, sub=sub)
    if not delivery:
        return {"ok": False, "error": "Доступ не знайдено"}
    with db() as conn:
        row = conn.execute(
            """
            SELECT c.totp_enc
            FROM deliveries d
            JOIN credentials c ON c.id = d.credential_id
            WHERE d.id = ?
            """,
            (delivery["id"],),
        ).fetchone()
    if not row or not row["totp_enc"]:
        return {"ok": False, "error": "Для цієї підписки 2FA не налаштовано"}
    since = (datetime.utcnow() - timedelta(minutes=_CODE_WINDOW_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db() as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) AS c FROM code_logs
            WHERE delivery_id = ? AND created_at >= ?
            """,
            (delivery["id"], since),
        ).fetchone()
        if count and int(count["c"]) >= _CODE_LIMIT:
            return {"ok": False, "error": "Забагато запитів. Спробуй пізніше або напиши менеджеру."}
        conn.execute(
            "INSERT INTO code_logs (id, delivery_id, user_id, ip, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id(), delivery["id"], site_user_id, ip or "", now()),
        )
    secret = decrypt(row["totp_enc"])
    data = totp_generate(secret)
    return {"ok": True, "code": data["code"], "secondsLeft": data["secondsLeft"]}


def enrich_subscriptions(site_user_id: str, subs: dict) -> dict:
    deliveries = list_deliveries_for_user(site_user_id)
    by_bot: dict[tuple[str, int], dict] = {}
    unlinked: dict[str, list[dict]] = {}
    for row in deliveries:
        kind = row.get("bot_sub_kind")
        bot_id = row.get("bot_sub_id")
        if kind and bot_id:
            by_bot[(str(kind), int(bot_id))] = row
        else:
            unlinked.setdefault(str(row["product_id"]), []).append(row)

    def attach(sub: dict) -> None:
        kind = sub.get("kind") or "one_time"
        bot_id = sub.get("botId")
        row = None
        if bot_id:
            row = by_bot.get((kind, int(bot_id)))
        if not row:
            pid = str(sub.get("productId") or "")
            pool = unlinked.get(pid) or []
            if pool:
                row = pool.pop(0)
        if not row or not _sub_active(sub) or not _delivery_active(row):
            sub.pop("login", None)
            sub.pop("password", None)
            sub.pop("hasTotp", None)
            sub.pop("deliveryId", None)
            return
        access = _delivery_access(row)
        sub["login"] = access["login"]
        sub["password"] = access["password"]
        sub["hasTotp"] = access["hasTotp"]
        sub["profileName"] = access.get("profileName") or sub.get("profileName")
        sub["pin"] = access.get("pin")
        sub["deliveryId"] = access["id"]
        pid = sub.get("productId")
        if pid:
            try:
                sub["autoIssue"] = is_auto_issue(int(pid))
            except (TypeError, ValueError):
                sub["autoIssue"] = False

    for bucket in (subs.get("oneTime") or [], subs.get("recurring") or []):
        for sub in bucket:
            if sub.get("autoIssue") is not None:
                continue
            pid = sub.get("productId")
            if not pid:
                continue
            try:
                sub["autoIssue"] = is_auto_issue(int(pid))
            except (TypeError, ValueError):
                sub["autoIssue"] = False

    for bucket in (subs.get("oneTime") or [], subs.get("recurring") or []):
        for sub in bucket:
            attach(sub)
    return subs


async def link_delivery_to_bot_sub(payment_row: dict) -> None:
    delivery = get_delivery_by_payment(str(payment_row.get("invoice_id") or ""))
    if not delivery or delivery.get("bot_sub_id"):
        return
    bot_user_id = int(payment_row["bot_user_id"])
    product_id = int(payment_row["product_id"])
    try:
        live = await bot_client.subscriptions(bot_user_id)
    except BotAPIError as e:
        log.warning("link delivery: %s", e)
        return
    for sub in live.get("oneTime") or []:
        if str(sub.get("productId")) == str(product_id) and sub.get("botId"):
            with db() as conn:
                conn.execute(
                    """
                    UPDATE deliveries
                    SET bot_sub_id = ?, bot_sub_kind = 'one_time'
                    WHERE id = ? AND bot_sub_id IS NULL
                    """,
                    (int(sub["botId"]), delivery["id"]),
                )
            return
    for sub in live.get("recurring") or []:
        if str(sub.get("productId")) == str(product_id) and sub.get("botId"):
            with db() as conn:
                conn.execute(
                    """
                    UPDATE deliveries
                    SET bot_sub_id = ?, bot_sub_kind = 'recurring'
                    WHERE id = ? AND bot_sub_id IS NULL
                    """,
                    (int(sub["botId"]), delivery["id"]),
                )
            return


def try_deliver_for_payment(payment_row: dict, months: int = 1) -> dict:
    status = (payment_row.get("status") or "").lower()
    if status not in ("success", "paid"):
        return {"ok": False, "reason": "not_paid"}
    invoice_id = str(payment_row.get("invoice_id") or "")
    if not invoice_id:
        return {"ok": False, "reason": "no_invoice"}
    if get_delivery_by_payment(invoice_id):
        return {"ok": True, "fresh": False}
    product_id = int(payment_row["product_id"])
    if not is_auto_issue(product_id):
        return {"ok": False, "reason": "manual"}

    with db() as conn:
        cred = conn.execute(
            """
            SELECT * FROM credentials
            WHERE product_id = ? AND active = 1 AND slots_used < slots_total
            ORDER BY slots_used DESC, created_at ASC
            LIMIT 1
            """,
            (product_id,),
        ).fetchone()
        if not cred:
            log.warning("auto-issue: no stock for product %s payment %s", product_id, invoice_id)
            return {"ok": False, "reason": "no_stock"}
        cred = dict(cred)
        delivery_id = new_id()
        slot_index = int(cred["slots_used"] or 0)
        profile_name, profile_pin = _profile_for_slot(cred, slot_index)
        profile_pin_enc = encrypt(profile_pin) if profile_pin else None
        expires = (datetime.utcnow() + timedelta(days=30 * max(1, int(months)))).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE credentials SET slots_used = slots_used + 1 WHERE id = ?",
            (cred["id"],),
        )
        conn.execute(
            """
            INSERT INTO deliveries (
                id, site_user_id, product_id, credential_id, payment_id,
                profile_name, profile_pin_enc, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                delivery_id,
                payment_row["site_user_id"],
                product_id,
                cred["id"],
                invoice_id,
                profile_name,
                profile_pin_enc,
                expires,
                now(),
            ),
        )
    log.info("auto-delivered product %s for payment %s", product_id, invoice_id)
    return {"ok": True, "fresh": True, "deliveryId": delivery_id}


async def process_paid_payment(payment_row: dict) -> None:
    result = try_deliver_for_payment(payment_row, months=int(payment_row.get("months") or 1))
    if result.get("ok"):
        await link_delivery_to_bot_sub(payment_row)
