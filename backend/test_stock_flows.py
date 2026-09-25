"""Перевірка ключових сценаріїв складу / видачі / кабінету."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from backend.crypto import encrypt
from backend.db import db, init_db, new_id, now
from backend.sheets_svc import (
    _format_sheet_term,
    _gpt_available,
    _netflix_available,
    _netflix_row_is_used,
)
from backend.stock_svc import (
    _delivery_active,
    _find_delivery_for_sub,
    _product_ids_for_match,
    append_orphan_deliveries,
    enrich_subscriptions,
    init_stock_tables,
    refresh_netflix_stock_aliases,
    stock_source_product_id,
    try_deliver_for_payment,
)


def _meta_d_color(r: float, g: float, b: float) -> dict:
    return {
        "values": [
            {"formattedValue": ""},
            {"formattedValue": "a@b.com"},
            {"formattedValue": "pass"},
            {"effectiveFormat": {"backgroundColor": {"red": r, "green": g, "blue": b}}},
            {"formattedValue": "1"},
        ]
    }


def test_netflix_availability() -> None:
    row = ["", "a@b.com", "pass", "", "1"]
    assert _netflix_available(row, _meta_d_color(1, 1, 1))
    assert not _netflix_available(row, _meta_d_color(0.275, 0.851, 0.953))
    assert not _netflix_available(["", "a@b.com", "pass", "23.10.2026", "1"], None)
    # колір у B, D білий — вільний
    meta = {
        "values": [
            {"effectiveFormat": {"backgroundColor": {"red": 0.275, "green": 0.851, "blue": 0.953}}},
            {"formattedValue": "a@b.com"},
            {"formattedValue": "pass"},
            {"effectiveFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}},
            {"formattedValue": ""},
        ]
    }
    assert _netflix_available(row, meta)

    # Колонка A = № рядка: логін у C, термін у E
    row_new = ["385", "", "a@b.com", "323433", "", ""]
    meta_e_cyan = {
        "values": [
            {"formattedValue": "385"},
            {"formattedValue": ""},
            {"formattedValue": "a@b.com"},
            {"formattedValue": "323433"},
            {"effectiveFormat": {"backgroundColor": {"red": 0.275, "green": 0.851, "blue": 0.953}}},
            {"formattedValue": ""},
        ]
    }
    assert _netflix_available(row_new, None)
    assert not _netflix_available(row_new, meta_e_cyan)
    assert not _netflix_available(["385", "", "a@b.com", "323433", "24.10.2026", ""], None)
    assert not _netflix_available(["385", "", "a@b.com", "323433", "3", ""], None)


def test_sheet_term_format() -> None:
    assert _format_sheet_term(1) == "1"
    assert _format_sheet_term(3) == "3"
    assert _format_sheet_term(6) == "6"
    assert _format_sheet_term(12) == "12"
    assert _format_sheet_term(2) == "3"


def test_netflix_stock_alias() -> None:
    products = [
        {"botId": 10, "name": "Netflix Premium Окремий акаунт"},
        {"botId": 55, "name": "Помісячно Netflix Premium Окремий акаунт"},
    ]
    refresh_netflix_stock_aliases(products)
    assert stock_source_product_id(55, products) == 10
    assert stock_source_product_id(10, products) == 10
    ids = _product_ids_for_match("55")
    assert "10" in ids and "55" in ids


def test_delivery_race() -> None:
    init_db()
    with db() as conn:
        init_stock_tables(conn)
        conn.execute("DELETE FROM deliveries")
        conn.execute("DELETE FROM credentials")
        conn.execute(
            "INSERT OR REPLACE INTO product_settings (product_id, auto_issue, updated_at) VALUES (10, 1, ?)",
            (now(),),
        )
        for i in range(3):
            conn.execute(
                """
                INSERT INTO credentials (
                    id, product_id, login, secret_enc, slots_total, slots_used,
                    note, active, created_at
                ) VALUES (?, 10, ?, ?, 1, 0, '', 1, ?)
                """,
                (new_id(), f"race{i}@test.com", encrypt("p"), now()),
            )

    payment = {
        "status": "success",
        "invoice_id": f"race-{new_id()[:8]}",
        "site_user_id": "user-race",
        "product_id": 10,
        "months": 1,
    }
    results = []
    threads = [threading.Thread(target=lambda: results.append(try_deliver_for_payment(payment))) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    fresh = [r for r in results if r.get("fresh")]
    assert len(fresh) == 1, results
    with db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM deliveries WHERE payment_id = ?",
            (payment["invoice_id"],),
        ).fetchone()[0]
    assert count == 1


def test_enrich_newest_sub_gets_unlinked() -> None:
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    deliveries = [
        {
            "id": "d-old",
            "product_id": 10,
            "bot_sub_id": 5,
            "bot_sub_kind": "one_time",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": exp,
            "login": "old@test.com",
            "secret_enc": encrypt("p"),
            "payment_id": "inv-old",
        },
        {
            "id": "d-new",
            "product_id": 10,
            "bot_sub_id": None,
            "bot_sub_kind": None,
            "created_at": "2026-03-01T00:00:00Z",
            "expires_at": exp,
            "login": "new@test.com",
            "secret_enc": encrypt("p"),
            "payment_id": "inv-new",
        },
    ]

    def fake_list(_uid: str):
        return deliveries

    import backend.stock_svc as svc

    orig = svc.list_deliveries_for_user
    svc.list_deliveries_for_user = fake_list
    try:
        subs = {
            "oneTime": [
                {
                    "id": "one-5",
                    "botId": 5,
                    "productId": "55",
                    "kind": "one_time",
                    "status": "active",
                    "expiresAt": exp,
                    "startsAt": "2026-01-01T00:00:00Z",
                    "name": "Netflix old",
                },
                {
                    "id": "one-7",
                    "botId": 7,
                    "productId": "55",
                    "kind": "one_time",
                    "status": "active",
                    "expiresAt": exp,
                    "startsAt": "2026-03-01T00:00:00Z",
                    "name": "Netflix new",
                },
            ],
            "recurring": [],
        }
        enrich_subscriptions("u1", subs)
        assert subs["oneTime"][1]["login"] == "new@test.com"
        assert subs["oneTime"][0]["login"] == "old@test.com"
        used = set()
        assert _find_delivery_for_sub(subs["oneTime"][1], deliveries, used)["id"] == "d-new"
        used.add("d-new")
        assert _find_delivery_for_sub(subs["oneTime"][0], deliveries, used)["id"] == "d-old"
    finally:
        svc.list_deliveries_for_user = orig


def test_enrich_no_steal_linked() -> None:
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    deliveries = [
        {
            "id": "d-linked",
            "product_id": 10,
            "bot_sub_id": 5,
            "bot_sub_kind": "one_time",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": exp,
        },
    ]
    sub = {"productId": "55", "botId": 7, "kind": "one_time", "expiresAt": exp, "status": "active"}
    assert _find_delivery_for_sub(sub, deliveries, set()) is None


def test_gpt_available() -> None:
    free = ["a", "b", "", "", "", "", "KEY"]
    used = ["a", "b", "", "01.01.26", "123", "@nick", "KEY"]
    assert _gpt_available(free)
    assert not _gpt_available(used)


def test_orphan_delivery() -> None:
    exp = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    import backend.stock_svc as svc

    orig = svc.list_deliveries_for_user
    svc.list_deliveries_for_user = lambda _uid: [
        {
            "id": "orphan-1",
            "product_id": 10,
            "bot_sub_id": None,
            "created_at": now(),
            "expires_at": exp,
            "login": "orphan@test.com",
            "secret_enc": encrypt("p"),
            "payment_id": "inv-orphan",
            "sheet_meta": '{"service":"netflix","sheet":"Лист1","row":99}',
        }
    ]
    try:
        subs = {"oneTime": [], "recurring": []}
        append_orphan_deliveries("u1", subs)
        assert len(subs["oneTime"]) == 1
        assert subs["oneTime"][0]["login"] == "orphan@test.com"
        assert subs["oneTime"][0]["id"].startswith("del-")
    finally:
        svc.list_deliveries_for_user = orig


def main() -> None:
    tests = [
        test_netflix_availability,
        test_sheet_term_format,
        test_netflix_stock_alias,
        test_delivery_race,
        test_enrich_newest_sub_gets_unlinked,
        test_enrich_no_steal_linked,
        test_gpt_available,
        test_orphan_delivery,
    ]
    for fn in tests:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    main()
