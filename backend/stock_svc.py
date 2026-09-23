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
_VERIFY_ATTEMPTS = 25


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
    _ensure_sheet_columns(conn)
    _migrate_deliveries_payment_unique(conn)
    _ensure_single_delivery_per_payment(conn)


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


def _ensure_single_delivery_per_payment(conn) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_deliveries_payment_single
        ON deliveries(payment_id)
        WHERE bundle_product_id IS NULL
          AND payment_id IS NOT NULL
          AND payment_id != ''
        """
    )


def _ensure_sheet_columns(conn) -> None:
    cred_cols = {row[1] for row in conn.execute("PRAGMA table_info(credentials)").fetchall()}
    if "external_source" not in cred_cols:
        conn.execute("ALTER TABLE credentials ADD COLUMN external_source TEXT")
    if "external_id" not in cred_cols:
        conn.execute("ALTER TABLE credentials ADD COLUMN external_id TEXT")
    if "sheet_meta" not in cred_cols:
        conn.execute("ALTER TABLE credentials ADD COLUMN sheet_meta TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_credentials_external "
        "ON credentials(external_source, external_id) WHERE external_id IS NOT NULL"
    )


def product_needs_profile_pin(product_name: str | None, product_id: int | None = None) -> bool:
    if product_id is not None and is_bundle_product(int(product_id)):
        return False
    name = (product_name or "").lower()
    if "+" in name:
        return False
    return "hbo" in name


def product_is_iptv(product_name: str | None, product_id: int | None = None) -> bool:
    if product_id is not None and is_bundle_product(int(product_id)):
        return False
    return "iptv" in (product_name or "").lower()


def _credential_is_iptv(row: dict) -> bool:
    meta = _parse_sheet_meta(row.get("sheet_meta"))
    if meta and meta.get("service") == "iptv":
        return True
    note = (row.get("note") or "").lower()
    if note.startswith("iptv:") or note.startswith("sheets:iptv:"):
        return True
    login = (row.get("login") or "").strip()
    return login.startswith("http://") or login.startswith("https://")


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


_NETFLIX_STOCK_ID: int | None = None
_NETFLIX_MONTHLY_IDS: set[int] = set()


def _is_netflix_monthly_name(name: str | None) -> bool:
    n = (name or "").lower()
    return "netflix" in n and "помісячно" in n and "+" not in n


def _is_netflix_standalone_name(name: str | None) -> bool:
    n = (name or "").lower()
    if "netflix" not in n or "+" in n or "помісячно" in n:
        return False
    return "окремий" in n or "premium" in n


def refresh_netflix_stock_aliases(catalog_products: list[dict]) -> None:
    """Помісячний Netflix і окремий акаунт — один склад."""
    global _NETFLIX_STOCK_ID, _NETFLIX_MONTHLY_IDS
    monthly_ids: set[int] = set()
    standalone_id: int | None = None
    for product in catalog_products:
        pid = _product_id_value(product)
        if pid is None:
            continue
        name = product.get("name") or ""
        if _is_netflix_monthly_name(name):
            monthly_ids.add(pid)
        elif _is_netflix_standalone_name(name):
            if standalone_id is None:
                standalone_id = pid
    _NETFLIX_STOCK_ID = standalone_id
    _NETFLIX_MONTHLY_IDS = monthly_ids


def stock_source_product_id(product_id: int, catalog_products: list[dict] | None = None) -> int:
    if catalog_products:
        refresh_netflix_stock_aliases(catalog_products)
    pid = int(product_id)
    if _NETFLIX_STOCK_ID and pid in _NETFLIX_MONTHLY_IDS:
        return _NETFLIX_STOCK_ID
    if not catalog_products and pid == 55 and (_NETFLIX_STOCK_ID == 10 or _NETFLIX_STOCK_ID is None):
        return 10
    return pid


def shares_netflix_stock(product_id: int) -> bool:
    pid = int(product_id)
    return _NETFLIX_STOCK_ID is not None and (
        pid == _NETFLIX_STOCK_ID or pid in _NETFLIX_MONTHLY_IDS
    )


def migrate_netflix_credentials(catalog_products: list[dict]) -> None:
    refresh_netflix_stock_aliases(catalog_products)
    if not _NETFLIX_STOCK_ID or not _NETFLIX_MONTHLY_IDS:
        return
    with db() as conn:
        for monthly_id in _NETFLIX_MONTHLY_IDS:
            conn.execute(
                "UPDATE credentials SET product_id = ? WHERE product_id = ?",
                (_NETFLIX_STOCK_ID, monthly_id),
            )


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


def free_slots_for_product(product_id: int, catalog_products: list[dict] | None = None) -> int:
    source_id = stock_source_product_id(product_id, catalog_products)
    with db() as conn:
        rows = conn.execute(
            """
            SELECT slots_total, slots_used FROM credentials
            WHERE product_id = ? AND active = 1
            """,
            (int(source_id),),
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


def _credential_stock_status(row: dict) -> str:
    if not row.get("active"):
        return "disabled"
    slots_total = int(row.get("slots_total") or 0)
    slots_used = int(row.get("slots_used") or 0)
    if slots_total > 0 and slots_used >= slots_total:
        return "sold"
    return "available"


def credential_public(row: dict) -> dict:
    free = max(0, int(row.get("slots_total") or 0) - int(row.get("slots_used") or 0))
    meta = _parse_sheet_meta(row.get("sheet_meta"))
    profile_slots = []
    if (meta or {}).get("service") == "hbo":
        profile_slots = [
            {"num": str(s.get("num") or "").strip()}
            for s in _decode_profile_slots(row.get("profile_slots_enc"))
            if str(s.get("num") or "").strip()
        ]
    sheet_meta = meta
    login = row.get("login") or ""
    is_url = login.startswith("http://") or login.startswith("https://")
    return {
        "id": row["id"],
        "productId": str(row["product_id"]),
        "login": login,
        "displayLogin": login if not is_url or len(login) <= 48 else f"{login[:45]}…",
        "isUrl": is_url,
        "hasTotp": bool(row.get("totp_enc")),
        "slotsTotal": int(row.get("slots_total") or 0),
        "slotsUsed": int(row.get("slots_used") or 0),
        "slotsFree": free,
        "note": row.get("note") or "",
        "active": bool(row.get("active")),
        "stockStatus": _credential_stock_status(row),
        "createdAt": row.get("created_at"),
        "soldAt": row.get("last_delivered_at"),
        "lastPaymentId": row.get("last_payment_id"),
        "profileSlots": profile_slots,
        "fromSheets": row.get("external_source") == "sheets",
        "sheetRow": sheet_meta.get("row") if sheet_meta else None,
        "sheetName": sheet_meta.get("sheet") if sheet_meta else None,
        "sheetService": sheet_meta.get("service") if sheet_meta else None,
    }


def list_credentials(product_id: int | None = None, catalog_products: list[dict] | None = None) -> list[dict]:
    if product_id is not None:
        product_id = stock_source_product_id(product_id, catalog_products)
    base_sql = """
        SELECT c.*,
            (
                SELECT d.created_at FROM deliveries d
                WHERE d.credential_id = c.id
                ORDER BY d.created_at DESC
                LIMIT 1
            ) AS last_delivered_at,
            (
                SELECT d.payment_id FROM deliveries d
                WHERE d.credential_id = c.id
                ORDER BY d.created_at DESC
                LIMIT 1
            ) AS last_payment_id
        FROM credentials c
    """
    with db() as conn:
        if product_id is not None:
            rows = conn.execute(
                f"""
                {base_sql}
                WHERE c.product_id = ?
                ORDER BY
                    CASE
                        WHEN c.active = 1 AND c.slots_used < c.slots_total THEN 0
                        WHEN c.active = 1 AND c.slots_used >= c.slots_total THEN 1
                        ELSE 2
                    END,
                    c.created_at DESC
                """,
                (int(product_id),),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                {base_sql}
                ORDER BY c.product_id,
                    CASE
                        WHEN c.active = 1 AND c.slots_used < c.slots_total THEN 0
                        WHEN c.active = 1 AND c.slots_used >= c.slots_total THEN 1
                        ELSE 2
                    END,
                    c.created_at DESC
                """
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
    catalog_products: list[dict] | None = None,
) -> dict:
    cid = new_id()
    slots_n = max(1, int(slots_total))
    profile_enc = _encode_profile_slots(profile_slots)
    storage_product_id = stock_source_product_id(product_id, catalog_products)
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
                int(storage_product_id),
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
                SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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
                SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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


