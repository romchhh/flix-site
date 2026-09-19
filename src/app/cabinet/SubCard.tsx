"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PaymentHistory } from "./PaymentHistory";
import { Arrow, Chevron } from "@/components/Logo";
import {
  dateUk, dateTimeUk, daysLeft, progress, plural,
  formatCard, productPhotoUrl,
} from "@/lib/display";
import { SUPPORT_TG } from "@/lib/seo";
import type { BillingEntry } from "@/lib/types";
import { ServiceIcon } from "@/components/ServiceIcon";

type Sub = {
  id: string;
  name: string;
  icon: string;
  color: string;
  slug: string;
  productId?: string;
  price?: number;
  months?: number;
  profileName: string | null;
  pin: string | null;
  login: string | null;
  password: string | null;
  hasTotp: boolean;
  startsAt: string;
  expiresAt: string;
  source?: string;
  recurring?: boolean;
  billingActive?: boolean;
  nextPaymentAt?: string;
  photoUrl?: string | null;
  maskedCard?: string | null;
  cardType?: string | null;
  charges?: BillingEntry[];
  autoIssue?: boolean;
};

function SubThumb({ name, icon, color, photoUrl, productId }: {
  name: string; icon: string; color: string;
  photoUrl?: string | null; productId?: string;
}) {
  const [failed, setFailed] = useState(false);
  const src = productPhotoUrl(photoUrl, productId);
  const show = Boolean(src) && !failed;

  if (show) {
    return <img className="sub-row-thumb" src={src!} alt="" onError={() => setFailed(true)} />;
  }
  return (
    <div
      className="sub-row-thumb sub-row-thumb-fallback"
      style={{ background: `linear-gradient(145deg, ${color}28 0%, ${color}50 100%)` }}
    >
      <ServiceIcon slug={icon} color={color} letter={name.charAt(0)} size={28} />
    </div>
  );
}

