"""Точка входу сайту: сесії, пошта, проксі до API бота."""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime
from urllib.parse import urlparse

import bcrypt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import bot_client, catalog_svc, mail, monopay, tg_photo
from .bot_client import BotAPIError
from .db import (
    confirm_telegram_login,
    db,
    get_bot_sub_cache,
    get_telegram_login,
    init_db,
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
    COOKIE_NAME,
    COOKIE_SECURE,
    MINIAPP_API_URL,
    SESSION_SECRET,
    TELEGRAM_BOT_NAME,
    TELEGRAM_BOT_TOKEN,
)

log = logging.getLogger("flix.site")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="flixmarket site")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in [APP_URL, MINIAPP_API_URL, "http://localhost:3000", "http://127.0.0.1:3000"] if origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_hits: dict[str, tuple[int, float]] = {}


@app.on_event("startup")
def _startup():
    init_db()
    _warn_if_telegram_token_mismatch()


def _warn_if_telegram_token_mismatch():
    token = (TELEGRAM_BOT_TOKEN or "").strip().strip('"')
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
    resp.set_cookie(
        COOKIE_NAME,
        sign_session(user_id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 30,
    )
    return resp


def clear_cookie(resp: JSONResponse):
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


def client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or request.client.host or "local").split(",")[0].strip()


def current_user_id(request: Request) -> str | None:
    return read_session(request.cookies.get(COOKIE_NAME))


def get_user(user_id: str):
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


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


TG_HASH_FIELDS = (
    "id", "auth_date", "login_token", "username", "first_name", "last_name", "photo_url",
)


def verify_telegram_widget(data: dict) -> dict | None:
    token = (TELEGRAM_BOT_TOKEN or "").strip().strip('"')
    given = str(data.get("hash") or "").strip().lower()
    if not given or not token:
        return None
    rest = {
        k: str(v)
        for k, v in data.items()
        if k in TG_HASH_FIELDS and v is not None and str(v) != ""
    }
    dcs = "\n".join(f"{k}={rest[k]}" for k in sorted(rest))
    secret = hashlib.sha256(token.encode()).digest()
    sign = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    try:
        if not hmac.compare_digest(sign, given):
            log.warning("telegram hash mismatch for fields %s", ",".join(sorted(rest)))
            return None
    except Exception:
        return None
    try:
        if abs(time.time() - float(rest.get("auth_date") or 0)) > 86400:
            return None
    except ValueError:
        return None
    return {
        "id": int(rest["id"]),
        "username": rest.get("username"),
        "first_name": rest.get("first_name"),
        "photo_url": rest.get("photo_url"),
    }


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
    return {"ok": True}


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


@app.post("/api/auth/telegram/start")
async def telegram_start():
    token = secrets.token_hex(8)
    try:
        data = await bot_client.start_web_login(APP_URL)
        token = data.get("token") or token
    except BotAPIError as e:
        log.info("web-login via bot API skipped: %s", e)
    save_telegram_login(token, APP_URL)
    bot = (TELEGRAM_BOT_NAME or "FlixMarketBot").lstrip("@")
    payload = telegram_start_payload(token, APP_URL)
    return {"ok": True, "token": token, "url": f"https://t.me/{bot}?start={payload}"}


def _telegram_from_signed(params: dict) -> tuple[dict, str] | None:
    tg = verify_telegram_widget(params)
    if not tg:
        return None
    username = (tg.get("username") or tg.get("first_name") or str(tg["id"])).lstrip("@")
    login_token = str(params.get("login_token") or "").strip()
    if login_token:
        confirm_telegram_login(login_token, tg["id"], username)
    return tg, username


