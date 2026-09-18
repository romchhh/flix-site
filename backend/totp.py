"""RFC 6238 TOTP: SHA-1, 6 цифр, вікно 30 секунд."""
from __future__ import annotations

import hashlib
import hmac
import struct
import time


def _base32_decode(secret: str) -> bytes:
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    clean = "".join(ch for ch in (secret or "").upper() if ch in abc)
    bits = 0
    value = 0
    out = bytearray()
    for ch in clean:
        idx = abc.index(ch)
        value = (value << 5) | idx
        bits += 5
        if bits >= 8:
            out.append((value >> (bits - 8)) & 0xFF)
            bits -= 8
    return bytes(out)


def generate(secret_base32: str, at: float | None = None) -> dict[str, int | str]:
    now = at if at is not None else time.time()
    step = 30
    counter = int(now // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(_base32_decode(secret_base32), msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return {
        "code": str(code_int % 1_000_000).zfill(6),
        "secondsLeft": step - int(now) % step,
    }
