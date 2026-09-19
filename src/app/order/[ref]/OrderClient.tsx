"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Arrow } from "@/components/Logo";

type Delivery = {
  id: string;
  login: string;
  password: string;
  hasTotp: boolean;
  profileName?: string | null;
  pin?: string | null;
  expiresAt?: string | null;
};

type OrderPayload = {
  paymentId: string;
  invoiceId: string;
  status: string;
  amount: number;
  months: number;
  productName?: string;
  productSlug?: string;
  autoIssue: boolean;
  delivery: Delivery | null;
  supportUrl: string;
};

export function OrderClient({ orderRef }: { orderRef: string }) {
  const [data, setData] = useState<OrderPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [codeLeft, setCodeLeft] = useState(0);
  const [codeBusy, setCodeBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/order/${encodeURIComponent(orderRef)}`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error || "Не вдалось завантажити замовлення");
        return;
      }
      setData(json);
      setError(null);
    } catch {
      setError("Мережа не відповідає");
    }
  }, [orderRef]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!data) return;
    const paid = data.status === "success" || data.status === "paid";
    if (paid && (data.delivery || !data.autoIssue)) return;
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, [data, load]);

  useEffect(() => {
    if (!code || codeLeft <= 0) return;
    const t = setInterval(() => setCodeLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(t);
  }, [code, codeLeft]);

  async function fetchCode() {
    setCodeBusy(true);
    try {
      const res = await fetch(`/api/order/${encodeURIComponent(orderRef)}/code`, { method: "POST" });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error || "Не вдалось отримати код");
        return;
      }
      setCode(json.code);
      setCodeLeft(json.secondsLeft || 30);
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setCodeBusy(false);
    }
  }

  const paid = data && (data.status === "success" || data.status === "paid");
  const failed = data && (data.status === "failed" || data.status === "failure");

  return (
    <section className="order-page">
      <p className="crumbs">
        <Link href="/catalog">Каталог</Link>
        {" → "}Замовлення
      </p>

      <h1 className="h-sm" style={{ marginBottom: 10 }}>
        {failed ? <>Оплата<br /><em>не пройшла</em></> :
          paid ? <>Оплату<br /><em>отримано</em></> :
            <>Чекаємо<br /><em>оплату</em></>}
      </h1>

      {error && <p className="err" style={{ marginBottom: 16 }}>{error}</p>}

      {!data && !error && <p className="sec-sub">Завантажуємо статус…</p>}

      {data && (
        <div className="order-card">
          <div className="order-meta">
            <div>
              <small>Товар</small>
              <b>{data.productName || "Підписка"}</b>
            </div>
            <div>
              <small>Строк</small>
              <b>{data.months} міс.</b>
            </div>
            <div>
              <small>Сума</small>
              <b>{Number(data.amount).toFixed(0)} ₴</b>
            </div>
            <div>
              <small>Номер</small>
              <b className="order-ref">{data.paymentId}</b>
            </div>
          </div>

          {!paid && !failed && (
            <p className="order-hint">
              Якщо вже оплатив — зачекай кілька секунд, статус оновиться сам.
            </p>
          )}

          {failed && (
            <div className="order-actions">
              {data.productSlug && (
                <Link className="btn" href={`/buy/${data.productSlug}`}>
                  Спробувати знову<span className="dot"><Arrow /></span>
                </Link>
              )}
              <Link className="btn ghost" href="/catalog">До каталогу<span className="dot"><Arrow /></span></Link>
            </div>
          )}

          {paid && data.autoIssue && data.delivery && (
            <div className="order-access">
              <h2>Дані для входу</h2>
              <p className="order-hint">Збережи їх — доступ уже активний.</p>
              <div className="order-creds">
                {data.delivery.profileName && (
                  <div>
                    <small>Профіль</small>
                    <code>{data.delivery.profileName}</code>
                  </div>
                )}
                {data.delivery.pin && (
                  <div>
                    <small>PIN</small>
                    <code>{data.delivery.pin}</code>
                  </div>
                )}
                <div>
                  <small>Логін</small>
                  <code>{data.delivery.login}</code>
                </div>
                <div>
                  <small>Пароль</small>
                  <code>{data.delivery.password}</code>
                </div>
              </div>
              {data.delivery.hasTotp && (
                <div className="order-totp">
                  {code ? (
                    <p>Код 2FA: <b>{code}</b> {codeLeft > 0 && <span>({codeLeft} с)</span>}</p>
                  ) : (
                    <button className="btn sm" type="button" onClick={fetchCode} disabled={codeBusy}>
                      {codeBusy ? "…" : "Код 2FA"}
                    </button>
                  )}
                </div>
              )}
              <div className="order-actions">
                <Link className="btn" href="/cabinet">У кабінет<span className="dot"><Arrow /></span></Link>
                <Link className="btn ghost" href="/catalog">Ще підписки<span className="dot"><Arrow /></span></Link>
              </div>
            </div>
          )}

          {paid && data.autoIssue && !data.delivery && (
            <div className="order-access">
              <p className="order-hint">
                Оплату отримано. Готуємо доступ — логін і пароль зʼявляться тут автоматично за кілька секунд.
              </p>
              <div className="order-actions">
                <Link className="btn" href="/cabinet">У кабінет<span className="dot"><Arrow /></span></Link>
              </div>
            </div>
          )}

          {paid && !data.autoIssue && (
            <div className="order-access">
              <h2>Отримай доступ у Telegram</h2>
              <p className="order-hint">
                Натисни кнопку — відкриється чат з менеджером уже з номером замовлення.
                Він видасть доступ вручну.
              </p>
              <div className="order-actions">
                <a className="btn" href={data.supportUrl} target="_blank" rel="noopener noreferrer">
                  Написати @kinomanage<span className="dot"><Arrow /></span>
                </a>
                <Link className="btn ghost" href="/cabinet">Мій кабінет<span className="dot"><Arrow /></span></Link>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
