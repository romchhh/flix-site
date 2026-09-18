"""Точка входу сайту: сесії, пошта, проксі до API бота."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime
from urllib.parse import quote, urlparse

import bcrypt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import bot_client, catalog_svc, mail, monopay, payments_svc, stock_svc, tg_photo
from .bot_client import BotAPIError
from .db import (
    confirm_telegram_login,
    create_guest_user,
    db,
    get_bot_sub_cache,
    get_telegram_login,
    init_db,
    is_guest_user,
    later,
    new_id,
    now,
    save_bot_sub_cache,
    save_telegram_login,
    user_public,
)
from .settings import (
    ADMIN_EMAILS,
    ADMIN_TELEGRAM_IDS,
    APP_URL,
    BOT_API_URL,
    bot_api_is_local,
    COOKIE_DOMAIN,
    COOKIE_NAME,
    COOKIE_SECURE,
    MINIAPP_API_URL,
    SESSION_SECRET,
    SITE_ORIGIN_PREFIXES,
    SITE_ORIGINS,
    TELEGRAM_BOT_NAME,
    TELEGRAM_BOT_TOKEN,
    resolve_request_origin,
)
from .telegram_auth import normalize_bot_token, verify_telegram_widget

log = logging.getLogger("flix.site")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="flixmarket site")
app.add_middleware(
    CORSMiddleware,
    allow_origins=SITE_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_hits: dict[str, tuple[int, float]] = {}


@app.on_event("startup")
async def _startup():
    init_db()
    _warn_if_telegram_token_mismatch()
    await _warn_if_bot_api_unreachable()
    asyncio.create_task(payments_svc.sync_loop())


async def _warn_if_bot_api_unreachable():
    if await _bot_api_ping():
        log.info("Bot API OK → %s", BOT_API_URL)
        return
    if bot_api_is_local():
        log.error(
            "Bot API недоступне на %s. Сайт і бот на різних серверах — "
            "в .env вкажи BOT_API_URL=https://ПУБЛІЧНИЙ_ДОМЕН_БОТА (напр. https://market.easyplayy.com)",
            BOT_API_URL,
        )
    else:
        log.error("Bot API недоступне: %s — перевір nginx/ufw і що бот запущений", BOT_API_URL)


async def _bot_api_ping() -> bool:
    try:
        await bot_client.bot_request("GET", "/api/v1/health")
        return True
    except Exception:
        return False


def _warn_if_telegram_token_mismatch():
    token = normalize_bot_token(TELEGRAM_BOT_TOKEN)
    if not token:
        log.error("TELEGRAM_BOT_TOKEN порожній — вхід через Telegram не запрацює")
        return
    try:
        import httpx
        res = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8.0)
        data = res.json()
        username = ((data.get("result") or {}).get("username") or "").lstrip("@")
        expected = (TELEGRAM_BOT_NAME or "").lstrip("@")
        if not data.get("ok"):
            log.error("TELEGRAM_BOT_TOKEN невалідний: %s", data)
            return
        if expected and username.lower() != expected.lower():
            log.error(
                "TELEGRAM_BOT_TOKEN належить @%s, а бот продажу — @%s. "
                "Скопіюй BOT_TOKEN з сервера бота в TELEGRAM_BOT_TOKEN сайту.",
                username,
                expected,
            )
        else:
            log.info("Telegram login token OK (@%s)", username)
    except Exception as e:
        log.warning("не вдалось перевірити TELEGRAM_BOT_TOKEN: %s", e)


def throttle(key: str, limit: int, window_s: int) -> bool:
    t = time.time()
    n, until = _hits.get(key, (0, 0.0))
    if until < t:
        _hits[key] = (1, t + window_s)
        return True
    n += 1
    _hits[key] = (n, until)
    return n <= limit


def password_problem(p: str) -> str | None:
    if len(p) < 8:
        return "Пароль має бути щонайменше 8 символів"
    if not re.search(r"[a-zA-Zа-яА-Я]", p) or not re.search(r"[0-9]", p):
        return "Додай хоча б одну літеру і одну цифру"
    return None


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=12)).decode()


def check_password(p: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except ValueError:
        return False


def sign_session(user_id: str) -> str:
    payload = f"{user_id}.{int(time.time()) + 60 * 60 * 24 * 30}"
    sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def read_session(token: str | None) -> str | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    user_id, exp, sig = parts
    payload = f"{user_id}.{exp}"
    expect = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        if int(exp) < time.time():
            return None
    except ValueError:
        return None
    return user_id


def set_cookie(resp: Response, user_id: str):
    kwargs = dict(
        key=COOKIE_NAME,
        value=sign_session(user_id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
    )
    if COOKIE_DOMAIN:
        kwargs["domain"] = COOKIE_DOMAIN
    resp.set_cookie(**kwargs)
    return resp


def clear_cookie(resp: JSONResponse):
    if COOKIE_DOMAIN:
        resp.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_DOMAIN)
    else:
        resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


def client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or request.client.host or "local").split(",")[0].strip()


def current_user_id(request: Request) -> str | None:
    return read_session(request.cookies.get(COOKIE_NAME))


def get_user(user_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


async def hydrate_telegram_photo(row) -> dict:
    d = dict(row)
    tg_id = d.get("telegram_id")
    if not tg_id:
        return d
    local = tg_photo.avatar_url(int(tg_id))
    if local:
        if d.get("telegram_photo") != local:
            with db() as conn:
                conn.execute("UPDATE users SET telegram_photo = ? WHERE id = ?", (local, d["id"]))
            d["telegram_photo"] = local
        return d
    photo = await tg_photo.save_telegram_avatar(int(tg_id))
    if photo:
        with db() as conn:
            conn.execute("UPDATE users SET telegram_photo = ? WHERE id = ?", (photo, d["id"]))
        d["telegram_photo"] = photo
    return d


def json_error(message: str, status: int = 400):
    return JSONResponse({"error": message}, status_code=status)


NGROK_SUFFIXES = (
    (".ngrok-free.dev", "n0"),
    (".ngrok-free.app", "n1"),
    (".ngrok.io", "n2"),
    (".ngrok.app", "n3"),
)


def telegram_start_payload(token: str, origin: str) -> str:
    host = (urlparse(origin).hostname or "").lower()
    if host == "localhost":
        return f"w1{token}"
    if host in ("127.0.0.1", "::1"):
        return f"w2{token}"
    for suffix, prefix in NGROK_SUFFIXES:
        if host.endswith(suffix):
            return f"{prefix}{token}{host[: -len(suffix)]}"
    prefix = SITE_ORIGIN_PREFIXES.get(host)
    if prefix:
        return f"{prefix}{token}"
    return f"w0{token}"


async def consume_telegram_login(request: Request, token: str, redirect_to: str | None = None):
    row = get_telegram_login(token)
    if not row:
        return None
    if row.get("expires_at") and row["expires_at"] < now() and not row.get("confirmed_at"):
        return json_error("Посилання протухло. Натисни кнопку ще раз.", 410)
    if not row.get("confirmed_at") or not row.get("telegram_id"):
        return {"status": "pending"}
    username = (row.get("username") or str(row["telegram_id"])).lstrip("@")
    return await complete_telegram_session(
        request, int(row["telegram_id"]), username, redirect_to=redirect_to,
    )


async def ensure_bot_user(conn, user_row) -> int | None:
    bot_user_id = user_row["bot_user_id"]
    if bot_user_id:
        return int(bot_user_id)
    created = await bot_client.ensure_user(
        email=user_row["email"],
        telegram_id=user_row["telegram_id"],
        username=user_row["telegram_name"] or user_row["email"],
    )
    uid = created.get("userId")
    if uid is None:
        return None
    conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (uid, user_row["id"]))
    return int(uid)


async def resolve_bot_user_id(user_row, site_user_id: str) -> int | None:
    """Повертає bot user id і зберігає його в site SQLite."""
    if not user_row:
        return None
    if not isinstance(user_row, dict):
        user_row = dict(user_row)
    if user_row.get("bot_user_id"):
        return int(user_row["bot_user_id"])
    if user_row.get("telegram_id"):
        try:
            created = await bot_client.ensure_user(
                telegram_id=int(user_row["telegram_id"]),
                username=user_row.get("telegram_name"),
            )
            bot_id = int(created.get("userId") or user_row["telegram_id"])
            with db() as conn:
                conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (bot_id, site_user_id))
            return bot_id
        except BotAPIError as e:
            log.warning("resolve_bot_user_id telegram: %s", e)
            return int(user_row["telegram_id"])
    if user_row.get("email"):
        try:
            created = await bot_client.ensure_user(
                email=user_row["email"],
                username=user_row.get("telegram_name") or user_row["email"],
            )
            bot_id = created.get("userId")
            if bot_id is not None:
                with db() as conn:
                    conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (int(bot_id), site_user_id))
                return int(bot_id)
        except BotAPIError as e:
            log.warning("resolve_bot_user_id email: %s", e)
    return None


async def ensure_checkout_identity(request: Request) -> tuple[dict, str, bool]:
    """Повертає (user, site_user_id, created_guest). Без Telegram — гість або email-акаунт."""
    uid = current_user_id(request)
    if uid:
        me = get_user(uid)
        if me:
            return me, uid, False
    guest = create_guest_user()
    return guest, guest["id"], True


async def _telegram_from_bot_login(params: dict) -> tuple[dict, str] | None:
    """Якщо підпис не зійшовся, але бот уже підтвердив login_token — довіряємо API бота."""
    login_token = str(params.get("login_token") or "").strip()
    tg_id_raw = str(params.get("id") or "").strip()
    if not login_token or not tg_id_raw.isdigit():
        return None
    try:
        data = await bot_client.web_login_status(login_token)
    except BotAPIError as e:
        log.info("telegram login fallback via bot API skipped: %s", e)
        return None
    if data.get("status") != "confirmed":
        return None
    confirmed_id = int(data.get("telegramId") or 0)
    if confirmed_id != int(tg_id_raw):
        log.warning(
            "telegram login token %s confirmed for %s, callback id=%s",
            login_token, confirmed_id, tg_id_raw,
        )
        return None
    username = (data.get("username") or str(confirmed_id)).lstrip("@")
    confirm_telegram_login(login_token, confirmed_id, username)
    return {"id": confirmed_id, "username": username}, username


async def _telegram_from_signed(params: dict) -> tuple[dict, str] | None:
    tg = verify_telegram_widget(params)
    if not tg:
        return await _telegram_from_bot_login(params)
    username = (tg.get("username") or tg.get("first_name") or str(tg["id"])).lstrip("@")
    login_token = str(params.get("login_token") or "").strip()
    if login_token:
        confirm_telegram_login(login_token, tg["id"], username)
    return tg, username


async def complete_telegram_session(
    request: Request, tg_id: int, username: str, photo: str | None = None, redirect_to: str | None = None,
):
    ip = client_ip(request)
    is_admin_tg = 1 if str(tg_id) in ADMIN_TELEGRAM_IDS else 0
    bot_id = tg_id
    imported = 0
    if not photo:
        photo = await tg_photo.save_telegram_avatar(tg_id)
    try:
        created = await bot_client.ensure_user(telegram_id=tg_id, username=username)
        bot_id = int(created.get("userId") or tg_id)
        subs = await bot_client.subscriptions(bot_id)
        imported = len(subs.get("oneTime") or []) + len(subs.get("recurring") or [])
        save_bot_sub_cache(tg_id, subs)
    except BotAPIError as e:
        log.warning("telegram bot sync: %s", e)

    uid = current_user_id(request)
    with db() as conn:
        if uid:
            me = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if not me:
                return json_error("Unauthorized", 401)
            if me["telegram_id"] and me["telegram_id"] != tg_id:
                return json_error("До акаунта вже привʼязаний інший Telegram", 409)
            taken = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,)).fetchone()
            if taken and taken["id"] != uid and taken["email"]:
                return json_error("Цей Telegram уже привʼязаний до іншого акаунта", 409)
            if me["bot_user_id"] and int(me["bot_user_id"]) != bot_id:
                try:
                    linked = await bot_client.link_user(int(me["bot_user_id"]), tg_id, username, me["email"])
                    bot_id = int((linked.get("user") or {}).get("userId") or bot_id)
                    imported = int(linked.get("imported") or imported)
                except BotAPIError as e:
                    log.warning("telegram link: %s", e)
            is_admin = 1 if me["is_admin"] or is_admin_tg else 0
            conn.execute(
                """
                UPDATE users SET telegram_id = ?, telegram_name = ?, telegram_photo = ?,
                    bot_user_id = ?, is_admin = ?, last_login_ip = ?, last_login_at = ?
                WHERE id = ?
                """,
                (tg_id, username, photo or me["telegram_photo"], bot_id, is_admin, ip, now(), uid),
            )
            if taken and taken["id"] != uid:
                conn.execute("UPDATE users SET telegram_id = NULL WHERE id = ?", (taken["id"],))
            user_id = uid
        else:
            existing = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,)).fetchone()
            if existing:
                is_admin = 1 if existing["is_admin"] or is_admin_tg else 0
                conn.execute(
                    """
                    UPDATE users SET telegram_name = ?, telegram_photo = ?, bot_user_id = ?,
                        is_admin = ?, last_login_ip = ?, last_login_at = ?
                    WHERE id = ?
                    """,
                    (username, photo or existing["telegram_photo"], bot_id, is_admin, ip, now(), existing["id"]),
                )
                user_id = existing["id"]
            else:
                user_id = new_id()
                conn.execute(
                    """
                    INSERT INTO users (
                        id, telegram_id, telegram_name, telegram_photo, bot_user_id,
                        is_admin, created_at, last_login_ip, last_login_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, tg_id, username, photo, bot_id, is_admin_tg, now(), ip, now()),
                )

    if redirect_to:
        return set_cookie(RedirectResponse(redirect_to, status_code=302), user_id)
    resp = JSONResponse({"ok": True, "linked": True, "imported": imported, "login": True})
    return set_cookie(resp, user_id)


