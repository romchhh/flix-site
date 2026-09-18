import os
from pathlib import Path

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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
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
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
