"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ServiceIcon } from "@/components/ServiceIcon";
import { Arrow, Chevron } from "@/components/Logo";
import { dateUk, daysLeft, progress, plural } from "@/lib/display";

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  bot: { label: "бот", cls: "b-bot" },
  site: { label: "сайт", cls: "b-site" },
  miniapp: { label: "мінідодаток", cls: "b-mini" },
};

type Sub = {
  id: string; name: string; icon: string; color: string; slug: string;
  profileName: string | null; pin: string | null; login: string | null;
  hasTotp: boolean; startsAt: string; expiresAt: string; source?: string;
  recurring?: boolean; nextPaymentAt?: string;
};

export function SubCard({ sub }: { sub: Sub }) {
  const [openCreds, setOpenCreds] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const exp = new Date(sub.expiresAt);
  const left = daysLeft(exp);
  const pct = progress(new Date(sub.startsAt), exp);
  const soon = left <= 7;
  const src = SOURCE_BADGE[sub.source || "bot"] || SOURCE_BADGE.bot;

  async function cancel() {
    if (!confirm("Скасувати автосписання? Доступ збережеться до кінця оплаченого періоду.")) return;
    setBusy(true); setError(null);
    try {
      const res = await fetch(`/api/subs/${sub.id}/cancel`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Не вдалось скасувати"); return; }
      router.refresh();
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sub">
      <div className="sub-top">
        <span className="mark">
          <ServiceIcon slug={sub.icon} color={sub.color} letter={sub.name.charAt(0)} size={42} />
        </span>
        <div className="ttl">
          <h3>{sub.name}</h3>
          {sub.recurring && sub.nextPaymentAt && (
            <p>наступне списання {dateUk(new Date(sub.nextPaymentAt))}</p>
          )}
          {!sub.recurring && (sub.profileName || sub.pin) && (
            <p>{sub.profileName}{sub.pin ? ` · PIN ${sub.pin}` : ""}</p>
          )}
        </div>
        <span className={`badge ${src.cls}`}>{src.label}</span>
        <span className={`badge ${soon ? "b-soon" : "b-ok"}`}>
          {soon ? `${left} ${plural(left, "день", "дні", "днів")}` : "активна"}
        </span>
      </div>

      <div className="track"><i className={soon ? "warn" : ""} style={{ width: `${pct}%` }} /></div>
      <div className="meta">
        <span>до {dateUk(exp)}</span>
        <span>{left > 0 ? `${left} ${plural(left, "день", "дні", "днів")} лишилось` : "спливає сьогодні"}</span>
      </div>

      <div className="acts">
        {sub.login && (
          <button className="btn sm soft" onClick={() => setOpenCreds(!openCreds)}>
            Дані для входу<span className="dot"><Chevron /></span>
          </button>
        )}
        {sub.recurring && (
          <button className="btn sm soft" onClick={cancel} disabled={busy}>
            {busy ? "Скасовуємо…" : "Вимкнути автосписання"}
          </button>
        )}
        {soon && sub.slug && (
          <Link className="btn sm" href={`/buy/${sub.slug}`}>
            Продовжити<span className="dot"><Arrow /></span>
          </Link>
        )}
      </div>

      {error && <p className="err">{error}</p>}

      {openCreds && (
        <div className="creds">
          {sub.login && <div className="row"><span>Логін</span><b>{sub.login}</b></div>}
          <p className="tip">
            Доступ після оплати надсилає менеджер у Telegram.
            Пише «сервіс недоступний у вашому регіоні»? Вмикай{" "}
            <a href="https://t.me/FlixVPNBot">FlixVPN</a>.
          </p>
        </div>
      )}
    </div>
  );
}
