"""Каталог сайту: бот (джерело правди) + мініапка (фото, бейджі, fallback)."""
from __future__ import annotations

import asyncio
import logging
import re
import time

import httpx
from fastapi.responses import Response

from . import bot_client
from .bot_client import BotAPIError
from .settings import BOT_API_URL, MINIAPP_API_KEY, MINIAPP_API_URL

log = logging.getLogger(__name__)

_CACHE_TTL = 15.0
_cache: dict = {"at": 0.0, "data": None}

_ICON_MAP = (
    ("netflix", "netflix", "#E50914"),
    ("chatgpt", "openai", "#10A37F"),
    ("openai", "openai", "#10A37F"),
    ("grok", "x", "#111111"),
    ("claude", "anthropic", "#D4A27F"),
    ("spotify", "spotify", "#1DB954"),
    ("youtube", "youtube", "#FF0000"),
    ("disney", "disneyplus", "#113CCF"),
    ("hbo", "hbo", "#000000"),
    ("sweet", "youtube", "#E31E24"),
    ("vpn", "protonvpn", "#6D4AFF"),
    ("ipvanish", "protonvpn", "#6D4AFF"),
    ("filmix", "imdb", "#F5C518"),
    ("iptv", "youtube", "#FF0000"),
    ("apple", "apple", "#111111"),
    ("adobe", "adobe", "#FF0000"),
    ("gemini", "google", "#4285F4"),
)


def clean_text(value) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", str(value))
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_tariffs(price_str) -> list[tuple[int, float]]:
    tariffs: list[tuple[int, float]] = []
    if price_str is None:
        return tariffs
    raw = str(price_str).strip()
    if not raw:
        return tariffs
    parts = [p.strip() for p in raw.split(",")] if "," in raw else [raw]
    for part in parts:
        if "-" not in part:
            part = f"1-{part}"
        months_s, price_s = part.split("-", 1)
        try:
            months = int(months_s.strip())
            price = float(price_s.strip().replace(",", ".").replace("₴", "").replace("грн", ""))
        except ValueError:
            continue
        tariffs.append((months, price))
    return tariffs


def icon_for(hay: str) -> tuple[str, str]:
    low = hay.lower()
    for needle, icon, color in _ICON_MAP:
        if needle in low:
            return icon, color
    return "", "#2B5CF6"


def uah_to_kop(amount: float) -> int:
    return int(round(float(amount) * 100))


def slug_for(product_id, name: str) -> str:
    ascii_name = re.sub(r"[^a-zA-Z0-9]+", "-", clean_text(name) or "item").strip("-").lower() or "item"
    return f"{ascii_name}-{product_id}"


def serialize_mini_product(raw: dict) -> dict:
    pid = raw.get("id")
    tariffs = parse_tariffs(raw.get("product_price"))
    by_months = {m: uah_to_kop(p) for m, p in tariffs}
    recurring = (raw.get("payment_type") or "") == "subscription"
    monthly = by_months.get(1, 0)
    if not monthly and tariffs:
        months, price = min(tariffs, key=lambda t: t[1] / max(t[0], 1))
        monthly = uah_to_kop(price / months)
    icon, color = icon_for(f"{raw.get('product_type') or ''} {raw.get('product_name') or ''}")
    name = clean_text(raw.get("product_name"))
    plans = [
        {
            "months": m,
            "total": uah_to_kop(p),
            "perMonth": uah_to_kop(p / m) if m else 0,
            "label": "щомісяця" if recurring and m == 1 else f"{m} міс",
            "off": 0,
        }
        for m, p in tariffs
    ]
    if monthly:
        for plan in plans:
            full = monthly * plan["months"]
            if full > 0:
                plan["off"] = max(0, round((1 - plan["total"] / full) * 100))
    photo = raw.get("product_photo")
    return {
        "id": str(pid),
        "botId": pid,
        "slug": slug_for(pid, name),
        "name": name,
        "icon": icon,
        "color": color,
        "description": clean_text(raw.get("product_description")),
        "features": "",
        "recurring": recurring,
        "price": monthly,
        "price3": by_months.get(3, 0),
        "price6": by_months.get(6, 0),
        "price12": by_months.get(12, 0),
        "faq": "",
        "deliveryNote": "Після оплати менеджер надішле доступ у Telegram або на пошту.",
        "visible": True,
        "autoIssue": False,
        "categoryId": str(raw.get("catalog_id") or ""),
        "categoryName": clean_text(raw.get("product_type") or "Інше"),
        "photoUrl": f"/api/media/product/{pid}" if photo else None,
        "badge": (raw.get("product_badge") or "").strip() or None,
        "tariff": str(raw.get("product_price") or ""),
        "paymentType": "subscription" if recurring else "one_time",
        "plans": plans,
    }


