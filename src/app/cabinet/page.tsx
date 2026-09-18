import Link from "next/link";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { backendJson } from "@/lib/backend";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { Arrow, TgIcon } from "@/components/Logo";
import { SubCard } from "./SubCard";
import { VerifyBar } from "./VerifyBar";
import { LogoutButton } from "@/components/LogoutButton";
import { pageMetadata } from "@/lib/seo";
import type { BotSubscription, SiteUser } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: "Мій кабінет",
  description: "Твої підписки, строки та автосписання в flixмаркет.",
  path: "/cabinet",
  noIndex: true,
});

type CabinetData = {
  user: SiteUser;
  bot: { userId?: number; username?: string | null; joinDate?: string | null; source?: string | null } | null;
  subscriptions: { oneTime: BotSubscription[]; recurring: BotSubscription[] };
  pending: { payment_id?: string; invoice_id?: string; status?: string; product_id?: number } | null;
};

export default async function Cabinet({ searchParams }:
  { searchParams: Promise<{ order?: string; verified?: string }> }) {
  const me = await currentUser();
  if (!me) redirect("/login");

  const { order, verified } = await searchParams;
  const data = await backendJson<CabinetData>(`/api/cabinet${order ? `?order=${encodeURIComponent(order)}` : ""}`);
  const oneTime = data?.subscriptions.oneTime ?? [];
  const recurring = data?.subscriptions.recurring ?? [];
  const all = [...recurring, ...oneTime];
  const expired = (s: BotSubscription) => {
    const st = (s.status || "").toLowerCase();
    if (st && st !== "active") return true;
    if (!s.expiresAt) return false;
    const t = new Date(s.expiresAt).getTime();
    return Number.isFinite(t) && t < Date.now();
  };
  const past = all.filter(expired);
  const active = all.filter((s) => !expired(s));
  const hasVpn = active.some((s) => /vpn/i.test(s.name || "") || s.slug.includes("vpn"));
  const pending = data?.pending ?? null;
  const pendingOpen = pending && (pending.status === "pending" || pending.status === "PENDING");
  const pendingPaid = pending && ["success", "PAID"].includes(String(pending.status));

  return (
    <div className="wrap-narrow">
      <SiteHeader />

      <h1 className="h-sm" style={{ margin: "28px 0 22px" }}>Мої<br /><em>підписки</em></h1>

      {me.telegramId && (
        <div className="cab-user">
          {me.telegramPhoto ? (
            <img className="av av-img" src={me.telegramPhoto} alt="" />
          ) : (
            <span className="av">{(me.telegramName || "TG").slice(0, 2).toUpperCase()}</span>
          )}
          <div>
            <b>{me.telegramName ? `@${me.telegramName}` : `Telegram ${me.telegramId}`}</b>
            <small>
              {all.length
                ? `${active.length} активн${active.length === 1 ? "а" : "их"} · ${past.length} в архіві`
                : data?.bot
                  ? "Telegram збігся з ботом — покупок поки немає"
                  : "Telegram привʼязано. Якщо купував у боті, натисни «Увійти через Telegram» ще раз — підписки підтягнуться."}
            </small>
          </div>
        </div>
      )}

      {verified && (
        <div className="import" style={{ background: "#E3F6EB", color: "#14733A" }}>
          <div className="grow">
            <b>Пошту підтверджено</b>
            <p style={{ color: "#2C7A4E" }}>Тепер акаунт повністю твій.</p>
          </div>
        </div>
      )}

      {me.email && !me.emailVerified && <VerifyBar email={me.email} />}

      {pendingOpen && (
        <div className="import">
          <div className="grow">
            <b>Чекаємо оплату</b>
            <p>Щойно гроші дійдуть, підписка зʼявиться тут. Обробка відбувається в боті.</p>
          </div>
        </div>
      )}

      {pendingPaid && (
        <div className="import">
          <div className="grow">
            <b>Оплату отримано</b>
            <p>Менеджер надішле доступ у Telegram. Підписка вже в кабінеті.</p>
          </div>
          <a className="btn" href="https://t.me/FlixMarketBot">Написати<span className="dot"><Arrow /></span></a>
        </div>
      )}

      {!me.telegramId && (
        <div className="import">
          <div className="grow">
            <b>Купував у боті?</b>
            <p>Привʼяжи Telegram — підписки з бота зʼявляться тут разом зі строками й автосписанням.</p>
          </div>
          <Link className="btn" href="/link">Привʼязати<span className="dot"><Arrow /></span></Link>
        </div>
      )}

      {all.length === 0 ? (
        <div className="empty">
          <h3>Тут поки порожньо</h3>
          <p>
            {me.telegramId
              ? "Обери підписку в каталозі — після оплати вона зʼявиться тут. Якщо в боті вже є покупки, увійди через Telegram ще раз, щоб синхронізувати."
              : "Обери підписку в каталозі — після оплати вона зʼявиться тут. Якщо купував у боті, увійди через Telegram."}
          </p>
          <Link className="btn" href="/catalog">До каталогу<span className="dot"><Arrow /></span></Link>
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <div className="list">
              {active.map((s) => (
                <SubCard key={s.id} sub={{
                  id: s.id,
                  name: s.name,
                  icon: s.icon,
                  color: s.color,
                  slug: s.slug,
                  profileName: s.kind === "recurring" ? "автосписання" : null,
                  pin: null,
                  login: null,
                  hasTotp: false,
                  startsAt: s.startsAt,
                  expiresAt: s.expiresAt,
                  source: s.source || "site",
                  recurring: s.kind === "recurring" && s.status === "active",
                  nextPaymentAt: s.nextPaymentAt,
                }} />
              ))}
            </div>
          )}

          {!hasVpn && (
            <div className="vpn dark">
              <span className="v">V</span>
              <div className="txt">
                <b>У тебе ще немає FlixVPN</b>
                <small>Він потрібен, щоб підписки відкривались без сюрпризів.</small>
              </div>
              <a href="https://t.me/FlixVPNBot"><TgIcon /> Бот VPN</a>
            </div>
          )}

          {past.length > 0 && (
            <>
              <h2 style={{ fontSize: 22, margin: active.length ? "36px 0 14px" : "8px 0 14px" }}>Архів</h2>
              <div className="list">
                {past.map((s) => (
                  <div className="sub" key={s.id} style={{ opacity: .75 }}>
                    <div className="sub-top">
                      <div className="ttl">
                        <h3>{s.name}</h3>
                        <p>
                          {s.expiresAt
                            ? `діяла до ${new Date(s.expiresAt).toLocaleDateString("uk-UA")}`
                            : "завершена"}
                          {s.price != null ? ` · ${s.price}₴` : ""}
                        </p>
                      </div>
                      <span className="badge b-off">архів</span>
                    </div>
                    <div className="acts">
                      {s.slug ? (
                        <Link className="btn sm" href={`/buy/${s.slug}`}>
                          Купити знову<span className="dot"><Arrow /></span>
                        </Link>
                      ) : (
                        <Link className="btn sm" href="/catalog">
                          До каталогу<span className="dot"><Arrow /></span>
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      <div className="logout-row">
        <LogoutButton />
      </div>

      <SiteFooter />
    </div>
  );
}
