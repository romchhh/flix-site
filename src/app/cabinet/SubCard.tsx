"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ServiceIcon } from "@/components/ServiceIcon";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Arrow, Chevron } from "@/components/Logo";
import {
  dateUk, dateTimeUk, daysLeft, progress, plural,
  productPhotoUrl, formatCard,
} from "@/lib/display";
import { SUPPORT_TG } from "@/lib/seo";

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  bot: { label: "бот", cls: "b-bot" },
  site: { label: "сайт", cls: "b-site" },
  miniapp: { label: "мінідодаток", cls: "b-mini" },
};

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
  hasTotp: boolean;
  startsAt: string;
  expiresAt: string;
  source?: string;
  recurring?: boolean;
  nextPaymentAt?: string;
  photoUrl?: string | null;
  maskedCard?: string | null;
  cardType?: string | null;
};

export function SubCard({ sub }: { sub: Sub }) {
  const [openCreds, setOpenCreds] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const exp = new Date(sub.expiresAt);
  const left = daysLeft(exp);
  const pct = progress(new Date(sub.startsAt), exp);
  const soon = left <= 7;
  const src = SOURCE_BADGE[sub.source || "bot"] || SOURCE_BADGE.bot;
  const photoSrc = productPhotoUrl(sub.photoUrl, sub.productId);
  const showPhoto = Boolean(photoSrc) && !imgFailed;
  const cardLabel = formatCard(sub.maskedCard, sub.cardType);
  const nextPay = sub.nextPaymentAt ? new Date(sub.nextPaymentAt) : null;

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
      <div className="sub sub-v2">
        <div className="sub-head">
          <div className="sub-visual">
            {showPhoto ? (
              <img
                className="sub-photo"
                src={photoSrc!}
                alt=""
                onError={() => setImgFailed(true)}
              />
            ) : (
              <span className="sub-fallback">
                <ServiceIcon slug={sub.icon} color={sub.color} letter={sub.name.charAt(0)} size={44} />
              </span>
            )}
          </div>

          <div className="sub-main">
            <div className="sub-title-row">
              <div>
                <h3>{sub.name}</h3>
                <p className="sub-price-line">
                  {sub.price != null ? `${sub.price}₴` : ""}
                  {sub.recurring && sub.months ? ` · кожні ${sub.months} міс` : ""}
                </p>
              </div>
              <div className="sub-badges">
                <span className={`badge ${src.cls}`}>{src.label}</span>
                <span className={`badge ${soon ? "b-soon" : "b-ok"}`}>
                  {soon ? `${left} ${plural(left, "день", "дні", "днів")}` : "активна"}
                </span>
              </div>
            </div>

            <div className="sub-facts">
              {sub.recurring && nextPay && (
                <div className="sub-fact">
                  <small>Наступне списання</small>
                  <b>{dateTimeUk(nextPay)}</b>
                </div>
              )}
              {sub.recurring && (
                <div className="sub-fact">
                  <small>Привʼязана картка</small>
                  <b>{cardLabel || "не привʼязана"}</b>
                </div>
              )}
              <div className="sub-fact">
                <small>Доступ до</small>
                <b>{dateUk(exp)}</b>
              </div>
              <div className="sub-fact">
                <small>Залишилось</small>
                <b>
                  {left > 0
                    ? `${left} ${plural(left, "день", "дні", "днів")}`
                    : "спливає сьогодні"}
                </b>
              </div>
            </div>
          </div>
        </div>

        <div className="track"><i className={soon ? "warn" : ""} style={{ width: `${pct}%` }} /></div>

        <div className="acts">
          <a className="btn sm soft" href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">
            Менеджер
          </a>
          {sub.login && (
            <button className="btn sm soft" type="button" onClick={() => setOpenCreds(!openCreds)}>
              Дані для входу<span className="dot"><Chevron /></span>
            </button>
          )}
          {sub.recurring && (
            <button
              className="btn sm soft"
              type="button"
              onClick={() => { setError(null); setConfirmCancel(true); }}
              disabled={busy}
            >
              Вимкнути автосписання
            </button>
          )}
          {soon && sub.slug && (
            <Link className="btn sm" href={`/buy/${sub.slug}`}>
              Продовжити<span className="dot"><Arrow /></span>
            </Link>
          )}
        </div>

        {error && (
          <div className="sub-alert" role="alert">
            <b>Не вдалось</b>
            <p>{error}</p>
          </div>
        )}

        {openCreds && (
          <div className="creds">
            {sub.login && <div className="row"><span>Логін</span><b>{sub.login}</b></div>}
            <p className="tip">
              Доступ після оплати надсилає{" "}
              <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">менеджер @kinomanage</a>.
              Пише «сервіс недоступний у вашому регіоні»? Вмикай{" "}
              <a href="https://t.me/FlixVPNBot">FlixVPN</a>.
            </p>
          </div>
        )}
      </div>

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