def serialize_mini_category(raw: dict, count: int = 0) -> dict:
    cid = raw.get("catalog_id")
    name = clean_text(raw.get("product_type") or "Інше")
    icon, color = icon_for(name)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower() or f"cat-{cid}"
    photo = raw.get("catalog_photo")
    return {
        "id": str(cid),
        "slug": f"{slug}-{cid}",
        "name": name,
        "icon": icon,
        "color": color,
        "sortOrder": cid or 0,
        "active": True,
        "count": count,
        "photoUrl": f"/api/media/category/{cid}" if photo else None,
    }


def apply_stock_settings(catalog: dict) -> dict:
    from .stock_svc import list_product_settings

    products = catalog.get("products") or []
    ids: list[int] = []
    for product in products:
        raw = product.get("botId") or product.get("id")
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    settings = list_product_settings(ids)
    for product in products:
        try:
            pid = int(product.get("botId") or product.get("id"))
        except (TypeError, ValueError):
            product["autoIssue"] = False
            continue
        product["autoIssue"] = settings.get(pid, False)
    return catalog


def rewrite_site_urls(catalog: dict) -> dict:
    for product in catalog.get("products") or []:
        pid = product.get("botId") or product.get("id")
        if product.get("photoUrl"):
            product["photoUrl"] = f"/api/media/product/{pid}"
    for category in catalog.get("categories") or []:
        if category.get("photoUrl"):
            category["photoUrl"] = f"/api/media/category/{category['id']}"
    return catalog


def overlay_miniapp(catalog: dict, mini_cats: list, mini_products: list) -> dict:
    by_id = {str(p.get("id")): p for p in mini_products}
    for product in catalog.get("products") or []:
        mini = by_id.get(str(product.get("botId") or product.get("id")))
        if not mini:
            continue
        badge = (mini.get("product_badge") or "").strip()
        if badge and not product.get("badge"):
            product["badge"] = badge
        if mini.get("product_photo") and not product.get("photoUrl"):
            product["photoUrl"] = f"/api/media/product/{product.get('botId') or product.get('id')}"
        if not product.get("tariff") and mini.get("product_price") is not None:
            product["tariff"] = str(mini.get("product_price"))
    by_cat = {str(c.get("catalog_id")): c for c in mini_cats}
    for category in catalog.get("categories") or []:
        mini = by_cat.get(str(category.get("id")))
        if mini and mini.get("catalog_photo") and not category.get("photoUrl"):
            category["photoUrl"] = f"/api/media/category/{category['id']}"
    return catalog


async def _miniapp_get(path: str):
    if not MINIAPP_API_URL:
        return None
    url = f"{MINIAPP_API_URL}{path}"
    headers = {"Accept": "application/json"}
    if MINIAPP_API_KEY:
        headers["X-API-Key"] = MINIAPP_API_KEY
    try:
        async with httpx.AsyncClient(timeout=2.5, follow_redirects=True) as client:
            res = await client.get(url, headers=headers)
    except httpx.RequestError as e:
        log.info("mini-app %s: %s", path, e)
        return None
    if res.status_code >= 400:
        log.info("mini-app %s -> %s", path, res.status_code)
        return None
    try:
        return res.json()
    except Exception:
        return None


async def fetch_miniapp() -> tuple[list, list]:
    cats = await _miniapp_get("/api/catalog")
    if not isinstance(cats, list):
        preview = await _miniapp_get("/api/products")
        return [], preview if isinstance(preview, list) else []

    products: list = []
    seen: set[int] = set()

    async def load_cat(cid):
        items = await _miniapp_get(f"/api/catalog/{cid}")
        return items if isinstance(items, list) else []

    loaded = await asyncio.gather(*(load_cat(c.get("catalog_id")) for c in cats), return_exceptions=True)
    for items in loaded:
        if isinstance(items, Exception) or not items:
            continue
        for item in items:
            pid = item.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            products.append(item)

    if not products:
        preview = await _miniapp_get("/api/products")
        if isinstance(preview, list):
            products = preview
    return cats, products


