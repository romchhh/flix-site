from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .settings import DB_PATH


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE,
                email_verified TEXT,
                password_hash TEXT,
                telegram_id INTEGER UNIQUE,
                telegram_name TEXT,
                bot_user_id INTEGER,
                is_admin INTEGER DEFAULT 0,
                last_login_ip TEXT,
                last_login_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                value TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_tg ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_tokens_value ON tokens(value);
            CREATE TABLE IF NOT EXISTS telegram_logins (
                token TEXT PRIMARY KEY,
                origin TEXT,
                telegram_id INTEGER,
                username TEXT,
                confirmed_at TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bot_sub_cache (
                telegram_id INTEGER PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkouts (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                telegram_id INTEGER,
                product_id INTEGER NOT NULL,
                months INTEGER NOT NULL,
                page_url TEXT,
                invoice_id TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS site_payments (
                payment_id TEXT PRIMARY KEY,
                invoice_id TEXT UNIQUE NOT NULL,
                site_user_id TEXT NOT NULL,
                bot_user_id INTEGER NOT NULL,
                telegram_id INTEGER,
                product_id INTEGER NOT NULL,
                months INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_type TEXT NOT NULL,
                wallet_id TEXT,
                username TEXT,
                status TEXT DEFAULT 'pending',
                mono_status TEXT,
                synced_to_bot INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_site_payments_invoice ON site_payments(invoice_id);
            CREATE INDEX IF NOT EXISTS idx_site_payments_sync ON site_payments(synced_to_bot);
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "telegram_photo" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN telegram_photo TEXT")
        from .stock_svc import init_stock_tables

        init_stock_tables(conn)


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def later(hours: float = 24) -> str:
    return (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_telegram_login(token: str, origin: str = "") -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO telegram_logins (token, origin, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET origin = excluded.origin, expires_at = excluded.expires_at
            """,
            (token, (origin or "").rstrip("/"), later(hours=10 / 60), now()),
        )


def get_telegram_login(token: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM telegram_logins WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def confirm_telegram_login(token: str, telegram_id: int, username: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM telegram_logins WHERE token = ?", (token,)).fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO telegram_logins (token, telegram_id, username, confirmed_at, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (token, telegram_id, username, now(), later(hours=10 / 60), now()),
            )
        else:
            conn.execute(
                """
                UPDATE telegram_logins
                SET telegram_id = ?, username = ?, confirmed_at = ?
                WHERE token = ?
                """,
                (telegram_id, username, now(), token),
            )
        row = conn.execute("SELECT * FROM telegram_logins WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def save_bot_sub_cache(telegram_id: int, payload: dict) -> None:
    if not telegram_id or not isinstance(payload, dict):
        return
    with db() as conn:
        conn.execute(
            """
            INSERT INTO bot_sub_cache (telegram_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
            """,
            (int(telegram_id), json.dumps(payload, ensure_ascii=False), now()),
        )


def get_bot_sub_cache(telegram_id: int) -> dict | None:
    if not telegram_id:
        return None
    with db() as conn:
        row = conn.execute(
            "SELECT payload FROM bot_sub_cache WHERE telegram_id = ?",
            (int(telegram_id),),
        ).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row["payload"])
    except (TypeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_checkout(token: str, user_id: str, telegram_id: int | None, product_id: int, months: int) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO checkouts (token, user_id, telegram_id, product_id, months, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (token, user_id, telegram_id, product_id, months, later(hours=15 / 60), now()),
        )


def get_checkout(token: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM checkouts WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def finish_checkout(token: str, page_url: str, invoice_id: str) -> dict | None:
    with db() as conn:
        conn.execute(
            """
            UPDATE checkouts SET page_url = ?, invoice_id = ? WHERE token = ?
            """,
            (page_url, invoice_id, token),
        )
        row = conn.execute("SELECT * FROM checkouts WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def user_public(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    return {
        "id": d["id"],
        "email": d.get("email"),
        "emailVerified": d.get("email_verified"),
        "telegramId": d.get("telegram_id"),
        "telegramName": d.get("telegram_name"),
        "telegramPhoto": d.get("telegram_photo"),
        "botUserId": d.get("bot_user_id"),
        "isAdmin": bool(d.get("is_admin")),
        "createdAt": d.get("created_at"),
    }
