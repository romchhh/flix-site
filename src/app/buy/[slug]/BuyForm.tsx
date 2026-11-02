"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Plan } from "@/lib/plan-types";
import type { SiteUser } from "@/lib/types";
import { uah } from "@/lib/display";
import { Arrow } from "@/components/Logo";
import { SUPPORT_TG } from "@/lib/seo";

type AppliedPromo = {
  code: string;
  type: string;
  discountPercent?: number | null;
  freeMonths?: number | null;
  amount: number;
  amountSaved: number;
  months: number;
};

export function BuyForm({
  productId,
  slug,
  options,
  free,
  recurring = false,
  deliveryNote = "",
}: {
  productId: string;
  slug: string;
  options: Plan[];
  free: number | null;
  recurring?: boolean;
  deliveryNote?: string;
}) {
  const [months, setMonths] = useState(options[0]?.months ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [user, setUser] = useState<SiteUser | null | undefined>(undefined);
  const [promoInput, setPromoInput] = useState("");
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoError, setPromoError] = useState<string | null>(null);
  const [promo, setPromo] = useState<AppliedPromo | null>(null);
  const buyPath = `/buy/${slug}`;
  const loginHref = `/login?next=${encodeURIComponent(buyPath)}`;
  const regHref = `/login?mode=reg&next=${encodeURIComponent(buyPath)}`;

  useEffect(() => {
    fetch("/api/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    setPromo(null);
    setPromoError(null);
  }, [months]);

  const chosen = options.find((o) => o.months === months);
  const canCheckout = user && !user.isGuest;
  const soldOut = free !== null && free <= 0;

  const payTotal = useMemo(() => {
    if (!chosen) return 0;
    if (!promo) return chosen.total;
    return Math.max(0, Math.round(promo.amount * 100));
  }, [chosen, promo]);

  async function applyPromo() {
    const code = promoInput.trim();
    if (!code || !chosen) return;
    setPromoBusy(true);
    setPromoError(null);
    try {
      const res = await fetch("/api/promo/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          productId,
          months,
          amount: chosen.total / 100,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setPromo(null);
        setPromoError(data.message || data.error || "Невірний промокод");
        return;
      }
      const p = data.promo || {};
      const pricing = data.pricing || {};
      setPromo({
        code: p.code || code.toUpperCase(),
        type: p.type,
        discountPercent: p.discountPercent,
        freeMonths: p.freeMonths,
        amount: Number(pricing.amount ?? 0),
        amountSaved: Number(pricing.amountSaved ?? 0),
        months: Number(pricing.months ?? months),
      });
      if (p.type === "free" && p.freeMonths) {
        const match = options.find((o) => o.months === Number(p.freeMonths));
        if (match) setMonths(match.months);
      }
    } catch {
      setPromoError("Мережа не відповідає");
    } finally {
      setPromoBusy(false);
    }
  }

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productId,
          months: promo?.type === "free" ? promo.months : months,
          promoCode: promo?.code || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data.error ?? "Не вдалось створити замовлення";
        if (res.status === 401 || res.status === 403) {
          setError(msg);
          setUser((prev) => (prev && !prev.isGuest ? prev : null));
        } else {
          setError(msg);
        }
        return;
      }
      if (!data.pageUrl) {
        setError("Немає посилання на оплату");
        return;
      }
      window.location.href = data.pageUrl;
    } catch {
      setError("Мережа не відповідає. Спробуй ще раз.");
    } finally {
      setBusy(false);
    }
  }

  if (!chosen) {
    return (
      <div>
        <h3 style={{ fontSize: 18, fontWeight: 800, marginBottom: 10 }}>Ціни ще не виставлені</h3>
        <p className="muted">
          Цей товар поки не продається. Напиши{" "}
          <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer" style={{ color: "var(--blue)", fontWeight: 800 }}>
            менеджеру @kinomanage
          </a>{" "}
          — скажемо, коли зʼявиться.
        </p>
      </div>
    );
  }

  return (
    <div className="buy-form">
      <section className="buy-form-block buy-form-intro">
        <h3 className="buy-form-title">
          {recurring ? "Помісячна підписка" : "Обери строк"}
        </h3>
        {recurring && (
          <p className="buy-form-note">
            Платиш за місяць, далі продовжується автоматично. Скасувати можна будь-коли в кабінеті.
          </p>
        )}
      </section>

      <section className="buy-form-block buy-form-plans">
        {options.map((o) => (
          <button
            key={o.months}
            className={`plan${o.months === months ? " on" : ""}`}
            onClick={() => setMonths(o.months)}
            type="button"
          >
            <span className="rad" />
            <span className="pl">
              <b>{o.label}</b>
              <small>{uah(o.perMonth)} ₴ за місяць</small>
            </span>
            <span className="pr">
              <b>{uah(o.total)} ₴</b>
              {o.off > 0 && <small>−{o.off}%</small>}
            </span>
          </button>
        ))}
      </section>

      <section className="buy-form-block buy-form-meta">
        <div className="buy-promo">
          <label className="buy-form-note" htmlFor="promo-code">Промокод</label>
          <div className="buy-promo-row">
            <input
              id="promo-code"
              className="buy-promo-input"
              type="text"
              value={promoInput}
              onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void applyPromo();
                }
              }}
              placeholder="FLIX-XXXX-XXXX"
              autoComplete="off"
              disabled={promoBusy || busy}
            />
            <button
              type="button"
              className="btn buy-promo-btn"
              onClick={applyPromo}
              disabled={promoBusy || !promoInput.trim()}
            >
              {promoBusy ? "…" : promo ? "Ок" : "Застосувати"}
            </button>
            {promo && (
              <button
                type="button"
                className="buy-promo-clear"
                onClick={() => {
                  setPromo(null);
                  setPromoInput("");
                  setPromoError(null);
                }}
              >
                Скинути
              </button>
            )}
          </div>
          {promo && (
            <p className="buy-form-note buy-form-note-box">
              {promo.type === "free"
                ? `Промокод ${promo.code}: безкоштовно на ${promo.months} міс.`
                : `Промокод ${promo.code}: −${promo.discountPercent ?? 0}% (−${uah(Math.round(promo.amountSaved * 100))} ₴)${
                    recurring ? ". Знижка лише на першу оплату — далі повна ціна." : ""
                  }`}
            </p>
          )}
          {promoError && <p className="err buy-pay-err">{promoError}</p>}
        </div>

        {free !== null && free > 0 && free <= 3 && (
          <p className="buy-form-note buy-form-note-box">
            Лишилось {free} шт. за цією ціною
          </p>
        )}

        {deliveryNote && (
          <p className="buy-form-note buy-form-note-box">{deliveryNote}</p>
        )}

        <p className="buy-form-terms">
          {promo?.type === "free"
            ? "Безкоштовна активація за промокодом — без оплати карткою."
            : `Оплата карткою через Monobank.${
                recurring
                  ? promo
                    ? " Наступні списання — раз на місяць за повною ціною тарифу, тією ж карткою."
                    : " Наступні списання — раз на місяць, тією ж карткою."
                  : ""
              }`}
        </p>
        {user !== undefined && !canCheckout && (
          <p className="buy-form-note buy-form-note-box">
            {user?.isGuest
              ? "Щоб оплатити, створи акаунт або увійди — тоді підписка зʼявиться в кабінеті навіть після очищення кукі."
              : "Спочатку увійди або зареєструйся — без цього замовлення не оформити."}
            {" "}
            <Link href={loginHref} style={{ fontWeight: 800 }}>Увійти</Link>
            {" · "}
            <Link href={regHref} style={{ fontWeight: 800 }}>Реєстрація</Link>
          </p>
        )}
      </section>

      <div className="buy-pay-wrap">
        <div className="buy-pay-inner">
          <div className="buy-pay-total">
            <span>До сплати</span>
            <b>
              {uah(payTotal)} ₴
              {promo && payTotal < chosen.total && (
                <small style={{ display: "block", fontWeight: 600, opacity: 0.7, textDecoration: "line-through" }}>
                  {uah(chosen.total)} ₴
                </small>
              )}
            </b>
          </div>
          {soldOut ? (
            <button className="btn buy-pay-btn" type="button" disabled>Немає в наявності</button>
          ) : !canCheckout && user !== undefined ? (
            <Link className="btn buy-pay-btn" href={regHref}>
              Увійти / реєстрація
              <span className="dot"><Arrow /></span>
            </Link>
          ) : (
            <button className="btn buy-pay-btn" type="button" onClick={pay} disabled={busy || user === undefined}>
              {busy
                ? "Створюємо…"
                : user === undefined
                  ? "Перевіряємо…"
                  : promo?.type === "free" || payTotal === 0
                    ? "Активувати"
                    : "До оплати"}
              <span className="dot"><Arrow /></span>
            </button>
          )}
        </div>
        {error && <p className="err buy-pay-err">{error}</p>}
        {soldOut && (
          <p className="tip buy-pay-err">
            Напиши <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">менеджеру @kinomanage</a>.
          </p>
        )}
      </div>
    </div>
  );
}
