"""AES-256-GCM для паролів і TOTP-секретів на складі."""
from __future__ import annotations

import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .settings import CREDENTIALS_KEY


def _key() -> bytes:
    raw = (CREDENTIALS_KEY or "").strip()
    if not raw:
        raise ValueError("CREDENTIALS_KEY не заданий у .env")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise ValueError("CREDENTIALS_KEY має бути 32 байти в base64")
    return key


def encrypt(plain: str) -> str:
    iv = os.urandom(12)
    aes = AESGCM(_key())
    data = aes.encrypt(iv, (plain or "").encode("utf-8"), None)
    tag, body = data[-16:], data[:-16]
    return ".".join(
        base64.b64encode(part).decode("ascii")
        for part in (iv, tag, body)
    )


def decrypt(packed: str) -> str:
    parts = (packed or "").split(".")
    if len(parts) != 3:
        raise ValueError("Некоректний зашифрований формат")
    iv, tag, body = (base64.b64decode(p) for p in parts)
    aes = AESGCM(_key())
    return aes.decrypt(iv, body + tag, None).decode("utf-8")


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
