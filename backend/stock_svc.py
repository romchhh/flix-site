"""Склад акаунтів і автовидача після оплати на сайті."""
from __future__ import annotations

import json
import logging
import re
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
    _ensure_bundle_columns(conn)
    _migrate_deliveries_payment_unique(conn)


def _ensure_bundle_columns(conn) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(product_settings)").fetchall()}
    if "bundle_sources_json" not in cols:
        conn.execute("ALTER TABLE product_settings ADD COLUMN bundle_sources_json TEXT")
    del_cols = {row[1] for row in conn.execute("PRAGMA table_info(deliveries)").fetchall()}
    if "bundle_product_id" not in del_cols:
        conn.execute("ALTER TABLE deliveries ADD COLUMN bundle_product_id INTEGER")
    if "part_label" not in del_cols:
        conn.execute("ALTER TABLE deliveries ADD COLUMN part_label TEXT")


def _migrate_deliveries_payment_unique(conn) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='deliveries'"
    ).fetchone()
    if not row or not row[0]:
        return
    create_sql = row[0].upper()
    if "PAYMENT_ID" not in create_sql or "UNIQUE" not in create_sql:
        return
    conn.executescript(
        """
        CREATE TABLE deliveries__bundle (
            id TEXT PRIMARY KEY,
            site_user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            credential_id TEXT NOT NULL,
            payment_id TEXT,
            bot_sub_id INTEGER,
            bot_sub_kind TEXT,
            profile_name TEXT,
            profile_pin_enc TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            bundle_product_id INTEGER,
            part_label TEXT,
            FOREIGN KEY (credential_id) REFERENCES credentials(id)
        );
        INSERT INTO deliveries__bundle (
            id, site_user_id, product_id, credential_id, payment_id,
            bot_sub_id, bot_sub_kind, profile_name, profile_pin_enc,
            expires_at, created_at, bundle_product_id, part_label
        )
        SELECT
            id, site_user_id, product_id, credential_id, payment_id,
            bot_sub_id, bot_sub_kind, profile_name, profile_pin_enc,
            expires_at, created_at, bundle_product_id, part_label
        FROM deliveries;
        DROP TABLE deliveries;
        ALTER TABLE deliveries__bundle RENAME TO deliveries;
        CREATE INDEX IF NOT EXISTS idx_deliveries_user ON deliveries(site_user_id);
        CREATE INDEX IF NOT EXISTS idx_deliveries_bot ON deliveries(bot_sub_kind, bot_sub_id);
        CREATE INDEX IF NOT EXISTS idx_deliveries_payment ON deliveries(payment_id);
        """
    )


def _ensure_profile_columns(conn) -> None:
    cred_cols = {row[1] for row in conn.execute("PRAGMA table_info(credentials)").fetchall()}
    if "profile_slots_enc" not in cred_cols:
        conn.execute("ALTER TABLE credentials ADD COLUMN profile_slots_enc TEXT")
    del_cols = {row[1] for row in conn.execute("PRAGMA table_info(deliveries)").fetchall()}
    if "profile_pin_enc" not in del_cols:
        conn.execute("ALTER TABLE deliveries ADD COLUMN profile_pin_enc TEXT")


def product_needs_profile_pin(product_name: str | None, product_id: int | None = None) -> bool:
    if product_id is not None and is_bundle_product(int(product_id)):
        return False
    name = (product_name or "").lower()
    if "+" in name:
        return False
    return "hbo" in name


