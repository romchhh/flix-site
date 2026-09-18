import Link from "next/link";
import { Logo } from "./Logo";
import { LogoutButton } from "./LogoutButton";
import { currentUser } from "@/lib/session";

export async function SiteHeader() {
  const me = await currentUser();
  const label = me?.telegramName ? `@${me.telegramName}` : me?.email ?? "";
  const short = label.length > 22 ? label.slice(0, 20) + "…" : label;
  const initials = (label.replace("@", "").slice(0, 2) || "??").toUpperCase();

  return (
    <header className="site-header">
      <div className="bar">
        <Logo size={25} />
        <div className="top-links">
          <Link href="/catalog">Каталог</Link>
          <Link className="secondary" href="/#how">Як це працює</Link>
          <Link className="secondary" href="/#reviews">Відгуки</Link>
          {me?.isAdmin && <Link href="/admin">Адмінка</Link>}
          {me ? (
            <span className="me-wrap">
              <Link className="me" href="/cabinet">
                {me.telegramPhoto ? (
                  <img className="av av-img" src={me.telegramPhoto} alt="" />
                ) : (
                  <span className="av">{initials}</span>
                )}
                <span className="me-label">{short}</span>
              </Link>
              <LogoutButton compact />
            </span>
          ) : (
            <Link className="enter" href="/login">Увійти</Link>
          )}
        </div>
      </div>
    </header>
  );
}

export function SiteFooter() {
  const links = [
    { label: "Підтримка", href: "https://t.me/kinomanage", note: "@kinomanage" },
    { label: "Telegram-бот", href: "https://t.me/FlixMarketBot" },
    { label: "Наш VPN", href: "https://t.me/FlixVPNBot" },
    { label: "Кабінет", href: "/cabinet" },
    { label: "Публічна оферта", href: "/offer" },
    { label: "Політика конфіденційності", href: "/privacy" },
  ];

  return (
    <footer className="ft">
      <nav className="ft-row">
        {links.map((l) => (
          <Link className="ft-btn" key={l.href} href={l.href}>
            {l.label}
            {l.note && <span className="ft-note">{l.note}</span>}
          </Link>
        ))}
      </nav>
      <p className="ft-copy">flixмаркет — {new Date().getFullYear()}</p>
    </footer>
  );
}