@app.post("/api/auth/telegram/bot-confirm")
async def telegram_bot_confirm(request: Request):
    try:
        body = await request.json()
    except Exception:
        return json_error("Немає даних підтвердження")
    parsed = _telegram_from_signed({k: str(v) for k, v in body.items() if v is not None})
    if not parsed:
        return json_error(
            "Підпис Telegram не пройшов перевірку. "
            "TELEGRAM_BOT_TOKEN на сайті має бути тим самим, що BOT_TOKEN у бота на сервері.",
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
    parsed = _telegram_from_signed(params)
    if not parsed:
        return json_error(
            "Підпис Telegram не пройшов перевірку. "
            "TELEGRAM_BOT_TOKEN на сайті має бути тим самим, що BOT_TOKEN у бота на сервері.",
        )
    tg, username = parsed
    photo = (tg.get("photo_url") or "").strip() or None
    return await complete_telegram_session(
        request, tg["id"], username, photo, redirect_to=f"{APP_URL}/cabinet",
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
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    body = await request.json()
    product_id = body.get("productId") or body.get("product_id")
    months = body.get("months")
    try:
        months = int(months)
        product_id_int = int(product_id)
    except (TypeError, ValueError):
        return json_error("Некоректні дані замовлення")
    with db() as conn:
        me = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if not me:
            return json_error("Unauthorized", 401)
        telegram_id = me["telegram_id"]
        username = me["telegram_name"] or me["email"]
    if not telegram_id:
        return json_error("Увійди через Telegram, щоб оплатити.")

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
    redirect_url = f"{origin or APP_URL}/cabinet"

    try:
        created_user = await bot_client.ensure_user(telegram_id=int(telegram_id), username=username)
        bot_uid = int(created_user.get("userId") or telegram_id)
        created = await monopay.create_invoice(
            user_id=bot_uid,
            product_name=item.get("name") or "Підписка",
            months=months,
            amount_uah=amount_uah,
            redirect_url=redirect_url,
            subscription=subscription,
        )
        await bot_client.record_payment(
            user_id=bot_uid,
            product_id=product_id_int,
            months=months,
            amount=amount_uah,
            invoice_id=created["invoice_id"],
            payment_id=created["payment_id"],
            payment_type=created["payment_type"],
            wallet_id=created.get("wallet_id"),
            username=username,
        )
    except monopay.MonoError as e:
        return json_error(e.message, min(e.status, 502))
    except BotAPIError as e:
        return json_error(e.message, min(e.status, 502))

    return JSONResponse({
        "ok": True,
        "pageUrl": created["page_url"],
        "ref": created["invoice_id"],
        "invoice_id": created["invoice_id"],
        "payment_id": created["payment_id"],
    })


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
    if invoice_id:
        try:
            await bot_client.forward_mono_webhook(payload)
        except BotAPIError as e:
            log.warning("mono webhook forward: %s", e)
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
    pending = None
    bot_profile = None
    bot_id = me["bot_user_id"] or me["telegram_id"]
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
            if order:
                try:
                    pending = await bot_client.get_payment(order)
                except BotAPIError:
                    pending = None
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
    return {
        "user": user_public(me),
        "bot": bot_profile,
        "subscriptions": subs,
        "pending": pending,
    }


@app.post("/api/subs/{sub_id}/cancel")
async def cancel_sub(sub_id: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    me = get_user(uid)
    if not me or not me["bot_user_id"]:
        return json_error("Спочатку привʼяжи Telegram або зроби покупку", 400)
    raw = sub_id.replace("rec-", "")
    try:
        bot_sub_id = int(raw)
    except ValueError:
        return json_error("Некоректна підписка")
    try:
        result = await bot_client.cancel_recurring(int(me["bot_user_id"]), bot_sub_id)
    except BotAPIError as e:
        return json_error(e.message, e.status)
    return result


@app.post("/api/subs/{sub_id}/code")
async def sub_code(sub_id: str, request: Request):
    uid = current_user_id(request)
    if not uid:
        return json_error("Unauthorized", 401)
    return json_error("Коди 2FA видає менеджер у Telegram-боті після оплати.")


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
