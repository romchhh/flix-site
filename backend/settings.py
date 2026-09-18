import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

APP_URL = os.getenv("APP_URL", "http://localhost:3000").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-session-secret-change-me")
BOT_API_URL = os.getenv("BOT_API_URL", "http://127.0.0.1:8088").rstrip("/")
BOT_API_KEY = os.getenv("BOT_API_KEY", "")
MINIAPP_API_URL = os.getenv("MINIAPP_API_URL", "https://market.easyplayy.com").rstrip("/")
MINIAPP_API_KEY = os.getenv("MINIAPP_API_KEY", "") or BOT_API_KEY
def _norm_token(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _read_env_token(*keys: str) -> str:
    """Останнє непусте значення з .env (дублікат TELEGRAM_BOT_TOKEN=\"\" в кінці файлу ламає dotenv)."""
    keyset = set(keys)
    last_nonempty: dict[str, str] = {}
    for env_path in (ROOT / ".env", Path(__file__).resolve().parent / ".env"):
        if not env_path.is_file():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, _, v = s.partition("=")
            k = k.strip()
            if k not in keyset:
                continue
            val = _norm_token(v)
            if val:
                last_nonempty[k] = val
    for key in keys:
        val = _norm_token(os.getenv(key, ""))
        if val:
            return val
    for key in keys:
        if key in last_nonempty:
            return last_nonempty[key]
    return ""


TELEGRAM_BOT_TOKEN = _read_env_token("TELEGRAM_BOT_TOKEN", "BOT_TOKEN")
TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME", "FlixMarketBot")
ADMIN_EMAILS = [s.strip().lower() for s in os.getenv("ADMIN_EMAILS", "").split(",") if s.strip()]
ADMIN_TELEGRAM_IDS = [s.strip() for s in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if s.strip()]
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MAIL_FROM = os.getenv("MAIL_FROM", "flixмаркет <hello@flixmarket.com>")
DB_PATH = os.getenv("SITE_DATABASE_PATH") or str(Path(__file__).resolve().parent / "data" / "site.db")
MONO_XTOKEN = (os.getenv("MONO_XTOKEN") or "").strip()
COOKIE_NAME = "flix_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1" if APP_URL.startswith("https://") else "0") == "1"
COOKIE_DOMAIN = (os.getenv("COOKIE_DOMAIN") or "").strip() or None


def _norm_origin(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _default_site_origins() -> list[str]:
    origins = [
        APP_URL,
        MINIAPP_API_URL,
        "https://flix-market.com",
        "https://www.flix-market.com",
        "https://market.easyplayy.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    host = (urlparse(APP_URL).hostname or "").lower()
    scheme = urlparse(APP_URL).scheme or "https"
    if host and not host.startswith("www."):
        origins.append(f"{scheme}://www.{host}")
    if host.startswith("www.") and len(host) > 4:
        origins.append(f"{scheme}://{host[4:]}")
    return origins


_extra = [s for s in os.getenv("SITE_ORIGINS", "").split(",") if s.strip()]
SITE_ORIGINS: list[str] = []
_seen: set[str] = set()
for item in [*_default_site_origins(), *_extra]:
    origin = _norm_origin(item)
    if origin and origin not in _seen:
        _seen.add(origin)
        SITE_ORIGINS.append(origin)


# Префікси deep-link для відомих прод-доменів (бот знає origin без WEB_SITE_URL).
SITE_ORIGIN_PREFIXES = {
    "flix-market.com": "f0",
    "www.flix-market.com": "f1",
    "market.easyplayy.com": "e0",
}


def is_allowed_origin(origin: str) -> bool:
    return _norm_origin(origin) in SITE_ORIGINS


def resolve_request_origin(origin_header: str = "", referer: str = "", host_header: str = "") -> str:
    for candidate in (origin_header, referer):
        origin = _norm_origin(candidate)
        if origin and is_allowed_origin(origin):
            return origin
    host = (host_header or "").split(",")[0].strip().split(":")[0].lower()
    if host:
        for scheme in ("https", "http"):
            origin = _norm_origin(f"{scheme}://{host}")
            if origin and is_allowed_origin(origin):
                return origin
    return APP_URL