def _product_id_value(product: dict) -> int | None:
    raw = product.get("botId") or product.get("id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _product_name_by_id(product_id: int, catalog_products: list[dict]) -> str | None:
    for product in catalog_products:
        pid = _product_id_value(product)
        if pid == int(product_id):
            return (product.get("name") or "").strip() or None
    return None


def guess_bundle_sources(bundle_name: str, catalog_products: list[dict]) -> list[int]:
    if "+" not in (bundle_name or ""):
        return []
    tokens = [re.sub(r"\s+", " ", t.strip()) for t in re.split(r"\s*\+\s*", bundle_name) if t.strip()]
    if not tokens:
        return []
    candidates: list[tuple[int, str]] = []
    for product in catalog_products:
        pid = _product_id_value(product)
        pname = (product.get("name") or "").strip()
        if pid is None or not pname or "+" in pname:
            continue
        candidates.append((pid, pname.lower()))
    source_ids: list[int] = []
    used: set[int] = set()
    for token in tokens:
        tl = token.lower()
        match: int | None = None
        for pid, pl in candidates:
            if pid in used:
                continue
            if pl == tl:
                match = pid
                break
        if match is None:
            keyword = tl.split()[0]
            for pid, pl in candidates:
                if pid in used:
                    continue
                if keyword and keyword in pl.split():
                    match = pid
                    break
        if match is None:
            for pid, pl in candidates:
                if pid in used:
                    continue
                if tl in pl or pl in tl:
                    match = pid
                    break
        if match is None:
            return []
        used.add(match)
        source_ids.append(match)
    return source_ids


def _parse_bundle_parts(raw_json: str | None) -> list[dict]:
    if not raw_json:
        return []
    try:
        data = json.loads(raw_json)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    parts: list[dict] = []
    seen: set[int] = set()
    for item in data:
        if isinstance(item, dict):
            try:
                pid = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if pid in seen:
                continue
            seen.add(pid)
            name = str(item.get("name") or "").strip() or f"Товар #{pid}"
            parts.append({"id": pid, "name": name})
            continue
        try:
            pid = int(item)
        except (TypeError, ValueError):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        parts.append({"id": pid, "name": f"Товар #{pid}"})
    return parts


def get_bundle_source_parts(product_id: int) -> list[dict]:
    with db() as conn:
        row = conn.execute(
            "SELECT bundle_sources_json FROM product_settings WHERE product_id = ?",
            (int(product_id),),
        ).fetchone()
    return _parse_bundle_parts(row["bundle_sources_json"] if row else None)


def get_bundle_sources_config(product_id: int) -> list[int]:
    return [int(part["id"]) for part in get_bundle_source_parts(product_id)]


def set_bundle_sources(
    product_id: int,
    source_ids: list[int],
    catalog_products: list[dict] | None = None,
) -> None:
    clean: list[dict] = []
    seen: set[int] = set()
    for raw in source_ids:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if pid in seen:
            continue
        seen.add(pid)
        name = _product_name_by_id(pid, catalog_products or []) if catalog_products else None
        clean.append({"id": pid, "name": name or f"Товар #{pid}"})
    payload = json.dumps(clean, ensure_ascii=False) if clean else None
    with db() as conn:
        conn.execute(
            """
            INSERT INTO product_settings (product_id, auto_issue, updated_at, bundle_sources_json)
            VALUES (
                ?,
                COALESCE((SELECT auto_issue FROM product_settings WHERE product_id = ? LIMIT 1), 0),
                ?,
                ?
            )
            ON CONFLICT(product_id) DO UPDATE SET
                bundle_sources_json = excluded.bundle_sources_json,
                updated_at = excluded.updated_at
            """,
            (int(product_id), int(product_id), now(), payload),
        )


def ensure_bundle_sources(catalog_products: list[dict]) -> None:
    for product in catalog_products:
        pid = _product_id_value(product)
        if pid is None or get_bundle_sources_config(pid):
            continue
        guessed = guess_bundle_sources(product.get("name") or "", catalog_products)
        if guessed:
            set_bundle_sources(pid, guessed, catalog_products)


def resolve_bundle_sources(product_id: int, catalog_products: list[dict] | None = None) -> list[int]:
    stored = get_bundle_sources_config(product_id)
    if stored:
        return stored
    if not catalog_products:
        return []
    product = next((p for p in catalog_products if _product_id_value(p) == int(product_id)), None)
    if not product:
        return []
    guessed = guess_bundle_sources(product.get("name") or "", catalog_products)
    if guessed:
        set_bundle_sources(int(product_id), guessed, catalog_products)
    return guessed


def is_bundle_product(product_id: int) -> bool:
    return bool(get_bundle_sources_config(int(product_id)))


def bundle_source_labels(product_id: int, catalog_products: list[dict] | None = None) -> list[dict]:
    parts = get_bundle_source_parts(product_id)
    if parts:
        return [{"id": str(part["id"]), "name": part["name"]} for part in parts]
    return [
        {
            "id": str(source_id),
            "name": _product_name_by_id(source_id, catalog_products or []) or f"Товар #{source_id}",
        }
        for source_id in resolve_bundle_sources(product_id, catalog_products)
    ]


def free_slots_for_product(product_id: int) -> int:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT slots_total, slots_used FROM credentials
            WHERE product_id = ? AND active = 1
            """,
            (int(product_id),),
        ).fetchall()
    total = 0
    for row in rows:
        total += max(0, int(row["slots_total"] or 0) - int(row["slots_used"] or 0))
    return total


def bundle_stock_free(product_id: int, catalog_products: list[dict] | None = None) -> int | None:
    sources = resolve_bundle_sources(product_id, catalog_products)
    if not sources:
        return None
    counts = [free_slots_for_product(source_id) for source_id in sources]
    return min(counts) if counts else 0


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


def get_deliveries_by_payment(payment_id: str, site_user_id: str | None = None) -> list[dict]:
    with db() as conn:
        if site_user_id:
            rows = conn.execute(
                """
                SELECT d.*, c.login, c.secret_enc, c.totp_enc
                FROM deliveries d
                JOIN credentials c ON c.id = d.credential_id
                WHERE d.payment_id = ? AND d.site_user_id = ?
                ORDER BY d.created_at ASC, d.id ASC
                """,
                (payment_id, site_user_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.*, c.login, c.secret_enc, c.totp_enc
                FROM deliveries d
                JOIN credentials c ON c.id = d.credential_id
                WHERE d.payment_id = ?
                ORDER BY d.created_at ASC, d.id ASC
                """,
                (payment_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_delivery_by_payment(payment_id: str) -> dict | None:
    rows = get_deliveries_by_payment(payment_id)
    return rows[0] if rows else None


def _bundle_delivery_complete(payment_id: str, bundle_product_id: int, site_user_id: str) -> bool:
    sources = get_bundle_sources_config(bundle_product_id)
    if not sources:
        return bool(get_delivery_by_payment(payment_id))
    rows = get_deliveries_by_payment(payment_id, site_user_id)
    delivered = {int(r["product_id"]) for r in rows if _delivery_active(r)}
    return all(source_id in delivered for source_id in sources)


def _access_parts_from_rows(rows: list[dict]) -> list[dict]:
    parts = []
    for row in rows:
        if not _delivery_active(row):
            continue
        access = _delivery_access(row)
        if access.get("partLabel"):
            access["label"] = access["partLabel"]
        parts.append(access)
    return parts


def delivery_admin_payload(payment_row: dict) -> dict:
    """Дані автовидачі для повідомлення адміну в боті."""
    invoice_id = str(payment_row.get("invoice_id") or "")
    site_user_id = str(payment_row.get("site_user_id") or "")
    try:
        product_id = int(payment_row["product_id"])
    except (TypeError, ValueError, KeyError):
        return {"autoIssue": False, "delivered": False}
    auto_issue = is_auto_issue(product_id)
    access = get_delivery_access_for_payment(site_user_id, invoice_id) if invoice_id and site_user_id else None
    payload: dict = {"autoIssue": auto_issue, "delivered": bool(access)}
    if not access:
        return payload
    if access.get("bundle") and access.get("parts"):
        payload["parts"] = access["parts"]
        first = access["parts"][0]
        payload.update({
            "login": first.get("login"),
            "password": first.get("password"),
            "profileName": first.get("profileName"),
            "pin": first.get("pin"),
        })
        return payload
    payload.update({
        "login": access.get("login"),
        "password": access.get("password"),
        "profileName": access.get("profileName"),
        "pin": access.get("pin"),
    })
    return payload


def get_delivery_access_for_payment(site_user_id: str, payment_id: str) -> dict | None:
    rows = get_deliveries_by_payment(payment_id, site_user_id)
    if not rows:
        return None
    parts = _access_parts_from_rows(rows)
    if not parts:
        return None
    if len(parts) == 1 and not parts[0].get("bundleProductId"):
        return parts[0]
    return {
        "id": parts[0]["id"],
        "bundle": True,
        "parts": parts,
        "login": parts[0].get("login"),
        "password": parts[0].get("password"),
        "hasTotp": any(p.get("hasTotp") for p in parts),
    }


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
    seen_bundle_payments: set[str] = set()
    for row in deliveries:
        if str(row["id"]) in linked_ids:
            continue
        if not _delivery_active(row):
            continue
        bundle_product_id = row.get("bundle_product_id")
        payment_id = row.get("payment_id")
        if bundle_product_id and payment_id:
            bundle_key = f"{payment_id}:{bundle_product_id}"
            if bundle_key in seen_bundle_payments:
                linked_ids.add(str(row["id"]))
                continue
            sibling_rows = [
                r for r in deliveries
                if r.get("payment_id") == payment_id
                and str(r.get("bundle_product_id") or "") == str(bundle_product_id)
            ]
            parts = _access_parts_from_rows(sibling_rows)
            if not parts:
                continue
            seen_bundle_payments.add(bundle_key)
            for sibling in sibling_rows:
                linked_ids.add(str(sibling["id"]))
            first = parts[0]
            extras.append({
                "id": f"del-{first['id']}",
                "botId": None,
                "productId": str(bundle_product_id),
                "name": f"Набір #{bundle_product_id}",
                "kind": "one_time",
                "status": "active",
                "source": "site",
                "autoIssue": is_auto_issue(int(bundle_product_id)),
                "startsAt": row.get("created_at"),
                "expiresAt": first.get("expiresAt"),
                "login": first.get("login"),
                "password": first.get("password"),
                "hasTotp": any(p.get("hasTotp") for p in parts),
                "deliveryId": first.get("id"),
                "profileName": first.get("profileName"),
                "pin": first.get("pin"),
                "accessParts": [
                    {
                        "label": part.get("partLabel") or part.get("label"),
                        "login": part.get("login"),
                        "password": part.get("password"),
                        "profileName": part.get("profileName"),
                        "pin": part.get("pin"),
                        "hasTotp": part.get("hasTotp"),
                        "deliveryId": part.get("id"),
                    }
                    for part in parts
                ],
                "photoUrl": f"/api/media/product/{bundle_product_id}",
            })
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
        "bundleProductId": str(row["bundle_product_id"]) if row.get("bundle_product_id") else None,
        "partLabel": row.get("part_label"),
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
            elif pid and is_bundle_product(int(pid)):
                bundle_rows = [
                    r for r in deliveries
                    if str(r.get("bundle_product_id") or "") == pid and _delivery_active(r)
                ]
                if bundle_rows:
                    row = bundle_rows[0]
        if not row or not _sub_active(sub) or not _delivery_active(row):
            sub.pop("login", None)
            sub.pop("password", None)
            sub.pop("hasTotp", None)
            sub.pop("deliveryId", None)
            sub.pop("accessParts", None)
            return
        payment_id = row.get("payment_id")
        bundle_id = row.get("bundle_product_id")
        sibling_rows = []
        if payment_id and bundle_id:
            sibling_rows = [
                r for r in deliveries
                if r.get("payment_id") == payment_id and str(r.get("bundle_product_id") or "") == str(bundle_id)
            ]
        parts = _access_parts_from_rows(sibling_rows or [row])
        if len(parts) > 1 or (parts and parts[0].get("bundleProductId")):
            sub["accessParts"] = [
                {
                    "label": part.get("partLabel") or part.get("label"),
                    "login": part.get("login"),
                    "password": part.get("password"),
                    "profileName": part.get("profileName"),
                    "pin": part.get("pin"),
                    "hasTotp": part.get("hasTotp"),
                    "deliveryId": part.get("id"),
                }
                for part in parts
            ]
            sub["login"] = parts[0].get("login")
            sub["password"] = parts[0].get("password")
            sub["hasTotp"] = any(p.get("hasTotp") for p in parts)
            sub["profileName"] = parts[0].get("profileName")
            sub["pin"] = parts[0].get("pin")
            sub["deliveryId"] = parts[0].get("id")
        else:
            access = parts[0]
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
    invoice_id = str(payment_row.get("invoice_id") or "")
    deliveries = get_deliveries_by_payment(invoice_id)
    if not deliveries:
        return
    delivery = deliveries[0]
    if delivery.get("bot_sub_id"):
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
                    WHERE payment_id = ? AND bot_sub_id IS NULL
                    """,
                    (int(sub["botId"]), invoice_id),
                )
            return
    for sub in live.get("recurring") or []:
        if str(sub.get("productId")) == str(product_id) and sub.get("botId"):
            with db() as conn:
                conn.execute(
                    """
                    UPDATE deliveries
                    SET bot_sub_id = ?, bot_sub_kind = 'recurring'
                    WHERE payment_id = ? AND bot_sub_id IS NULL
                    """,
                    (int(sub["botId"]), invoice_id),
                )
            return


def _allocate_delivery(
    conn,
    *,
    payment_row: dict,
    product_id: int,
    source_product_id: int,
    bundle_product_id: int | None,
    part_label: str | None,
    months: int,
) -> str | None:
    cred = conn.execute(
        """
        SELECT * FROM credentials
        WHERE product_id = ? AND active = 1 AND slots_used < slots_total
        ORDER BY slots_used DESC, created_at ASC
        LIMIT 1
        """,
        (int(source_product_id),),
    ).fetchone()
    if not cred:
        return None
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
            profile_name, profile_pin_enc, expires_at, created_at,
            bundle_product_id, part_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            delivery_id,
            payment_row["site_user_id"],
            int(source_product_id),
            cred["id"],
            str(payment_row.get("invoice_id") or ""),
            profile_name,
            profile_pin_enc,
            expires,
            now(),
            int(bundle_product_id) if bundle_product_id else None,
            part_label,
        ),
    )
    return delivery_id


def try_deliver_bundle(payment_row: dict, sources: list[int], months: int = 1) -> dict:
    invoice_id = str(payment_row.get("invoice_id") or "")
    site_user_id = str(payment_row.get("site_user_id") or "")
    bundle_product_id = int(payment_row["product_id"])
    if _bundle_delivery_complete(invoice_id, bundle_product_id, site_user_id):
        return {"ok": True, "fresh": False}

    part_map = {int(part["id"]): part["name"] for part in get_bundle_source_parts(bundle_product_id)}
    delivery_ids: list[str] = []
    with db() as conn:
        for source_id in sources:
            available = conn.execute(
                """
                SELECT COUNT(*) AS c FROM credentials
                WHERE product_id = ? AND active = 1 AND slots_used < slots_total
                """,
                (int(source_id),),
            ).fetchone()
            if not available or int(available["c"]) <= 0:
                log.warning(
                    "auto-issue bundle: no stock for source %s bundle %s payment %s",
                    source_id,
                    bundle_product_id,
                    invoice_id,
                )
                conn.rollback()
                return {"ok": False, "reason": "no_stock", "missingProductId": int(source_id)}
        for source_id in sources:
            delivery_id = _allocate_delivery(
                conn,
                payment_row=payment_row,
                product_id=bundle_product_id,
                source_product_id=int(source_id),
                bundle_product_id=bundle_product_id,
                part_label=part_map.get(int(source_id)),
                months=months,
            )
            if not delivery_id:
                conn.rollback()
                return {"ok": False, "reason": "no_stock", "missingProductId": int(source_id)}
            delivery_ids.append(delivery_id)

    log.info(
        "auto-delivered bundle %s (%s parts) for payment %s",
        bundle_product_id,
        len(delivery_ids),
        invoice_id,
    )
    return {"ok": True, "fresh": True, "deliveryIds": delivery_ids}


def try_deliver_for_payment(payment_row: dict, months: int = 1) -> dict:
    status = (payment_row.get("status") or "").lower()
    if status not in ("success", "paid"):
        return {"ok": False, "reason": "not_paid"}
    invoice_id = str(payment_row.get("invoice_id") or "")
    if not invoice_id:
        return {"ok": False, "reason": "no_invoice"}
    product_id = int(payment_row["product_id"])
    if not is_auto_issue(product_id):
        return {"ok": False, "reason": "manual"}

    bundle_sources = get_bundle_sources_config(product_id)
    if bundle_sources:
        return try_deliver_bundle(payment_row, bundle_sources, months=months)

    if get_delivery_by_payment(invoice_id):
        return {"ok": True, "fresh": False}

    with db() as conn:
        delivery_id = _allocate_delivery(
            conn,
            payment_row=payment_row,
            product_id=product_id,
            source_product_id=product_id,
            bundle_product_id=None,
            part_label=None,
            months=months,
        )
        if not delivery_id:
            log.warning("auto-issue: no stock for product %s payment %s", product_id, invoice_id)
            return {"ok": False, "reason": "no_stock"}
    log.info("auto-delivered product %s for payment %s", product_id, invoice_id)
    return {"ok": True, "fresh": True, "deliveryId": delivery_id}


async def process_paid_payment(payment_row: dict) -> None:
    result = try_deliver_for_payment(payment_row, months=int(payment_row.get("months") or 1))
    if result.get("ok"):
        await link_delivery_to_bot_sub(payment_row)
