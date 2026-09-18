"""Завантажує аватар з Telegram і віддає його з сайту (без токена бота в URL)."""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from .settings import DB_PATH, TELEGRAM_BOT_TOKEN
from .telegram_auth import normalize_bot_token

log = logging.getLogger("flix.site")
AVATAR_DIR = Path(DB_PATH).parent / "avatars"
EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def avatar_path(telegram_id: int) -> Path | None:
    if not telegram_id:
        return None
    for ext in EXT:
        candidate = AVATAR_DIR / f"{int(telegram_id)}{ext}"
        if candidate.is_file():
            return candidate
    return None


def avatar_url(telegram_id: int) -> str | None:
    path = avatar_path(telegram_id)
    return f"/api/media/avatar/{int(telegram_id)}" if path else None


async def save_telegram_avatar(telegram_id: int) -> str | None:
    token = (TELEGRAM_BOT_TOKEN or "").strip().strip('"')
    if not token or not telegram_id:
        return avatar_url(telegram_id)
    api = f"https://api.telegram.org/bot{token}"
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            photos = await client.get(f"{api}/getUserProfilePhotos", params={"user_id": int(telegram_id), "limit": 1})
            data = photos.json()
            sizes = (((data.get("result") or {}).get("photos") or [None])[0]) or []
            if not data.get("ok") or not sizes:
                return avatar_url(telegram_id)
            file_id = sizes[-1].get("file_id")
            if not file_id:
                return avatar_url(telegram_id)
            meta = await client.get(f"{api}/getFile", params={"file_id": file_id})
            file_path = ((meta.json().get("result") or {}).get("file_path") or "").lstrip("/")
            if not file_path:
                return avatar_url(telegram_id)
            raw = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
            if raw.status_code != 200 or not raw.content:
                return avatar_url(telegram_id)
    except Exception as e:
        log.warning("telegram avatar: %s", e)
        return avatar_url(telegram_id)

    suffix = Path(file_path).suffix.lower()
    if suffix not in EXT:
        suffix = ".jpg"
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    dest = AVATAR_DIR / f"{int(telegram_id)}{suffix}"
    dest.write_bytes(raw.content)
    for extra in EXT:
        other = AVATAR_DIR / f"{int(telegram_id)}{extra}"
        if other != dest and other.exists():
            other.unlink()
    return f"/api/media/avatar/{int(telegram_id)}"
