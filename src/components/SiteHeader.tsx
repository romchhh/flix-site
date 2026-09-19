import { Suspense } from "react";
import { Logo } from "./Logo";
import { PageBack } from "./PageBack";
import { SiteNav } from "./SiteNav";
import { currentUser } from "@/lib/session";
import { SUPPORT_TG } from "@/lib/seo";
import Link from "next/link";

export async function SiteHeader() {
  const me = await currentUser();

  return (
    <header className="site-header">
      <div className="header-shell">
        <div className="bar">
          <div className="bar-start">
            <Suspense fallback={null}>
              <PageBack className="page-back-in-header" />
            </Suspense>
            <Logo size={25} />
          </div>
          <SiteNav user={me} />
        </div>
      </div>
      <Suspense fallback={null}>
        <PageBack className="page-back-float" />
      </Suspense>
    </header>
  );
}

export function SiteFooter() {
  const links = [
    { label: "Каталог", href: "/catalog" },
    { label: "Менеджер", href: SUPPORT_TG, note: "@kinomanage", external: true },
    { label: "Telegram-бот", href: "https://t.me/FlixMarketBot", external: true },
    { label: "Наш VPN", href: "https://t.me/FlixVPNBot", external: true },
    { label: "Кабінет", href: "/cabinet" },
    { label: "Публічна оферта", href: "/offer" },
    { label: "Політика конфіденційності", href: "/privacy" },
  ];

  return (
    <footer className="ft">
      <nav className="ft-row" aria-label="Підвал сайту">
        {links.map((l) => (
          <Link
            className="ft-btn"
            key={l.href}
            href={l.href}
            {...(l.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            {l.label}
            {l.note && <span className="ft-note">{l.note}</span>}
          </Link>
        ))}
      </nav>
      <p className="ft-copy">flixмаркет — {new Date().getFullYear()}</p>
    </footer>
  );
}
