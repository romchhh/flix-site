"""Перевірка підпису Telegram Login (віджет і deep-link з бота)."""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from .settings import TELEGRAM_BOT_TOKEN

log = logging.getLogger(__name__)

TG_HASH_FIELDS = (
    "id",
    "auth_date",
    "login_token",
    "username",
    "first_name",
    "last_name",
    "photo_url",
)


def normalize_bot_token(raw: str | None) -> str:
    return (raw or "").strip().strip('"').strip("'")


def telegram_token_candidates() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for candidate in (
        TELEGRAM_BOT_TOKEN,
        normalize_bot_token(TELEGRAM_BOT_TOKEN),
    ):
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _hash_fields(data: dict) -> dict[str, str]:
    return {
        k: str(v)
        for k, v in data.items()
        if k in TG_HASH_FIELDS and v is not None and str(v) != ""
    }


def compute_telegram_hash(data: dict, token: str) -> str:
    rest = _hash_fields(data)
    dcs = "\n".join(f"{k}={rest[k]}" for k in sorted(rest))
    secret = hashlib.sha256(normalize_bot_token(token).encode()).digest()
    return hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()


def verify_telegram_widget(data: dict) -> dict | None:
    given = str(data.get("hash") or "").strip().lower()
    if not given:
        return None
    rest = _hash_fields(data)
    if not rest.get("id") or not rest.get("auth_date"):
        return None

    matched = False
    for token in telegram_token_candidates():
        if not token:
            continue
        sign = compute_telegram_hash({**rest, "hash": given}, token).lower()
        if hmac.compare_digest(sign, given):
            matched = True
            break

    if not matched:
        token = telegram_token_candidates()[0] if telegram_token_candidates() else ""
        expected = compute_telegram_hash({**rest, "hash": given}, token).lower() if token else ""
        log.warning(
            "telegram hash mismatch fields=%s expected=%s given=%s token_id=%s",
            ",".join(sorted(rest)),
            expected[:12] + "...",
            given[:12] + "...",
            normalize_bot_token(token).split(":", 1)[0] if token else "?",
        )
        return None

    try:
        if abs(time.time() - float(rest.get("auth_date") or 0)) > 86400:
            log.warning("telegram auth_date expired for id=%s", rest.get("id"))
            return None
    except ValueError:
        return None

    return {
        "id": int(rest["id"]),
        "username": rest.get("username"),
        "first_name": rest.get("first_name"),
        "photo_url": rest.get("photo_url"),
    }
