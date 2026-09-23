"""Синхронізація складу з Google Таблицями."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .db import db, now
from .settings import GOOGLE_SHEETS_ID, GOOGLE_SERVICE_ACCOUNT_INFO

log = logging.getLogger("flix.site.sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Лист1 — Netflix: жовті (доступні) → після видачі сині + термін у col D
# Лист2 — Filmix: вільні рядки без ніка/дати → після видачі нік + дата
# Лист3 — GPT: A/B логін/пароль, G 2FA ключ, D/E/F дата/id/нік → після видачі заповнюються
# Лист5 — HBO: вільні без дати/id/ніка → після видачі дата + id + нік
# Лист6 — IPTV: col A посилання, col B нік, col C дата → після видачі нік + дата

SHEET_CONFIGS: dict[str, dict[str, Any]] = {
    "netflix": {
        "sheet": "Лист1",
        "product_keywords": ("netflix",),
        "exclude_keywords": ("sweet", "hbo", "помісячно", "+"),
        "prefer_keywords": ("окремий", "premium"),
        "cols": {"login": 1, "password": 2, "expiry": 3, "profile": 4},
    },
    "filmix": {
        "sheet": "Лист2",
        "product_keywords": ("filmix",),
        "exclude_keywords": ("+",),
        "prefer_keywords": ("додаток",),
        "cols": {"login": 0, "password": 1, "nick": 2, "expiry": 3},
    },
    "gpt": {
        "sheet": "Лист3",
        "product_keywords": ("chatgpt",),
        "exclude_keywords": ("claude", "+"),
        "prefer_keywords": ("plus",),
        "cols": {"login": 0, "password": 1, "two_fa": 6, "expiry": 3, "tg_id": 4, "nick": 5},
    },
    "hbo": {
        "sheet": "Лист5",
        "product_keywords": ("hbo",),
        "exclude_keywords": ("netflix", "+"),
        "prefer_keywords": ("max", "premium"),
        "cols": {"login": 0, "password": 1, "profile": 2, "pin": 3, "expiry": 4, "tg_id": 5, "nick": 6},
    },
    "iptv": {
        "sheet": "Лист6",
        "product_keywords": ("iptv",),
        "exclude_keywords": ("+",),
        "prefer_keywords": (),
        "cols": {"url": 0, "nick": 1, "expiry": 2},
    },
}

# Google Sheets Netflix: жовтий/білий = вільний, бірюзовий/синій = виданий
_COLOR_ISSUED = (0.435, 0.659, 0.863)
_NETFLIX_ISSUED_CYAN = (0.275, 0.851, 0.953)  # «сині» рядки у таблиці Netflix

_lock = threading.Lock()
_last_sync: dict[str, Any] = {
    "at": None,
    "ok": False,
    "imported": 0,
    "deactivated": 0,
    "errors": [],
    "byService": {},
}


def sync_status() -> dict:
    return dict(_last_sync)


def _service():
    if not GOOGLE_SERVICE_ACCOUNT_INFO or not GOOGLE_SHEETS_ID:
        return None
    creds = service_account.Credentials.from_service_account_info(
        GOOGLE_SERVICE_ACCOUNT_INFO, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _cell(row: list, idx: int) -> str:
    if idx < len(row):
        return str(row[idx] or "").strip()
    return ""


def _is_blueish(r: float, g: float, b: float) -> bool:
    return b > 0.75 and g > 0.5 and r < 0.6


def _netflix_expiry_cell_color(row_data: dict | None) -> tuple[float, float, float] | None:
    """Колір лише комірки терміну (col D), не всього рядка."""
    if not row_data:
        return None
    cells = row_data.get("values", [])
    if len(cells) <= 3:
        return None
    bg = (cells[3].get("effectiveFormat") or {}).get("backgroundColor") or {}
    r = bg.get("red", 1.0)
    g = bg.get("green", 1.0)
    b = bg.get("blue", 1.0)
    if r > 0.99 and g > 0.99 and b > 0.99:
        return None
    return (r, g, b)


def _netflix_row_is_used(row: list, row_data: dict | None) -> bool:
    """Виданий: є термін у col D або комірка D забарвлена (бірюзовий/синій)."""
    if _cell(row, 3):
        return True
    color = _netflix_expiry_cell_color(row_data)
    if not color:
        return False
    r, g, b = color
    if (
        abs(r - _NETFLIX_ISSUED_CYAN[0]) < 0.06
        and abs(g - _NETFLIX_ISSUED_CYAN[1]) < 0.06
        and abs(b - _NETFLIX_ISSUED_CYAN[2]) < 0.06
    ):
        return True
    if _is_blueish(r, g, b):
        return True
    return False


def _row_bg_color(row_data: dict | None) -> tuple[float, float, float] | None:
    if not row_data:
        return None
    for cell in row_data.get("values", []):
        bg = (cell.get("effectiveFormat") or {}).get("backgroundColor") or {}
        r = bg.get("red", 1.0)
        g = bg.get("green", 1.0)
        b = bg.get("blue", 1.0)
        if r < 0.99 or g < 0.99 or b < 0.99:
            return (r, g, b)
    return None


def _format_expiry(dt: datetime) -> str:
    """Як у Telegram-боті: DD.MM.YYYY."""
    return dt.strftime("%d.%m.%Y")


def _parse_expiry(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _is_bundle_name(name: str) -> bool:
    return " + " in name or name.count("+") > 1


def resolve_product_id(
    keywords: tuple[str, ...],
    catalog_products: list[dict],
    *,
    exclude_keywords: tuple[str, ...] = (),
    prefer_keywords: tuple[str, ...] = (),
) -> int | None:
    candidates: list[tuple[int, str, int]] = []
    for product in catalog_products:
        name = (product.get("name") or "").lower()
        if not any(kw in name for kw in keywords):
            continue
        if "+" in exclude_keywords and _is_bundle_name(name):
            continue
        if exclude_keywords and any(ex in name for ex in exclude_keywords if ex != "+"):
            continue
        raw = product.get("botId") or product.get("id")
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        score = sum(2 for pk in prefer_keywords if pk in name)
        if "окремий" in name:
            score += 3
        candidates.append((score, name, pid))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _netflix_available(row: list, row_data: dict | None) -> bool:
    login = _cell(row, 1)
    password = _cell(row, 2)
    if not login or not password:
        return False
    return not _netflix_row_is_used(row, row_data)


def _filmix_available(row: list) -> bool:
    login = _cell(row, 0)
    password = _cell(row, 1)
    nick = _cell(row, 2)
    expiry = _cell(row, 3)
    return bool(login and password and not nick and not expiry)


def _gpt_two_fa_raw(row: list) -> str:
    """2FA ключ у колонці G; колонка C лишається запасним варіантом."""
    return _cell(row, 6) or _cell(row, 2)


def _parse_gpt_two_fa(raw: str) -> tuple[str | None, str | None]:
    value = (raw or "").strip()
    if not value:
        return None, None
    if value.lower().startswith("http"):
        return value, None
    return None, value.replace(" ", "").upper()


def _gpt_available(row: list) -> bool:
    login = _cell(row, 0)
    password = _cell(row, 1)
    if not login or not password:
        return False
    return not (_cell(row, 3) and _cell(row, 4) and _cell(row, 5))


def _hbo_available(row: list) -> bool:
    login = _cell(row, 0)
    password = _cell(row, 1)
    profile = _cell(row, 2)
    pin = _cell(row, 3)
    if not login or not password or not profile or not pin:
        return False
    return not (_cell(row, 4) and _cell(row, 5) and _cell(row, 6))


def _iptv_available(row: list) -> bool:
    url = _cell(row, 0)
    if not url or not re.match(r"^https?://", url, re.I):
        return False
    return not (_cell(row, 1) and _cell(row, 2))


def _extract_2fa_secret(url: str) -> str | None:
    """Спроба витягти секрет з flix2fa URL (hex → base32 для TOTP)."""
    m = re.search(r"#c=([a-fA-F0-9]+)", url or "")
    if not m:
        return None
    return None  # flix2fa — окремий сервіс, зберігаємо URL у meta


def _read_sheet(service, sheet_name: str, with_colors: bool = False) -> tuple[list[list], list[dict | None]]:
    if with_colors:
        result = service.spreadsheets().get(
            spreadsheetId=GOOGLE_SHEETS_ID,
            ranges=[f"'{sheet_name}'!A1:H2000"],
            includeGridData=True,
        ).execute()
        grid_rows = result["sheets"][0].get("data", [{}])[0].get("rowData", [])
        values = []
        row_meta = []
        for gr in grid_rows:
            cells = gr.get("values", [])
            values.append([c.get("formattedValue", "") for c in cells])
            row_meta.append(gr)
        return values, row_meta

    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!A1:H2000",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    values = result.get("values", [])
    return values, [None] * len(values)


def _collect_available(service) -> list[dict]:
    items: list[dict] = []

    netflix_values, netflix_meta = _read_sheet(service, "Лист1", with_colors=True)
    for i, row in enumerate(netflix_values):
        if not _netflix_available(row, netflix_meta[i] if i < len(netflix_meta) else None):
            continue
        items.append({
            "service": "netflix",
            "sheet": "Лист1",
            "row": i + 1,
            "login": _cell(row, 1),
            "password": _cell(row, 2),
            "profile": _cell(row, 4),
            "external_id": f"netflix:{i + 1}",
        })

    filmix_values, _ = _read_sheet(service, "Лист2")
    for i, row in enumerate(filmix_values):
        if not _filmix_available(row):
            continue
        items.append({
            "service": "filmix",
            "sheet": "Лист2",
            "row": i + 1,
            "login": _cell(row, 0),
            "password": _cell(row, 1),
            "external_id": f"filmix:{i + 1}",
        })

    gpt_values, _ = _read_sheet(service, "Лист3")
    for i, row in enumerate(gpt_values):
        if not _gpt_available(row):
            continue
        two_fa_raw = _gpt_two_fa_raw(row)
        two_fa_url, _ = _parse_gpt_two_fa(two_fa_raw)
        items.append({
            "service": "gpt",
            "sheet": "Лист3",
            "row": i + 1,
            "login": _cell(row, 0),
            "password": _cell(row, 1),
            "two_fa_raw": two_fa_raw,
            "two_fa_url": two_fa_url,
            "external_id": f"gpt:{i + 1}",
        })

    hbo_values, _ = _read_sheet(service, "Лист5")
    for i, row in enumerate(hbo_values):
        if not _hbo_available(row):
            continue
        items.append({
            "service": "hbo",
            "sheet": "Лист5",
            "row": i + 1,
            "login": _cell(row, 0),
            "password": _cell(row, 1),
            "profile": _cell(row, 2),
            "pin": _cell(row, 3),
            "external_id": f"hbo:{i + 1}",
        })

    iptv_values, _ = _read_sheet(service, "Лист6")
    for i, row in enumerate(iptv_values):
        if not _iptv_available(row):
            continue
        url = _cell(row, 0)
        items.append({
            "service": "iptv",
            "sheet": "Лист6",
            "row": i + 1,
            "login": url,
            "password": "-",
            "playlist_url": url,
            "external_id": f"iptv:{i + 1}",
        })

    return items


def _upsert_credential(
    item: dict,
    product_id: int,
    existing: dict | None,
) -> str:
    """Повертає id credential (створений або оновлений)."""
    from .crypto import encrypt
    from .db import new_id
    from .stock_svc import _encode_profile_slots

    two_fa_url = item.get("two_fa_url")
    totp_enc = None
    if item["service"] == "gpt":
        parsed_url, totp_secret = _parse_gpt_two_fa(item.get("two_fa_raw") or "")
        two_fa_url = parsed_url
        if totp_secret:
            totp_enc = encrypt(totp_secret)

    meta = {
        "service": item["service"],
        "sheet": item["sheet"],
        "row": item["row"],
        "profile": item.get("profile"),
        "two_fa_url": two_fa_url,
        "playlist_url": item.get("playlist_url"),
    }
    meta_json = json.dumps(meta, ensure_ascii=False)
    note = f"sheets:{item['external_id']}"

    profile_slots = None
    if item["service"] == "hbo":
        profile_slots = [{"num": item["profile"], "pin": item["pin"]}]

    profile_name_note = ""
    if item["service"] == "netflix" and item.get("profile"):
        profile_name_note = f"Профіль {item['profile']}"

    with db() as conn:
        if existing:
            cred_id = existing["id"]
            slots_used = int(existing.get("slots_used") or 0)
            conn.execute(
                """
                UPDATE credentials SET
                    product_id = ?, login = ?, secret_enc = ?, note = ?, sheet_meta = ?,
                    active = 1, slots_total = ?, totp_enc = ?
                WHERE id = ?
                """,
                (
                    int(product_id),
                    item["login"],
                    encrypt(item["password"]),
                    note,
                    meta_json,
                    max(1, slots_used),
                    totp_enc,
                    cred_id,
                ),
            )
            if profile_slots:
                conn.execute(
                    "UPDATE credentials SET profile_slots_enc = ? WHERE id = ?",
                    (_encode_profile_slots(profile_slots), cred_id),
                )
            return cred_id

        cred_id = new_id()
        profile_enc = _encode_profile_slots(profile_slots) if profile_slots else None

        conn.execute(
            """
            INSERT INTO credentials (
                id, product_id, login, secret_enc, totp_enc,
                slots_total, slots_used, note, active, created_at,
                profile_slots_enc, external_source, external_id, sheet_meta
            ) VALUES (?, ?, ?, ?, ?, 1, 0, ?, 1, ?, ?, 'sheets', ?, ?)
            """,
            (
                cred_id,
                int(product_id),
                item["login"],
                encrypt(item["password"]),
                totp_enc,
                note,
                now(),
                profile_enc,
                item["external_id"],
                meta_json,
            ),
        )
        return cred_id


def import_stock(catalog_products: list[dict]) -> dict:
    """Імпорт доступних акаунтів з Google Таблиць у склад сайту."""
    from .stock_svc import refresh_netflix_stock_aliases, stock_source_product_id

    refresh_netflix_stock_aliases(catalog_products)
    global _last_sync
    result = {"ok": False, "imported": 0, "deactivated": 0, "errors": [], "byService": {}}

    service = _service()
    if not service:
        result["errors"].append("Google Sheets не налаштовано (GOOGLE_SHEETS_ID / GOOGLE_SERVICE_ACCOUNT_JSON)")
        with _lock:
            _last_sync = {**result, "at": now()}
        return result

    try:
        with _lock:
            available = _collect_available(service)
    except Exception as e:
        log.exception("sheets import read failed")
        result["errors"].append(str(e))
        with _lock:
            _last_sync = {**result, "at": now()}
        return result

    product_map: dict[str, int | None] = {}
    for key, cfg in SHEET_CONFIGS.items():
        product_map[key] = resolve_product_id(
            cfg["product_keywords"],
            catalog_products,
            exclude_keywords=tuple(cfg.get("exclude_keywords") or ()),
            prefer_keywords=tuple(cfg.get("prefer_keywords") or ()),
        )

    with db() as conn:
        existing_rows = conn.execute(
            "SELECT * FROM credentials WHERE external_source = 'sheets'"
        ).fetchall()
    existing_by_ext = {r["external_id"]: dict(r) for r in existing_rows}

    seen_ext: set[str] = set()
    imported = 0
    by_service: dict[str, int] = {}

    for item in available:
        service_key = item["service"]
        product_id = product_map.get(service_key)
        if not product_id:
            result["errors"].append(f"Товар для {service_key} не знайдено в каталозі")
            continue
        product_id = stock_source_product_id(product_id, catalog_products)

        ext_id = item["external_id"]
        seen_ext.add(ext_id)
        prev = existing_by_ext.get(ext_id)

        if prev and int(prev.get("slots_used") or 0) > 0:
            with db() as conn:
                active_delivery = conn.execute(
                    """
                    SELECT 1 FROM deliveries
                    WHERE credential_id = ?
                      AND (expires_at IS NULL OR expires_at > ?)
                    LIMIT 1
                    """,
                    (prev["id"], now()),
                ).fetchone()
            if active_delivery:
                continue
            with db() as conn:
                conn.execute(
                    "UPDATE credentials SET slots_used = 0, active = 1 WHERE id = ?",
                    (prev["id"],),
                )
            prev = dict(prev)
            prev["slots_used"] = 0
            prev["active"] = 1

        try:
            _upsert_credential(item, product_id, prev)
            imported += 1
            by_service[service_key] = by_service.get(service_key, 0) + 1
        except Exception as e:
            log.warning("upsert %s: %s", ext_id, e)
            result["errors"].append(f"{ext_id}: {e}")

    reactivated = 0
    deactivated = 0
    with db() as conn:
        for ext_id, row in existing_by_ext.items():
            if ext_id in seen_ext:
                slots_used = int(row.get("slots_used") or 0)
                active_delivery = conn.execute(
                    """
                    SELECT 1 FROM deliveries
                    WHERE credential_id = ?
                      AND (expires_at IS NULL OR expires_at > ?)
                    LIMIT 1
                    """,
                    (row["id"], now()),
                ).fetchone()
                if not active_delivery and slots_used > 0:
                    conn.execute(
                        "UPDATE credentials SET slots_used = 0, active = 1 WHERE id = ?",
                        (row["id"],),
                    )
                    reactivated += 1
                elif not int(row.get("active") or 0) and slots_used == 0:
                    conn.execute(
                        "UPDATE credentials SET active = 1 WHERE id = ?",
                        (row["id"],),
                    )
                    reactivated += 1
                continue
            if int(row.get("slots_used") or 0) > 0:
                continue
            conn.execute(
                "UPDATE credentials SET active = 0 WHERE id = ?",
                (row["id"],),
            )
            deactivated += 1

    result.update({
        "ok": True,
        "imported": imported,
        "deactivated": deactivated,
        "byService": by_service,
        "available": len(available),
    })
    with _lock:
        _last_sync = {**result, "at": now()}
    log.info(
        "sheets sync: imported=%s deactivated=%s available=%s",
        imported, deactivated, len(available),
    )
    return result


def _fetch_sheet_row(
    service,
    sheet_name: str,
    row_num: int,
    *,
    with_colors: bool = False,
) -> tuple[list, dict | None]:
    if row_num < 1:
        return [], None
    row_range = f"'{sheet_name}'!A{row_num}:H{row_num}"
    if with_colors:
        result = service.spreadsheets().get(
            spreadsheetId=GOOGLE_SHEETS_ID,
            ranges=[row_range],
            includeGridData=True,
        ).execute()
        grid_rows = result["sheets"][0].get("data", [{}])[0].get("rowData", [])
        if not grid_rows:
            return [], None
        row_meta = grid_rows[0]
        cells = row_meta.get("values", [])
        return [c.get("formattedValue", "") for c in cells], row_meta
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=row_range,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    values = (result.get("values") or [[]])[0]
    return values, None


def _service_row_available(service_key: str, row: list, row_meta: dict | None) -> bool:
    if service_key == "netflix":
        return _netflix_available(row, row_meta)
    if service_key == "filmix":
        return _filmix_available(row)
    if service_key == "gpt":
        return _gpt_available(row)
    if service_key == "hbo":
        return _hbo_available(row)
    if service_key == "iptv":
        return _iptv_available(row)
    return True


def verify_sheet_credential(cred: dict) -> bool:
    """Перевірити в Google Таблиці, що рядок досі вільний (перед видачею після оплати)."""
    if cred.get("external_source") != "sheets":
        return True
    raw_meta = cred.get("sheet_meta")
    if not raw_meta:
        return True
    try:
        meta = json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
    except (TypeError, json.JSONDecodeError):
        return True
    if not isinstance(meta, dict):
        return True

    service_key = meta.get("service")
    sheet_name = meta.get("sheet")
    row_num = int(meta.get("row") or 0)
    if not service_key or not sheet_name or row_num < 1:
        return True

    service = _service()
    if not service:
        log.warning("verify sheet: Google API unavailable, skip live check for %s", cred.get("id"))
        return True

    try:
        row, row_meta = _fetch_sheet_row(
            service,
            sheet_name,
            row_num,
            with_colors=service_key == "netflix",
        )
        if not row:
            log.warning("verify sheet: row missing %s:%s", sheet_name, row_num)
            return False
        available = _service_row_available(service_key, row, row_meta)
        if not available:
            log.info("verify sheet: row %s:%s already used", sheet_name, row_num)
        return available
    except Exception as e:
        log.warning("verify sheet %s:%s failed: %s", sheet_name, row_num, e)
        return True


def _user_nick(payment_row: dict) -> str:
    username = (payment_row.get("username") or "").strip()
    if username:
        return username if username.startswith("@") else f"@{username}"
    tg_id = payment_row.get("telegram_id")
    if tg_id:
        return f"@{tg_id}"
    return ""


def _user_tg_id(payment_row: dict) -> str:
    tg_id = payment_row.get("telegram_id")
    return str(tg_id) if tg_id else ""


def mark_row_issued(
    sheet_meta: dict,
    payment_row: dict,
    expires_at: str | None,
    months: int = 1,
) -> bool:
    """Позначити рядок у таблиці як виданий після автовидачі."""
    service = _service()
    if not service or not sheet_meta:
        return False

    service_key = sheet_meta.get("service")
    sheet_name = sheet_meta.get("sheet")
    row_num = int(sheet_meta.get("row") or 0)
    if not service_key or not sheet_name or row_num < 1:
        return False

    exp_dt = _parse_expiry(expires_at or "")
    if not exp_dt:
        exp_dt = datetime.now(timezone.utc) + timedelta(days=30 * max(1, months))
    expiry_str = _format_expiry(exp_dt)
    nick = _user_nick(payment_row)
    tg_id = _user_tg_id(payment_row)

    try:
        if service_key == "netflix":
            _mark_netflix(service, sheet_name, row_num, expiry_str)
        elif service_key == "filmix":
            _mark_filmix(service, sheet_name, row_num, nick, expiry_str)
        elif service_key == "gpt":
            _mark_gpt(service, sheet_name, row_num, expiry_str, tg_id, nick)
        elif service_key == "hbo":
            _mark_hbo(service, sheet_name, row_num, expiry_str, tg_id, nick)
        elif service_key == "iptv":
            _mark_iptv(service, sheet_name, row_num, nick, expiry_str)
        else:
            return False
        log.info("marked sheet row %s:%s as issued", sheet_name, row_num)
        return True
    except Exception as e:
        log.exception("mark_row_issued %s:%s: %s", sheet_name, row_num, e)
        return False


def _color_request(sheet_id: int, row: int, col_start: int, col_end: int, rgb: tuple[float, float, float]) -> dict:
    r, g, b = rgb
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row - 1,
                "endRowIndex": row,
                "startColumnIndex": col_start,
                "endColumnIndex": col_end,
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": {"red": r, "green": g, "blue": b},
                }
            },
            "fields": "userEnteredFormat.backgroundColor",
        }
    }


def _get_sheet_id(service, sheet_name: str) -> int | None:
    meta = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == sheet_name:
            return sheet["properties"]["sheetId"]
    return None


def _mark_netflix(service, sheet_name: str, row: int, expiry: str) -> None:
    sheet_id = _get_sheet_id(service, sheet_name)
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!D{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[expiry]]},
    ).execute()
    if sheet_id is not None:
        service.spreadsheets().batchUpdate(
            spreadsheetId=GOOGLE_SHEETS_ID,
            body={"requests": [_color_request(sheet_id, row, 0, 5, _NETFLIX_ISSUED_CYAN)]},
        ).execute()


def _mark_filmix(service, sheet_name: str, row: int, nick: str, expiry: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!C{row}:D{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[nick, expiry]]},
    ).execute()


def _mark_gpt(service, sheet_name: str, row: int, expiry: str, tg_id: str, nick: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!D{row}:F{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[expiry, tg_id, nick]]},
    ).execute()


def _mark_hbo(service, sheet_name: str, row: int, expiry: str, tg_id: str, nick: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!E{row}:G{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[expiry, tg_id, nick]]},
    ).execute()


def _mark_iptv(service, sheet_name: str, row: int, nick: str, expiry: str) -> None:
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"'{sheet_name}'!B{row}:C{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[nick, expiry]]},
    ).execute()


async def sync_loop(interval_s: float = 60.0) -> None:
    """Фонове оновлення складу з Google Таблиць кожні 60 секунд."""
    from . import catalog_svc

    await asyncio.sleep(5)
    while True:
        try:
            catalog_data = await catalog_svc.get_catalog()
            products = catalog_data.get("products") or []
            import_stock(products)
        except Exception:
            log.exception("sheets sync loop")
        await asyncio.sleep(interval_s)