@app.get("/api/health")
async def health():
    token = normalize_bot_token(TELEGRAM_BOT_TOKEN)
    bot_ok = await _bot_api_ping()
    return {
        "ok": True,
        "telegramToken": bool(token),
        "botApi": bot_ok,
        "botApiUrl": BOT_API_URL,
        "unsyncedPayments": payments_svc.unsynced_count(),
    }


@app.post("/api/admin/sync-payments")
async def admin_sync_payments(request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    before = payments_svc.unsynced_count()
    synced = await payments_svc.sync_pending_to_bot()
    return {
        "ok": True,
        "before": before,
        "synced": synced,
        "remaining": payments_svc.unsynced_count(),
        "botApi": await _bot_api_ping(),
    }


@app.get("/api/me")
async def me(request: Request):
    uid = current_user_id(request)
    if not uid:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    row = get_user(uid)
    if not row:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return user_public(await hydrate_telegram_photo(row))


@app.get("/api/catalog")
async def catalog():
    try:
        return await catalog_svc.get_catalog()
    except BotAPIError as e:
        return json_error(e.message, e.status)


@app.get("/api/products/{product_id}")
async def product(product_id: str):
    item = await catalog_svc.get_product(product_id)
    if not item:
        return json_error("not found", 404)
    return item


@app.get("/api/media/product/{product_id}")
async def media_product(product_id: int):
    resp = catalog_svc.media_response(await catalog_svc.fetch_product_media(product_id))
    return resp or json_error("not found", 404)


@app.get("/api/media/avatar/{telegram_id}")
async def media_avatar(telegram_id: int):
    path = tg_photo.avatar_path(telegram_id)
    if not path:
        return json_error("not found", 404)
    ctype = tg_photo.EXT.get(path.suffix.lower(), "image/jpeg")
    return FileResponse(path, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/media/category/{catalog_id}")
async def media_category(catalog_id: int):
    resp = catalog_svc.media_response(await catalog_svc.fetch_category_media(catalog_id))
    return resp or json_error("not found", 404)


@app.post("/api/auth/register")
async def register(request: Request):
    ip = client_ip(request)
    if not throttle(f"reg:{ip}", 5, 3600):
        return json_error("Забагато спроб. Спробуй пізніше.", 429)
    body = await request.json()
    mail_addr = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not EMAIL_RE.match(mail_addr):
        return json_error("Схоже, у пошті помилка")
    problem = password_problem(password)
    if problem:
        return json_error(problem)
    with db() as conn:
        if conn.execute("SELECT id FROM users WHERE email = ?", (mail_addr,)).fetchone():
            return json_error("Такий акаунт вже є. Спробуй увійти.", 409)
        user_id = new_id()
        is_admin = 1 if mail_addr in ADMIN_EMAILS else 0
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, is_admin, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, mail_addr, hash_password(password), is_admin, now()),
        )
        token = secrets.token_urlsafe(32)
        conn.execute(
            """
            INSERT INTO tokens (id, user_id, kind, value, expires_at)
            VALUES (?, ?, 'EMAIL_VERIFY', ?, ?)
            """,
            (new_id(), user_id, token, later(24)),
        )
    try:
        bot_user = await bot_client.ensure_user(email=mail_addr, username=mail_addr)
        with db() as conn:
            conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (bot_user.get("userId"), user_id))
    except BotAPIError as e:
        log.warning("register bot user: %s", e)
    try:
        await mail.send_verify(mail_addr, token)
    except Exception as e:
        log.error("verify mail: %s", e)
    resp = JSONResponse({"ok": True, "needsVerify": True})
    return set_cookie(resp, user_id)


