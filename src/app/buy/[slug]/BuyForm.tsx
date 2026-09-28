"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { Plan } from "@/lib/plan-types";
import type { SiteUser } from "@/lib/types";
import { uah } from "@/lib/display";
import { Arrow } from "@/components/Logo";
import { SUPPORT_TG } from "@/lib/seo";

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
  const buyPath = `/buy/${slug}`;
  const loginHref = `/login?next=${encodeURIComponent(buyPath)}`;
  const regHref = `/login?mode=reg&next=${encodeURIComponent(buyPath)}`;

  useEffect(() => {
    fetch("/api/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  const chosen = options.find((o) => o.months === months);
  const canCheckout = user && !user.isGuest;
  const soldOut = free !== null && free <= 0;

  async function pay() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId, months }),
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
        {free !== null && free > 0 && free <= 3 && (
          <p className="buy-form-note buy-form-note-box">
            Лишилось {free} шт. за цією ціною
          </p>
        )}

        {deliveryNote && (
          <p className="buy-form-note buy-form-note-box">{deliveryNote}</p>
        )}

        <p className="buy-form-terms">
          Оплата карткою через Monobank.
          {recurring ? " Наступні списання — раз на місяць, тією ж карткою." : ""}
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
            <b>{uah(chosen.total)} ₴</b>
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
              {busy ? "Створюємо…" : user === undefined ? "Перевіряємо…" : "До оплати"}
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
