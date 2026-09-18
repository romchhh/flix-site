"use client";
import { useState } from "react";
import type { Plan } from "@/lib/plan-types";
import { uah } from "@/lib/display";
import { Arrow } from "@/components/Logo";
import { SUPPORT_TG } from "@/lib/seo";

export function BuyForm({
  productId,
  options,
  loggedIn,
  free,
  recurring = false,
  deliveryNote = "",
  autoIssue = false,
}: {
  productId: string;
  slug: string;
  options: Plan[];
  loggedIn: boolean;
  free: number | null;
  recurring?: boolean;
  deliveryNote?: string;
  autoIssue?: boolean;
}) {
  const [months, setMonths] = useState(options[0]?.months ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const chosen = options.find((o) => o.months === months);
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
        setError(data.error ?? "Не вдалось створити замовлення");
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
          {!loggedIn && autoIssue
            ? " Після оплати доступ зʼявиться одразу на цій вкладці."
            : !loggedIn
              ? " Після оплати напиши менеджеру — він видасть доступ."
              : ""}
        </p>
      </section>

      <div className="buy-pay-wrap">
        <div className="buy-pay-inner">
          <div className="buy-pay-total">
            <span>До сплати</span>
            <b>{uah(chosen.total)} ₴</b>
          </div>
          {soldOut ? (
            <button className="btn buy-pay-btn" type="button" disabled>Немає в наявності</button>
          ) : (
            <button className="btn buy-pay-btn" type="button" onClick={pay} disabled={busy}>
              {busy ? "Створюємо…" : "До оплати"}
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