@app.post("/api/auth/login")
async def login(request: Request):
    ip = client_ip(request)
    body = await request.json()
    mail_addr = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not throttle(f"login:{ip}:{mail_addr}", 8, 15 * 60):
        return json_error("Забагато спроб. Спробуй пізніше.", 429)
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (mail_addr,)).fetchone()
        if not row or not row["password_hash"] or not check_password(password, row["password_hash"]):
            return json_error("Пошта або пароль не збігаються", 401)
        known = row["last_login_ip"] == ip
        conn.execute(
            "UPDATE users SET last_login_ip = ?, last_login_at = ? WHERE id = ?",
            (ip, now(), row["id"]),
        )
    if not known and row["email"] and row["last_login_ip"]:
        try:
            await mail.send_login(
                row["email"],
                datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
                ip,
            )
        except Exception as e:
            log.error("login mail: %s", e)
    resp = JSONResponse({"ok": True})
    return set_cookie(resp, row["id"])


@app.post("/api/auth/logout")
async def logout():
    return clear_cookie(JSONResponse({"ok": True}))


@app.get("/api/auth/verify")
async def verify(token: str = ""):
    with db() as conn:
        row = conn.execute("SELECT * FROM tokens WHERE value = ?", (token,)).fetchone()
        if not row or row["kind"] != "EMAIL_VERIFY" or row["used_at"] or row["expires_at"] < now():
            return RedirectResponse(f"{APP_URL}/login?verify=fail")
        conn.execute("UPDATE users SET email_verified = ? WHERE id = ?", (now(), row["user_id"]))
        conn.execute("UPDATE tokens SET used_at = ? WHERE id = ?", (now(), row["id"]))
        user = conn.execute("SELECT email FROM users WHERE id = ?", (row["user_id"],)).fetchone()
    if user and user["email"]:
        try:
            await mail.send_welcome(user["email"])
        except Exception as e:
            log.error("welcome mail: %s", e)
    return RedirectResponse(f"{APP_URL}/cabinet?verified=1")