export function SubCard({ sub }: { sub: Sub }) {
  const [open, setOpen] = useState(false);
  const [openHistory, setOpenHistory] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [codeLeft, setCodeLeft] = useState(0);
  const [codeBusy, setCodeBusy] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!code || codeLeft <= 0) return;
    const timer = setInterval(() => setCodeLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(timer);
  }, [code, codeLeft]);

  const exp = new Date(sub.expiresAt);
  const left = daysLeft(exp);
  const remainingPct = progress(new Date(sub.startsAt), exp);
  const soon = left <= 7;
  const critical = left <= 3;
  const trackTone = critical ? "crit" : soon ? "warn" : "";
  const cardLabel = formatCard(sub.maskedCard, sub.cardType);
  const nextPay = sub.nextPaymentAt ? new Date(sub.nextPaymentAt) : null;
  const charges = sub.charges ?? [];
  const billingOn = Boolean(sub.recurring && sub.billingActive !== false);

  const subtitle = sub.profileName
    || (sub.login || sub.password ? "Доступ у кабінеті" : null)
    || (sub.recurring ? (billingOn ? "Автосписання" : "Без автосписання") : null)
    || "Підписка";

  const daysLabel = left > 0
    ? `${left} ${plural(left, "день", "дні", "днів")}`
    : "сьогодні";

  async function fetchCode() {
    setCodeBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/subs/${sub.id}/code`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Не вдалось отримати код");
        return;
      }
      setCode(data.code);
      setCodeLeft(data.secondsLeft ?? 30);
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setCodeBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/subs/${sub.id}/cancel`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Не вдалось скасувати");
        return;
      }
      setConfirmCancel(false);
      router.refresh();
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <article className={`sub-row${open ? " is-open" : ""}${soon ? " is-soon" : ""}`}>
        <div className="sub-row-main">
          <SubThumb
            name={sub.name}
            icon={sub.icon}
            color={sub.color}
            photoUrl={sub.photoUrl}
            productId={sub.productId}
          />

          <div className="sub-row-body">
            <div className="sub-row-top">
              <div className="sub-row-text">
                <h3>
                  {sub.slug ? (
                    <Link href={`/buy/${sub.slug}`} className="sub-title-link">{sub.name}</Link>
                  ) : sub.name}
                </h3>
                <p>{subtitle}</p>
              </div>
              <div className="sub-row-side">
                <span className={`sub-row-days${soon ? " warn" : ""}`}>{daysLabel}</span>
                <button
                  type="button"
                  className="sub-row-more"
                  aria-expanded={open}
                  onClick={() => setOpen((v) => !v)}
                >
                  {open ? "згорнути" : "ще"}
                  <span className={`chev${open ? " open" : ""}`}><Chevron /></span>
                </button>
              </div>
            </div>
            <div className="sub-row-track" title={`Лишилось ${daysLabel}`}>
              <i className={trackTone} style={{ width: `${remainingPct}%` }} />
            </div>
          </div>
        </div>

        {open && (
          <div className="sub-row-extra">
            <div className="sub-row-meta">
              <div>
                <small>Доступ до</small>
                <b>{dateUk(exp)}</b>
              </div>
              {sub.price != null && (
                <div>
                  <small>Ціна</small>
                  <b>{sub.price}₴{sub.recurring && sub.months ? ` / ${sub.months} міс` : ""}</b>
                </div>
              )}
              {sub.recurring && (
                <div>
                  <small>Картка</small>
                  <b>{cardLabel || "не привʼязана"}</b>
                </div>
              )}
              {sub.recurring && billingOn && nextPay && (
                <div>
                  <small>Наступне списання</small>
                  <b>{dateTimeUk(nextPay)}</b>
                </div>
              )}
            </div>

            {(sub.login || sub.password || sub.profileName || sub.pin) && (
              <div className="creds">
                {sub.profileName && <div className="row"><span>Профіль</span><b>{sub.profileName}</b></div>}
                {sub.pin && <div className="row"><span>PIN</span><b>{sub.pin}</b></div>}
                {sub.login && <div className="row"><span>Логін</span><b>{sub.login}</b></div>}
                {sub.password && <div className="row"><span>Пароль</span><b>{sub.password}</b></div>}
              </div>
            )}

            {code && (
              <div className="code-box">
                <b>{code}</b>
                <small>{codeLeft} с</small>
              </div>
            )}

            {error && (
              <div className="sub-alert" role="alert">
                <b>Не вдалось</b>
                <p>{error}</p>
              </div>
            )}

            {sub.recurring && charges.length > 0 && (
              <div className="sub-history-wrap">
                <button type="button" className="sub-history-toggle" onClick={() => setOpenHistory(!openHistory)}>
                  Історія списань ({charges.length})
                  <span className={`chev${openHistory ? " open" : ""}`}><Chevron /></span>
                </button>
                {openHistory && <PaymentHistory items={charges} title="" limit={20} compact />}
              </div>
            )}

            <div className="sub-row-acts">
              {sub.hasTotp && (
                <button className="btn sm soft" type="button" onClick={fetchCode} disabled={codeBusy}>
                  {codeBusy ? "Код…" : "Код 2FA"}
                </button>
              )}
              {billingOn && (
                <button
                  className="btn sm soft"
                  type="button"
                  onClick={() => { setError(null); setConfirmCancel(true); }}
                  disabled={busy}
                >
                  Вимкнути авто
                </button>
              )}
              {soon && sub.slug && (
                <Link className="btn sm" href={`/buy/${sub.slug}`}>
                  Продовжити<span className="dot"><Arrow /></span>
                </Link>
              )}
              <a className="btn sm soft" href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">
                Менеджер
              </a>
            </div>

            <p className="tip">
              {(sub.login || sub.password)
                ? "Не передавай дані третім особам. Якщо сервіс просить код — натисни «Код 2FA»."
                : sub.autoIssue
                  ? "Доступ зʼявиться тут одразу після автовидачі. Якщо довго немає даних — напиши в підтримку."
                  : <>Доступ після оплати надсилає <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">менеджер @kinomanage</a>.</>}
              {" "}Пише «сервіс недоступний у вашому регіоні»? Вмикай{" "}
              <a href="https://t.me/FlixVPNBot">FlixVPN</a>.
            </p>
          </div>
        )}
      </article>

      <ConfirmDialog
        open={confirmCancel}
        title="Вимкнути автосписання?"
        message="Доступ збережеться до кінця оплаченого періоду. Після цього підписку доведеться оформити знову."
        confirmLabel="Так, вимкнути"
        cancelLabel="Залишити"
        danger
        busy={busy}
        onConfirm={cancel}
        onCancel={() => { if (!busy) setConfirmCancel(false); }}
      />
    </>
  );
}