def from_miniapp(cats: list, products: list) -> dict:
    serialized_products = [serialize_mini_product(p) for p in products]
    counts: dict[str, int] = {}
    for p in serialized_products:
        cid = str(p.get("categoryId") or "")
        counts[cid] = counts.get(cid, 0) + 1
    categories = [serialize_mini_category(c, counts.get(str(c.get("catalog_id")), 0)) for c in cats]
    if not categories:
        by_name: dict[str, dict] = {}
        for p in serialized_products:
            cid = str(p.get("categoryId") or "")
            if cid not in by_name:
                by_name[cid] = serialize_mini_category(
                    {"catalog_id": p.get("categoryId"), "product_type": p.get("categoryName")},
                    counts.get(cid, 0),
                )
        categories = list(by_name.values())
    return {"categories": categories, "products": serialized_products}


async def _load_catalog() -> dict:
    bot_data = None
    bot_error = None
    mini_cats: list = []
    mini_products: list = []

    async def from_bot():
        nonlocal bot_data, bot_error
        try:
            bot_data = await bot_client.catalog()
        except BotAPIError as e:
            bot_error = e
            log.warning("bot catalog: %s", e)

    async def from_mini():
        nonlocal mini_cats, mini_products
        mini_cats, mini_products = await fetch_miniapp()

    await asyncio.gather(from_bot(), from_mini())

    # Бот — джерело каталогу. Мініапка лише додає фото/бейджі, якщо жива.
    if bot_data and (bot_data.get("products") or bot_data.get("categories")):
        catalog = rewrite_site_urls(bot_data)
        if mini_cats or mini_products:
            catalog = overlay_miniapp(catalog, mini_cats, mini_products)
        return catalog

    if mini_cats or mini_products:
        return rewrite_site_urls(from_miniapp(mini_cats, mini_products))

    if bot_error:
        raise bot_error
    return {"categories": [], "products": []}


async def get_catalog() -> dict:
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < _CACHE_TTL:
        return _cache["data"]
    data = apply_stock_settings(await _load_catalog())
    _cache["data"] = data
    _cache["at"] = now
    return data


async def get_product(product_id: str) -> dict | None:
    catalog = await get_catalog()
    for product in catalog.get("products") or []:
        if (
            str(product.get("id")) == str(product_id)
            or product.get("slug") == product_id
            or str(product.get("botId")) == str(product_id)
        ):
            return product
    try:
        product = await bot_client.product(product_id)
        return rewrite_site_urls({"products": [product], "categories": []})["products"][0]
    except BotAPIError:
        pass
    if product_id.isdigit() and MINIAPP_API_URL:
        raw = await _miniapp_get(f"/api/products/{product_id}")
        if isinstance(raw, dict) and raw.get("id"):
            return serialize_mini_product(raw)
    return None


async def _get_bytes(url: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(url)
    except httpx.RequestError:
        return None
    if res.status_code != 200 or not res.content:
        return None
    ctype = (res.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
    if ctype.startswith("image/") or ctype in ("application/octet-stream",):
        return res.content, ctype if ctype.startswith("image/") else "image/jpeg"
    if res.content[:3] in (b"\xff\xd8\xff", b"\x89PN") or res.content[:4] == b"RIFF":
        return res.content, "image/jpeg"
    return None


def _abs_mini(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{MINIAPP_API_URL}{url if url.startswith('/') else '/' + url}"


async def fetch_product_media(product_id: int) -> tuple[bytes, str] | None:
    data = await _get_bytes(f"{BOT_API_URL}/api/v1/media/product/{product_id}")
    if data:
        return data
    if not MINIAPP_API_URL:
        return None
    raw = await _miniapp_get(f"/api/products/{product_id}")
    photo = (raw or {}).get("product_photo") if isinstance(raw, dict) else None
    if photo:
        return await _get_bytes(_abs_mini(str(photo)))
    return None


async def fetch_category_media(catalog_id: int) -> tuple[bytes, str] | None:
    data = await _get_bytes(f"{BOT_API_URL}/api/v1/media/category/{catalog_id}")
    if data:
        return data
    if not MINIAPP_API_URL:
        return None
    cats = await _miniapp_get("/api/catalog")
    if not isinstance(cats, list):
        return None
    for cat in cats:
        if str(cat.get("catalog_id")) == str(catalog_id) and cat.get("catalog_photo"):
            return await _get_bytes(_abs_mini(str(cat["catalog_photo"])))
    return None


def media_response(payload: tuple[bytes, str] | None):
    if not payload:
        return None
    body, ctype = payload
    return Response(
        content=body,
        media_type=ctype,
        headers={"Cache-Control": "public, max-age=86400"},
    )