@app.post("/api/auth/resend")
async def resend(request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    if not throttle(f"resend:{uid}", 3, 3600):
        return json_error("Забагато запитів. Спробуй за годину.", 429)
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if not row or not row["email"]:
            return json_error("До акаунта не привʼязана пошта")
        if row["email_verified"]:
            return JSONResponse({"ok": True})
        token = secrets.token_urlsafe(32)
        conn.execute(
            "INSERT INTO tokens (id, user_id, kind, value, expires_at) VALUES (?, ?, 'EMAIL_VERIFY', ?, ?)",
            (new_id(), uid, token, later(24)),
        )
    try:
        await mail.send_verify(row["email"], token)
    except Exception:
        return json_error("Пошта тимчасово не відправляється. Напиши в бот.", 502)
    return JSONResponse({"ok": True})


@app.post("/api/auth/forgot")
async def forgot(request: Request):
    ip = client_ip(request)
    if not throttle(f"forgot:{ip}", 5, 3600):
        return json_error("Забагато запитів", 429)
    body = await request.json()
    mail_addr = str(body.get("email") or "").strip().lower()
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (mail_addr,)).fetchone()
        if row and row["password_hash"]:
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO tokens (id, user_id, kind, value, expires_at) VALUES (?, ?, 'PASSWORD_RESET', ?, ?)",
                (new_id(), row["id"], token, later(1)),
            )
            try:
                await mail.send_reset(mail_addr, token)
            except Exception as e:
                log.error("reset mail: %s", e)
    return JSONResponse({"ok": True})