def _issue_totp_code(
    *,
    delivery_id: str,
    site_user_id: str,
    totp_enc: str,
    ip: str = "",
    active_check: dict | None = None,
) -> dict:
    if active_check is not None and not _delivery_active(active_check):
        return {"ok": False, "error": "Підписка закінчилась"}
    with db() as conn:
        since_hour = (datetime.utcnow() - timedelta(minutes=_CODE_WINDOW_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent = conn.execute(
            """
            SELECT COUNT(*) AS c FROM code_logs
            WHERE delivery_id = ? AND created_at >= ?
            """,
            (delivery_id, since_hour),
        ).fetchone()
        if recent and int(recent["c"]) >= _CODE_LIMIT:
            return {"ok": False, "error": "Забагато запитів. Спробуй пізніше або напиши менеджеру."}
        since_window = (datetime.utcnow() - timedelta(seconds=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
        logged = conn.execute(
            """
            SELECT 1 FROM code_logs
            WHERE delivery_id = ? AND created_at >= ?
            LIMIT 1
            """,
            (delivery_id, since_window),
        ).fetchone()
        if not logged:
            conn.execute(
                "INSERT INTO code_logs (id, delivery_id, user_id, ip, created_at) VALUES (?, ?, ?, ?, ?)",
                (new_id(), delivery_id, site_user_id, ip or "", now()),
            )
    secret = decrypt(totp_enc)
    data = totp_generate(secret)
    return {"ok": True, "code": data["code"], "secondsLeft": data["secondsLeft"]}


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
    return _issue_totp_code(
        delivery_id=delivery_id,
        site_user_id=site_user_id,
        totp_enc=row["totp_enc"],
        ip=ip,
        active_check=data,
    )


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
            "name": _delivery_service_label(row) or f"Підписка #{pid}",
            "kind": "one_time",
            "status": "active",
            "source": "site",
            "autoIssue": is_auto_issue(int(pid)),
            "startsAt": row.get("created_at"),
            "expiresAt": access.get("expiresAt"),
            "login": access.get("login"),
            "password": access.get("password"),
            "hasTotp": access.get("hasTotp"),
            "isIptv": access.get("isIptv"),
            "playlistUrl": access.get("playlistUrl"),
            "deliveryInstructions": access.get("deliveryInstructions"),
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
            SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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


def _delivery_is_hbo(row: dict) -> bool:
    meta = _parse_sheet_meta(row.get("sheet_meta"))
    if meta and meta.get("service") == "hbo":
        return True
    label = (row.get("part_label") or "").lower()
    return "hbo" in label


def _delivery_service_label(row: dict) -> str | None:
    meta = _parse_sheet_meta(row.get("sheet_meta"))
    service = (meta or {}).get("service")
    labels = {
        "netflix": "Netflix",
        "filmix": "Filmix",
        "gpt": "ChatGPT",
        "hbo": "HBO",
        "iptv": "IPTV",
    }
    if service in labels:
        return labels[service]
    part = (row.get("part_label") or "").strip()
    return part or None


def _delivery_access(row: dict) -> dict:
    from .iptv_content import IPTV_DELIVERY_INSTRUCTIONS

    pin = None
    if row.get("profile_pin_enc"):
        try:
            pin = decrypt(row["profile_pin_enc"])
        except Exception:
            pin = None
    two_fa_url = None
    sheet_meta = _parse_sheet_meta(row.get("sheet_meta"))
    is_hbo = _delivery_is_hbo(row)
    if sheet_meta and sheet_meta.get("two_fa_url"):
        two_fa_url = sheet_meta["two_fa_url"]
    is_iptv = _credential_is_iptv(row)
    playlist_url = (sheet_meta or {}).get("playlist_url") or row.get("login")
    if is_iptv:
        return {
            "id": row["id"],
            "productId": str(row["product_id"]),
            "isIptv": True,
            "playlistUrl": playlist_url,
            "deliveryInstructions": IPTV_DELIVERY_INSTRUCTIONS,
            "login": None,
            "password": None,
            "hasTotp": False,
            "twoFaUrl": None,
            "profileName": None,
            "pin": None,
            "botSubId": row.get("bot_sub_id"),
            "botSubKind": row.get("bot_sub_kind"),
            "paymentId": row.get("payment_id"),
            "expiresAt": row.get("expires_at"),
            "bundleProductId": str(row["bundle_product_id"]) if row.get("bundle_product_id") else None,
            "partLabel": row.get("part_label") or _delivery_service_label(row),
        }
    return {
        "id": row["id"],
        "productId": str(row["product_id"]),
        "login": row["login"],
        "password": decrypt(row["secret_enc"]),
        "hasTotp": bool(row.get("totp_enc")) or bool(two_fa_url),
        "twoFaUrl": two_fa_url,
        "profileName": row.get("profile_name") if is_hbo else None,
        "pin": pin if is_hbo else None,
        "botSubId": row.get("bot_sub_id"),
        "botSubKind": row.get("bot_sub_kind"),
        "paymentId": row.get("payment_id"),
        "expiresAt": row.get("expires_at"),
        "bundleProductId": str(row["bundle_product_id"]) if row.get("bundle_product_id") else None,
        "partLabel": row.get("part_label") or _delivery_service_label(row),
    }


def delivery_for_sub(site_user_id: str, sub_id: str, sub: dict | None = None) -> dict | None:
    if sub and not _sub_active(sub):
        return None
    if (sub_id or "").startswith("del-"):
        delivery_id = sub_id[4:]
        with db() as conn:
            row = conn.execute(
                """
                SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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
            SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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
            SELECT d.*, c.login, c.secret_enc, c.totp_enc, c.sheet_meta
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
    return _issue_totp_code(
        delivery_id=delivery["id"],
        site_user_id=site_user_id,
        totp_enc=row["totp_enc"],
        ip=ip,
    )


def enrich_subscriptions(site_user_id: str, subs: dict) -> dict:
    deliveries = list_deliveries_for_user(site_user_id)
    by_bot: dict[tuple[str, int], dict] = {}
    unlinked: dict[str, list[dict]] = {}
    used_delivery_ids: set[str] = set()
    for row in deliveries:
        kind = row.get("bot_sub_kind")
        bot_id = row.get("bot_sub_id")
        if kind and bot_id:
            by_bot[(str(kind), int(bot_id))] = row
        else:
            unlinked.setdefault(str(row["product_id"]), []).append(row)

    def _take_unlinked(pool: list[dict]) -> dict | None:
        while pool:
            candidate = pool.pop(0)
            cid = str(candidate.get("id") or "")
            if cid and cid not in used_delivery_ids:
                return candidate
        return None

    def attach(sub: dict) -> None:
        kind = sub.get("kind") or "one_time"
        bot_id = sub.get("botId")
        row = None
        if bot_id:
            candidate = by_bot.get((kind, int(bot_id)))
            cid = str(candidate.get("id") or "") if candidate else ""
            if candidate and cid not in used_delivery_ids:
                row = candidate
        if not row:
            pid = str(sub.get("productId") or "")
            pool = list(unlinked.get(pid) or [])
            row = _take_unlinked(pool)
            unlinked[pid] = pool
            if not row and pid.isdigit():
                source_pid = str(stock_source_product_id(int(pid)))
                if source_pid != pid:
                    pool = list(unlinked.get(source_pid) or [])
                    row = _take_unlinked(pool)
                    unlinked[source_pid] = pool
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
        used_delivery_ids.add(str(row["id"]))
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
            for part in sibling_rows:
                used_delivery_ids.add(str(part["id"]))
        else:
            access = parts[0]
            sub["login"] = access["login"]
            sub["password"] = access["password"]
            sub["hasTotp"] = access["hasTotp"]
            sub["twoFaUrl"] = access.get("twoFaUrl")
            sub["isIptv"] = access.get("isIptv")
            sub["playlistUrl"] = access.get("playlistUrl")
            sub["deliveryInstructions"] = access.get("deliveryInstructions")
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
    def _link_kind(subs: list[dict], kind: str) -> bool:
        for sub in subs:
            if str(sub.get("productId")) != str(product_id) or not sub.get("botId"):
                continue
            bot_sub_id = int(sub["botId"])
            with db() as conn:
                taken = conn.execute(
                    """
                    SELECT 1 FROM deliveries
                    WHERE bot_sub_id = ? AND bot_sub_kind = ?
                    LIMIT 1
                    """,
                    (bot_sub_id, kind),
                ).fetchone()
                if taken:
                    continue
                conn.execute(
                    """
                    UPDATE deliveries
                    SET bot_sub_id = ?, bot_sub_kind = ?
                    WHERE payment_id = ? AND bot_sub_id IS NULL
                    """,
                    (bot_sub_id, kind, invoice_id),
                )
            return True
        return False

    if _link_kind(live.get("oneTime") or [], "one_time"):
        return
    _link_kind(live.get("recurring") or [], "recurring")


def _pick_verified_credential(conn, source_product_id: int) -> dict | None:
    """Обирає акаунт зі складу; для таблиць — перевіряє рядок у Google Sheets."""
    from . import sheets_svc

    for _ in range(_VERIFY_ATTEMPTS):
        row = conn.execute(
            """
            SELECT * FROM credentials
            WHERE product_id = ? AND active = 1 AND slots_used < slots_total
            ORDER BY
                CASE WHEN external_source = 'sheets' THEN 1 ELSE 0 END ASC,
                slots_used DESC,
                created_at ASC
            LIMIT 1
            """,
            (int(source_product_id),),
        ).fetchone()
        if not row:
            return None
        cred = dict(row)
        if cred.get("external_source") == "sheets" and not sheets_svc.verify_sheet_credential(cred):
            conn.execute("UPDATE credentials SET active = 0 WHERE id = ?", (cred["id"],))
            log.warning(
                "auto-issue: sheet row no longer free, deactivated credential %s",
                cred["id"],
            )
            continue
        return cred
    return None


def _allocate_delivery(
    conn,
    *,
    payment_row: dict,
    product_id: int,
    source_product_id: int,
    bundle_product_id: int | None,
    part_label: str | None,
    months: int,
) -> tuple[str | None, dict | None, str | None]:
    cred = _pick_verified_credential(conn, int(source_product_id))
    if not cred:
        return None, None, None
    delivery_id = new_id()
    slot_index = int(cred["slots_used"] or 0)
    profile_name, profile_pin = _profile_for_slot(cred, slot_index)
    sheet_meta = _parse_sheet_meta(cred.get("sheet_meta"))
    if sheet_meta and sheet_meta.get("service") == "hbo":
        pass  # profile_name + pin з профілю HBO
    elif sheet_meta and sheet_meta.get("service") == "gpt" and sheet_meta.get("two_fa_url"):
        pass  # 2FA через flix2fa — URL у sheet_meta
    elif sheet_meta:
        profile_name = None
        profile_pin = None
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
    return delivery_id, cred, expires


def _bundle_delivery_complete_conn(
    conn,
    payment_id: str,
    bundle_product_id: int,
    site_user_id: str,
) -> bool:
    sources = get_bundle_sources_config(bundle_product_id)
    if not sources:
        row = conn.execute(
            "SELECT 1 FROM deliveries WHERE payment_id = ? LIMIT 1",
            (payment_id,),
        ).fetchone()
        return bool(row)
    rows = conn.execute(
        """
        SELECT product_id, expires_at FROM deliveries
        WHERE payment_id = ? AND site_user_id = ?
        """,
        (payment_id, site_user_id),
    ).fetchall()
    delivered = {int(r["product_id"]) for r in rows if _delivery_active(dict(r))}
    return all(source_id in delivered for source_id in sources)


def _parse_sheet_meta(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (TypeError, json.JSONDecodeError):
        return None


def _mark_sheet_issued(cred: dict, payment_row: dict, expires_at: str, months: int) -> None:
    if cred.get("external_source") != "sheets":
        return
    meta = _parse_sheet_meta(cred.get("sheet_meta"))
    if not meta:
        return
    try:
        from . import sheets_svc

        sheets_svc.mark_row_issued(meta, payment_row, expires_at, months=months)
    except Exception as e:
        log.warning("sheet mark issued failed: %s", e)


async def sync_from_sheets(catalog_products: list[dict]) -> dict:
    from . import sheets_svc

    refresh_netflix_stock_aliases(catalog_products)
    migrate_netflix_credentials(catalog_products)
    return sheets_svc.import_stock(catalog_products)


def try_deliver_bundle(payment_row: dict, sources: list[int], months: int = 1) -> dict:
    invoice_id = str(payment_row.get("invoice_id") or "")
    site_user_id = str(payment_row.get("site_user_id") or "")
    bundle_product_id = int(payment_row["product_id"])
    part_map = {int(part["id"]): part["name"] for part in get_bundle_source_parts(bundle_product_id)}
    delivery_ids: list[str] = []
    sheet_marks: list[tuple[dict, dict, str, int]] = []
    months_n = int(payment_row.get("months") or 1)

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if _bundle_delivery_complete_conn(conn, invoice_id, bundle_product_id, site_user_id):
            return {"ok": True, "fresh": False}

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
            delivery_id, cred, expires = _allocate_delivery(
                conn,
                payment_row=payment_row,
                product_id=bundle_product_id,
                source_product_id=int(source_id),
                bundle_product_id=bundle_product_id,
                part_label=part_map.get(int(source_id)),
                months=months,
            )
            if not delivery_id or not cred or not expires:
                conn.rollback()
                return {"ok": False, "reason": "no_stock", "missingProductId": int(source_id)}
            delivery_ids.append(delivery_id)
            sheet_marks.append((cred, payment_row, expires, months_n))

    for cred, row, expires, months_mark in sheet_marks:
        _mark_sheet_issued(cred, row, expires, months_mark)

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

    source_product_id = stock_source_product_id(product_id)
    months_n = int(payment_row.get("months") or 1)
    delivery_id: str | None = None
    mark_cred: dict | None = None
    mark_expires: str | None = None

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """
            SELECT id FROM deliveries
            WHERE payment_id = ? AND bundle_product_id IS NULL
            LIMIT 1
            """,
            (invoice_id,),
        ).fetchone()
        if existing:
            return {"ok": True, "fresh": False}

        delivery_id, mark_cred, mark_expires = _allocate_delivery(
            conn,
            payment_row=payment_row,
            product_id=product_id,
            source_product_id=source_product_id,
            bundle_product_id=None,
            part_label=None,
            months=months,
        )
        if not delivery_id:
            log.warning("auto-issue: no stock for product %s payment %s", product_id, invoice_id)
            return {"ok": False, "reason": "no_stock"}

    if mark_cred and mark_expires:
        _mark_sheet_issued(mark_cred, payment_row, mark_expires, months_n)

    log.info("auto-delivered product %s for payment %s", product_id, invoice_id)
    return {"ok": True, "fresh": True, "deliveryId": delivery_id}


async def process_paid_payment(payment_row: dict) -> None:
    result = try_deliver_for_payment(payment_row, months=int(payment_row.get("months") or 1))
    if result.get("ok"):
        await link_delivery_to_bot_sub(payment_row)
