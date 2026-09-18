import Link from "next/link";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { backendJson } from "@/lib/backend";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { Arrow, TgIcon } from "@/components/Logo";
import { SubCard } from "./SubCard";
import { PaymentHistory } from "./PaymentHistory";
import { SubPhoto } from "./SubPhoto";
import { VerifyBar } from "./VerifyBar";
import { LogoutButton } from "@/components/LogoutButton";
import { pageMetadata, SUPPORT_TG } from "@/lib/seo";
import type { BillingEntry, BotSubscription, SiteUser } from "@/lib/types";

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
  payments?: BillingEntry[];
  pending: { payment_id?: string; invoice_id?: string; status?: string; product_id?: number } | null;
};

function subBotId(id: string): number | null {
  const m = id.match(/^rec-(\d+)$/);
  return m ? Number(m[1]) : null;
}

function chargesForSub(payments: BillingEntry[], subId: string) {
  const botId = subBotId(subId);
  if (!botId) return [];
  return payments.filter((p) => p.kind === "charge" && p.subscriptionId === botId);
}

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
    // Архів лише коли строк дійсно минув — скасоване автосписання лишається активним до expiresAt
    if (!s.expiresAt) {
      const st = (s.status || "").toLowerCase();
      return Boolean(st && st !== "active");
    }
    const t = new Date(s.expiresAt).getTime();
    return Number.isFinite(t) && t < Date.now();
  };
  const past = all.filter(expired);
  const active = all.filter((s) => !expired(s));
  const billingOff = (s: BotSubscription) => {
    const st = (s.status || "").toLowerCase();
    return Boolean(st && st !== "active");
  };
  const hasVpn = active.some((s) => /vpn/i.test(s.name || "") || s.slug.includes("vpn"));
  const payments = data?.payments ?? [];
  const pending = data?.pending ?? null;
  const pendingOpen = pending && (pending.status === "pending" || pending.status === "PENDING");
  const pendingPaid = pending && ["success", "PAID"].includes(String(pending.status));

  return (
    <>
      <SiteHeader />
      <div className="wrap-narrow">
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
            <p>
              {active.some((s) => s.login || s.password)
                ? "Дані для входу вже в картці підписки нижче. Якщо потрібен код 2FA — натисни «Код 2FA»."
                : <>Менеджер <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer" style={{ color: "#A9C4FF", fontWeight: 800 }}>@kinomanage</a> надішле доступ у Telegram. Підписка вже в кабінеті.</>}
            </p>
          </div>
          {!active.some((s) => s.login || s.password) && (
            <a className="btn" href={SUPPORT_TG} target="_blank" rel="noopener noreferrer">Написати менеджеру<span className="dot"><Arrow /></span></a>
          )}
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
            <section className="subs-panel">
              <header className="subs-panel-head">
                <h2>Мої підписки</h2>
                {me.telegramName && <span>@{me.telegramName}</span>}
              </header>
              <div className="subs-panel-list">
                {active.map((s) => (
                  <SubCard key={s.id} sub={{
                    id: s.id,
                    name: s.name,
                    icon: s.icon,
                    color: s.color,
                    slug: s.slug,
                    productId: s.productId,
                    price: s.price,
                    months: s.months,
                    profileName: null,
                    pin: null,
                    login: s.login ?? null,
                    password: s.password ?? null,
                    hasTotp: Boolean(s.hasTotp),
                    startsAt: s.startsAt,
                    expiresAt: s.expiresAt,
                    source: s.source || "site",
                    recurring: s.kind === "recurring",
                    billingActive: s.kind === "recurring" && !billingOff(s),
                    nextPaymentAt: s.nextPaymentAt,
                    photoUrl: s.photoUrl,
                    maskedCard: s.maskedCard,
                    cardType: s.cardType,
                    charges: chargesForSub(payments, s.id),
                  }} />
                ))}
              </div>
              <p className="subs-panel-note">Коди підтвердження — кнопкою «ще», тут же</p>
            </section>
          )}

          {payments.length > 0 && (
            <div style={{ marginTop: active.length ? 28 : 0 }}>
              <PaymentHistory items={payments} />
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
            <section className="subs-panel subs-panel-arch" style={{ marginTop: active.length || payments.length ? 28 : 0 }}>
              <header className="subs-panel-head">
                <h2>Архів</h2>
                <span>{past.length}</span>
              </header>
              <div className="subs-panel-list">
                {past.map((s) => (
                  <article className="sub-row sub-row-arch" key={s.id}>
                    <div className="sub-row-main">
                      <SubPhoto
                        name={s.name}
                        icon={s.icon}
                        color={s.color}
                        photoUrl={s.photoUrl}
                        productId={s.productId}
                        size={28}
                        variant="row"
                      />
                      <div className="sub-row-body">
                        <div className="sub-row-top">
                          <div className="sub-row-text">
                            <h3>{s.name}</h3>
                            <p>
                              {s.expiresAt
                                ? `діяла до ${new Date(s.expiresAt).toLocaleDateString("uk-UA")}`
                                : "завершена"}
                              {s.price != null ? ` · ${s.price}₴` : ""}
                            </p>
                          </div>
                          <div className="sub-row-side">
                            <span className="sub-row-days off">архів</span>
                            {s.slug ? (
                              <Link className="sub-row-more" href={`/buy/${s.slug}`}>
                                знову
                              </Link>
                            ) : (
                              <Link className="sub-row-more" href="/catalog">
                                каталог
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <div className="logout-row">
        <LogoutButton />
      </div>

      <SiteFooter />
      </div>
    </>
  );
}