@app.post("/api/auth/reset")
async def reset(request: Request):
    body = await request.json()
    value = str(body.get("token") or "")
    password = str(body.get("password") or "")
    problem = password_problem(password)
    if problem:
        return json_error(problem)
    with db() as conn:
        token = conn.execute("SELECT * FROM tokens WHERE value = ?", (value,)).fetchone()
        if not token or token["kind"] != "PASSWORD_RESET" or token["used_at"] or token["expires_at"] < now():
            return json_error("Посилання протухло. Запроси нове.")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), token["user_id"]))
        conn.execute("UPDATE tokens SET used_at = ? WHERE id = ?", (now(), token["id"]))
        user_id = token["user_id"]
    return set_cookie(JSONResponse({"ok": True}), user_id)


@app.post("/api/auth/link")
async def auth_link(request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    try:
        body = await request.json()
    except Exception:
        return json_error("Немає даних")
    code = str(body.get("code") or "").strip().upper()
    if len(code) < 4:
        return json_error("Введи код з бота")

    me = get_user(uid)
    if not me:
        return json_error("Unauthorized", 401)

    try:
        linked = await bot_client.consume_link_code(code)
    except BotAPIError as e:
        return json_error(e.message, e.status)

    purchase_uid = int(linked.get("userId") or 0)
    if not purchase_uid:
        return json_error("Код недійсний", 400)

    site_bot_id = await resolve_bot_user_id(me, uid)
    if not site_bot_id:
        return json_error("Спочатку увійди через email або Telegram", 400)

    if int(site_bot_id) == purchase_uid:
        subs = await bot_client.subscriptions(purchase_uid)
        imported = len(subs.get("oneTime") or []) + len(subs.get("recurring") or [])
        cache_id = int(me["telegram_id"] or purchase_uid)
        save_bot_sub_cache(cache_id, subs)
        return {"ok": True, "imported": imported}

    try:
        result = await bot_client.link_user(
            int(site_bot_id),
            purchase_uid,
            me.get("telegram_name") or linked.get("username"),
            me.get("email"),
        )
    except BotAPIError as e:
        return json_error(e.message, e.status)

    merged_id = int((result.get("user") or {}).get("userId") or purchase_uid)
    imported = int(result.get("imported") or 0)
    with db() as conn:
        conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (merged_id, uid))
        if not me.get("telegram_id") and purchase_uid > 0:
            conn.execute(
                "UPDATE users SET telegram_id = ?, telegram_name = COALESCE(telegram_name, ?) WHERE id = ?",
                (purchase_uid, linked.get("username"), uid),
            )
    save_bot_sub_cache(int(me.get("telegram_id") or purchase_uid), {
        "oneTime": result.get("oneTime") or [],
        "recurring": result.get("recurring") or [],
    })
    return {"ok": True, "imported": imported}


@app.post("/api/auth/telegram/start")
async def telegram_start(request: Request):
    origin = resolve_request_origin(
        request.headers.get("origin") or "",
        request.headers.get("referer") or "",
        request.headers.get("x-forwarded-host") or request.headers.get("host") or "",
    )
    token = secrets.token_hex(8)
    try:
        data = await bot_client.start_web_login(origin)
        token = data.get("token") or token
    except BotAPIError as e:
        log.info("web-login via bot API skipped: %s", e)
    save_telegram_login(token, origin)
    bot = (TELEGRAM_BOT_NAME or "FlixMarketBot").lstrip("@")
    payload = telegram_start_payload(token, origin)
    return {"ok": True, "token": token, "url": f"https://t.me/{bot}?start={payload}", "origin": origin}


@app.post("/api/auth/telegram/bot-confirm")
async def telegram_bot_confirm(request: Request):
    try:
        body = await request.json()
    except Exception:
        return json_error("Немає даних підтвердження")
    flat = {k: str(v) for k, v in body.items() if v is not None and not isinstance(v, (dict, list))}
    parsed = await _telegram_from_signed(flat)
    if not parsed:
        login_token = str(flat.get("login_token") or "").strip()
        tg_id_raw = str(flat.get("id") or "").strip()
        if login_token and tg_id_raw.isdigit():
            try:
                data = await bot_client.web_login_status(login_token)
            except BotAPIError:
                data = {}
            if data.get("status") == "confirmed" and int(data.get("telegramId") or 0) == int(tg_id_raw):
                username = (data.get("username") or tg_id_raw).lstrip("@")
                confirm_telegram_login(login_token, int(tg_id_raw), username)
                parsed = ({"id": int(tg_id_raw), "username": username}, username)
        if not parsed:
            token_ok = bool(normalize_bot_token(TELEGRAM_BOT_TOKEN))
            hint = (
                "У .env сайту є дублікат TELEGRAM_BOT_TOKEN=\"\" в кінці файлу — видали його. "
                if not token_ok
                else "Натисни Start у боті з посилання (не /start вручну) і спробуй ще раз. "
            )
            return json_error(
                "Підпис Telegram не пройшов перевірку. "
                + hint
                + "TELEGRAM_BOT_TOKEN на сайті = BOT_TOKEN у бота (без лапок).",
                401,
            )
    tg, _username = parsed
    subs = body.get("subscriptions")
    if isinstance(subs, dict):
        save_bot_sub_cache(tg["id"], subs)
    return {"ok": True}


