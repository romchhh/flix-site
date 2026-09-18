"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Plan } from "@/lib/plan-types";
import { uah } from "@/lib/display";
import { Arrow } from "@/components/Logo";

export function BuyForm({ productId, slug, options, loggedIn, free, recurring = false, deliveryNote = "" }:
  { productId: string; slug: string; options: Plan[]; loggedIn: boolean; free: number | null;
    recurring?: boolean; deliveryNote?: string }) {
  const [months, setMonths] = useState(options[0]?.months ?? 0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const chosen = options.find((o) => o.months === months);
  const soldOut = free !== null && free <= 0;

  async function pay() {
    if (!loggedIn) { router.push(`/login?next=/buy/${slug}`); return; }
    setBusy(true); setError(null);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ productId, months }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Не вдалось створити замовлення"); return; }
      if (!data.pageUrl) { setError("Немає посилання на оплату"); return; }
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
        <p className="muted">Цей товар поки не продається. Напиши в <a href="https://t.me/kinomanage" style={{ color: "var(--blue)", fontWeight: 800 }}>підтримку</a> — скажемо, коли зʼявиться.</p>
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 16 }}>
        {recurring ? "Помісячна підписка" : "Обери строк"}
      </h3>

      {recurring && (
        <p className="tip" style={{ marginTop: 0, marginBottom: 14 }}>
          Платиш за місяць, далі продовжується автоматично. Скасувати можна будь-коли в кабінеті.
        </p>
      )}

      {options.map((o) => (
        <button
          key={o.months}
          className={`plan${o.months === months ? " on" : ""}`}
          onClick={() => setMonths(o.months)}
          style={{ width: "100%", border: "2px solid transparent", textAlign: "left" }}
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

      <div style={{ marginTop: 16 }}>

      <div className="total">
        <span style={{ fontWeight: 700, color: "var(--muted)" }}>До сплати</span>
        <b>{uah(chosen.total)} ₴</b>
      </div>

      {soldOut ? (
        <>
          <button className="btn block" disabled>Зараз немає в наявності</button>
          <p className="tip" style={{ textAlign: "center" }}>
            Напиши в <a href="https://t.me/kinomanage">підтримку</a> — скажемо, коли зʼявиться.
          </p>
        </>
      ) : (
        <button className="btn block" onClick={pay} disabled={busy}>
          {busy ? "Створюємо рахунок…" : loggedIn ? "Перейти до оплати" : "Увійти та оплатити"}
          <span className="dot"><Arrow /></span>
        </button>
      )}

      {error && <p className="err">{error}</p>}

      {free !== null && free > 0 && free <= 3 && (
        <p className="tip" style={{ textAlign: "center" }}>
          Лишилось {free} шт. за цією ціною
        </p>
      )}

      {deliveryNote && <p className="tip" style={{ textAlign: "center" }}>{deliveryNote}</p>}

      <p className="terms">
        Оплата карткою через Monobank.
        {recurring ? " Наступні списання — раз на місяць, тією ж карткою." : ""}
      </p>
      </div>
    </div>
  );
}