@app.get("/api/auth/telegram/callback")
async def telegram_callback(request: Request):
    params = {k: str(v) for k, v in request.query_params.items() if v is not None}
    parsed = await _telegram_from_signed(params)
    if not parsed:
        return json_error(
            "Підпис Telegram не пройшов перевірку. "
            "Повернись на вкладку з сайтом — кабінет має відкритись сам. "
            "Якщо ні — натисни «Увійти через Telegram» ще раз.",
        )
    tg, username = parsed
    photo = (tg.get("photo_url") or "").strip() or None
    login_token = str(params.get("login_token") or "").strip()
    redirect_base = APP_URL
    if login_token:
        row = get_telegram_login(login_token)
        origin = (row or {}).get("origin") or ""
        if origin and origin in SITE_ORIGINS:
            redirect_base = origin
    return await complete_telegram_session(
        request, tg["id"], username, photo, redirect_to=f"{redirect_base}/cabinet",
    )


@app.get("/api/auth/telegram/status")
async def telegram_status(request: Request):
    token = (request.query_params.get("token") or "").strip()
    if not token:
        return json_error("Немає токена входу")
    local = await consume_telegram_login(request, token)
    pending = isinstance(local, dict) and local.get("status") == "pending"
    if local is not None and not pending:
        return local
    try:
        data = await bot_client.web_login_status(token)
    except BotAPIError:
        return local or {"status": "pending"}
    status = data.get("status")
    if status != "confirmed":
        return {"status": status or "pending"}
    tg_id = int(data.get("telegramId") or 0)
    if not tg_id:
        return {"status": "pending"}
    username = (data.get("username") or str(tg_id)).lstrip("@")
    confirm_telegram_login(token, tg_id, username)
    return await complete_telegram_session(request, tg_id, username)


@app.post("/api/auth/telegram")
async def telegram_auth(request: Request):
    body = await request.json()
    tg = verify_telegram_widget({k: str(v) for k, v in body.items() if v is not None})
    if not tg:
        return json_error("Підпис Telegram не пройшов перевірку")
    tg_id = tg["id"]
    username = (tg.get("username") or tg.get("first_name") or str(tg_id)).lstrip("@")
    photo = (tg.get("photo_url") or "").strip() or None
    return await complete_telegram_session(request, tg_id, username, photo)


@app.post("/api/checkout")
async def checkout(request: Request):
    body = await request.json()
    product_id = body.get("productId") or body.get("product_id")
    months = body.get("months")
    try:
        months = int(months)
        product_id_int = int(product_id)
    except (TypeError, ValueError):
        return json_error("Некоректні дані замовлення")

    me, uid, created_guest = await ensure_checkout_identity(request)
    telegram_id = me.get("telegram_id")
    username = me.get("telegram_name") or (None if is_guest_user(me) else me.get("email")) or "guest"

    item = await catalog_svc.get_product(str(product_id_int))
    if not item:
        return json_error("Товар не знайдено", 404)
    plan = next((p for p in (item.get("plans") or []) if int(p.get("months") or 0) == months), None)
    if not plan:
        return json_error("Такого строку немає")
    amount_uah = int(plan["total"]) / 100
    if amount_uah <= 0:
        return json_error("Некоректна ціна")
    subscription = bool(item.get("recurring") or item.get("paymentType") == "subscription")
    origin = (request.headers.get("origin") or APP_URL or "").rstrip("/")
    auto_issue = bool(item.get("autoIssue"))

    try:
        bot_uid = await resolve_bot_user_id(me, uid)
        if not bot_uid:
            try:
                if telegram_id:
                    created_user = await bot_client.ensure_user(
                        telegram_id=int(telegram_id), username=username,
                    )
                    bot_uid = int(created_user.get("userId") or telegram_id)
                else:
                    guest_email = me.get("email") or f"guest-{uid}@guest.flix.local"
                    created_user = await bot_client.ensure_user(
                        email=guest_email, username=username,
                    )
                    bot_uid = int(created_user.get("userId"))
            except BotAPIError as e:
                return json_error(e.message or "Не вдалось створити акаунт для оплати", min(e.status, 502))
            with db() as conn:
                conn.execute("UPDATE users SET bot_user_id = ? WHERE id = ?", (bot_uid, uid))

        payment_ref = f"site_{bot_uid}_{int(time.time())}"
        redirect_url = f"{origin or APP_URL}/order/{payment_ref}"
        created = await monopay.create_invoice(
            user_id=bot_uid,
            product_name=item.get("name") or "Підписка",
            months=months,
            amount_uah=amount_uah,
            redirect_url=redirect_url,
            subscription=subscription,
            payment_id=payment_ref,
        )
        payments_svc.save_site_payment(
            payment_id=created["payment_id"],
            invoice_id=created["invoice_id"],
            site_user_id=uid,
            bot_user_id=bot_uid,
            telegram_id=int(telegram_id) if telegram_id else None,
            product_id=product_id_int,
            months=months,
            amount=amount_uah,
            payment_type=created["payment_type"],
            wallet_id=created.get("wallet_id"),
            username=username,
        )
        synced = await payments_svc.sync_payment_to_bot_by_ref(created["invoice_id"])
        if not synced:
            log.warning(
                "checkout: bot API offline, payment %s saved locally — sync later",
                created["invoice_id"],
            )
    except monopay.MonoError as e:
        return json_error(e.message, min(e.status, 502))

    resp = JSONResponse({
        "ok": True,
        "pageUrl": created["page_url"],
        "ref": created["invoice_id"],
        "invoice_id": created["invoice_id"],
        "payment_id": created["payment_id"],
        "autoIssue": auto_issue,
        "guest": created_guest or is_guest_user(me),
    })
    if created_guest:
        set_cookie(resp, uid)
    return resp


@app.get("/api/order/{ref}")
async def order_status(ref: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    row = payments_svc.get_site_payment(ref)
    if not row:
        return json_error("Замовлення не знайдено", 404)
    if str(row.get("site_user_id")) != str(uid):
        return json_error("Це чуже замовлення", 403)

    status = (row.get("status") or "pending").lower()
    product = await catalog_svc.get_product(str(row["product_id"]))
    auto_issue = bool(product and product.get("autoIssue")) if product else stock_svc.is_auto_issue(int(row["product_id"]))
    delivery = None
    if status in ("success", "paid"):
        await stock_svc.process_paid_payment(row)
        drow = stock_svc.get_delivery_access_for_payment(uid, str(row.get("invoice_id") or ""))
        if drow:
            delivery = drow

    support_text = (
        f"Привіт! Оплатив замовлення на сайті flixмаркет.\n"
        f"Номер: {row.get('payment_id')}\n"
        f"Товар: {(product or {}).get('name') or row.get('product_id')}\n"
        f"Строк: {row.get('months')} міс."
    )
    return {
        "ok": True,
        "paymentId": row.get("payment_id"),
        "invoiceId": row.get("invoice_id"),
        "status": status,
        "amount": row.get("amount"),
        "months": row.get("months"),
        "productId": str(row.get("product_id")),
        "productName": (product or {}).get("name"),
        "productSlug": (product or {}).get("slug"),
        "photoUrl": (product or {}).get("photoUrl"),
        "autoIssue": auto_issue,
        "delivery": delivery,
        "supportUrl": f"https://t.me/kinomanage?text={quote(support_text)}",
        "supportText": support_text,
    }


@app.post("/api/order/{ref}/code")
async def order_code(ref: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    row = payments_svc.get_site_payment(ref)
    if not row or str(row.get("site_user_id")) != str(uid):
        return json_error("Замовлення не знайдено", 404)
    ip = request.client.host if request.client else ""
    result = stock_svc.totp_code_for_payment(uid, str(row.get("invoice_id") or ""), ip=ip)
    if not result.get("ok"):
        return json_error(result.get("error") or "Не вдалось отримати код", 400)
    return result


@app.post("/api/webhooks/mono")
async def mono_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    invoice_id = str(payload.get("invoiceId") or payload.get("invoice_id") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    log.info("mono webhook invoice=%s status=%s", invoice_id, status)
    await payments_svc.handle_mono_webhook(payload)
    return {"ok": True}


@app.get("/api/cabinet")
async def cabinet(request: Request, order: str | None = None):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    me = get_user(uid)
    if not me:
        return json_error("Unauthorized", 401)
    me = await hydrate_telegram_photo(me)
    subs = {"oneTime": [], "recurring": []}
    payments = []
    pending = None
    bot_profile = None
    bot_id = await resolve_bot_user_id(me, uid) or me["bot_user_id"] or me["telegram_id"]
    if bot_id:
        try:
            bot_profile = await bot_client.bot_user(int(bot_id))
        except BotAPIError:
            bot_profile = None
        try:
            live = await bot_client.subscriptions(int(bot_id))
            subs = {
                "oneTime": live.get("oneTime") or [],
                "recurring": live.get("recurring") or [],
            }
            save_bot_sub_cache(int(me["telegram_id"] or bot_id), subs)
            try:
                pay_data = await bot_client.user_payments(int(bot_id))
                payments = pay_data.get("payments") or []
            except BotAPIError as e:
                log.warning("cabinet payments: %s", e)
            if order:
                try:
                    pending = await bot_client.get_payment(order)
                except BotAPIError:
                    pending = payments_svc.payment_public(payments_svc.get_site_payment(order))
        except BotAPIError as e:
            log.warning("cabinet bot: %s", e)
            cached = get_bot_sub_cache(int(me["telegram_id"] or bot_id))
            if cached:
                subs = {
                    "oneTime": cached.get("oneTime") or [],
                    "recurring": cached.get("recurring") or [],
                }
    elif me["telegram_id"]:
        cached = get_bot_sub_cache(int(me["telegram_id"]))
        if cached:
            subs = {
                "oneTime": cached.get("oneTime") or [],
                "recurring": cached.get("recurring") or [],
            }
    for bucket in (subs.get("oneTime") or [], subs.get("recurring") or []):
        for sub in bucket:
            pid = sub.get("productId")
            if pid and not sub.get("photoUrl"):
                sub["photoUrl"] = f"/api/media/product/{pid}"

    stock_svc.enrich_subscriptions(uid, subs)
    stock_svc.append_orphan_deliveries(uid, subs)
    for bucket in (subs.get("oneTime") or [],):
        for sub in bucket:
            if not str(sub.get("id") or "").startswith("del-"):
                continue
            pid = sub.get("productId")
            if not pid:
                continue
            product = await catalog_svc.get_product(str(pid))
            if product:
                sub["name"] = product.get("name") or sub.get("name")
                sub["slug"] = product.get("slug")
                sub["icon"] = product.get("icon")
                sub["color"] = product.get("color")
                sub["photoUrl"] = product.get("photoUrl") or sub.get("photoUrl")

    return {
        "user": user_public(me),
        "bot": bot_profile,
        "subscriptions": subs,
        "payments": payments,
        "pending": pending,
    }


@app.post("/api/subs/{sub_id}/cancel")
async def cancel_sub(sub_id: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    me = get_user(uid)
    if not me:
        return json_error("Unauthorized", 401)
    bot_id = await resolve_bot_user_id(me, uid) or me["bot_user_id"] or me["telegram_id"]
    if not bot_id:
        return json_error("Спочатку привʼяжи Telegram або зроби покупку", 400)
    raw = sub_id.replace("rec-", "")
    try:
        bot_sub_id = int(raw)
    except ValueError:
        return json_error("Некоректна підписка")
    try:
        result = await bot_client.cancel_recurring(int(bot_id), bot_sub_id)
    except BotAPIError as e:
        return json_error(e.message, e.status)
    return result


@app.post("/api/subs/{sub_id}/code")
async def sub_code(sub_id: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    ip = request.client.host if request.client else ""
    result = stock_svc.totp_code_for_sub(uid, sub_id, ip=ip)
    if not result.get("ok"):
        return json_error(result.get("error") or "Не вдалось отримати код", 400)
    return {"code": result["code"], "secondsLeft": result["secondsLeft"]}


@app.get("/api/admin/stock")
async def admin_stock(request: Request, product_id: int | None = None):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    try:
        catalog_data = await catalog_svc.get_catalog()
    except BotAPIError as e:
        return json_error(e.message, e.status)
    products = catalog_data.get("products") or []
    settings = stock_svc.list_product_settings(
        [int(p.get("botId") or p.get("id")) for p in products if str(p.get("botId") or p.get("id")).isdigit()]
    )
    creds = stock_svc.list_credentials(product_id)
    stock_counts: dict[str, int] = {}
    for cred in creds:
        pid = cred["productId"]
        stock_counts[pid] = stock_counts.get(pid, 0) + cred["slotsFree"]
    return {
        "products": [
            {
                "id": str(p.get("botId") or p.get("id")),
                "name": p.get("name"),
                "autoIssue": settings.get(int(p.get("botId") or p.get("id")), False),
                "stockFree": stock_counts.get(str(p.get("botId") or p.get("id")), 0),
            }
            for p in products
        ],
        "credentials": creds,
    }


@app.post("/api/admin/stock/products/{product_id}")
async def admin_stock_product(product_id: int, request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    stock_svc.set_auto_issue(product_id, bool(body.get("autoIssue")))
    return {"ok": True, "autoIssue": stock_svc.is_auto_issue(product_id)}


@app.post("/api/admin/stock/credentials")
async def admin_stock_add(request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    try:
        body = await request.json()
    except Exception:
        return json_error("Некоректні дані", 400)
    login = (body.get("login") or "").strip()
    password = (body.get("password") or "").strip()
    if not login or not password:
        return json_error("Логін і пароль обовʼязкові", 400)
    try:
        product_id = int(body.get("productId"))
    except (TypeError, ValueError):
        return json_error("Обери товар", 400)
    cred = stock_svc.add_credential(
        product_id=product_id,
        login=login,
        password=password,
        totp_secret=(body.get("totpSecret") or "").strip() or None,
        slots_total=int(body.get("slotsTotal") or 1),
        note=(body.get("note") or "").strip(),
    )
    return {"ok": True, "credential": cred}


@app.patch("/api/admin/stock/credentials/{cred_id}")
async def admin_stock_update(cred_id: str, request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    cred = stock_svc.update_credential(
        cred_id,
        login=body.get("login"),
        password=body.get("password"),
        totp_secret=body.get("totpSecret"),
        clear_totp=bool(body.get("clearTotp")),
        slots_total=body.get("slotsTotal"),
        note=body.get("note"),
        active=body.get("active"),
    )
    if not cred:
        return json_error("Акаунт не знайдено", 404)
    return {"ok": True, "credential": cred}


@app.delete("/api/admin/stock/credentials/{cred_id}")
async def admin_stock_delete(cred_id: str, request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    if not stock_svc.delete_credential(cred_id):
        return json_error("Акаунт не знайдено", 404)
    return {"ok": True}


@app.get("/api/admin/overview")
async def admin_overview(request: Request):
    uid = current_user_id(request)
    me = get_user(uid) if uid else None
    if not me or not me["is_admin"]:
        return json_error("Forbidden", 403)
    try:
        stats = await bot_client.admin_stats()
        payments = await bot_client.admin_payments()
        users = await bot_client.admin_users()
        catalog_data = await catalog_svc.get_catalog()
    except BotAPIError as e:
        return json_error(e.message, e.status)
    return {
        "stats": stats,
        "payments": payments.get("payments") or [],
        "users": users.get("users") or [],
        "products": catalog_data.get("products") or [],
        "categories": catalog_data.get("categories") or [],
    }
