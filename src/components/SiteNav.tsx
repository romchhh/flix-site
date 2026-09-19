"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SUPPORT_TG } from "@/lib/seo";

type UserChip = {
  telegramPhoto?: string | null;
  telegramName?: string | null;
  email?: string | null;
  isAdmin?: boolean;
  isGuest?: boolean;
};

function navClass(pathname: string, href: string, base = "top-nav-link") {
  const active = href === "/catalog"
    ? pathname.startsWith("/catalog") || pathname.startsWith("/buy/")
    : href === "/cabinet"
      ? pathname.startsWith("/cabinet") || pathname.startsWith("/order/")
      : href === "/admin"
        ? pathname.startsWith("/admin")
        : pathname === href || (href.startsWith("/#") && false);
  return `${base}${active ? " active" : ""}`;
}

export function SiteNav({ user }: { user?: UserChip | null }) {
  const pathname = usePathname() || "/";
  const label = user?.telegramName
    ? `@${user.telegramName}`
    : user?.email
      ? user.email
      : user?.isGuest
        ? "Гість"
        : "";
  const short = label.length > 22 ? label.slice(0, 20) + "…" : label;
  const initials = (label.replace("@", "").slice(0, 2) || (user?.isGuest ? "ГС" : "??")).toUpperCase();

  return (
    <nav className="top-nav" aria-label="Головна навігація">
      <div className="top-nav-links">
        <Link className={navClass(pathname, "/catalog")} href="/catalog">Каталог</Link>
        <Link className={`${navClass(pathname, "/#how")} secondary`} href="/#how">Як це працює</Link>
        <Link className={`${navClass(pathname, "/#reviews")} secondary`} href="/#reviews">Відгуки</Link>
        <a
          className="top-nav-link secondary top-nav-ext"
          href={SUPPORT_TG}
          target="_blank"
          rel="noopener noreferrer"
        >
          Менеджер
        </a>
        {user?.isAdmin && (
          <Link className={navClass(pathname, "/admin")} href="/admin">Адмінка</Link>
        )}
      </div>

      <div className="top-nav-actions">
        {user ? (
          <Link className="me" href="/cabinet">
            {user.telegramPhoto ? (
              <img className="av av-img" src={user.telegramPhoto} alt="" />
            ) : (
              <span className="av">{initials}</span>
            )}
            <span className="me-label">{short}</span>
          </Link>
        ) : (
          <Link className="enter" href="/login">Увійти</Link>
        )}
      </div>
    </nav>
  );
}
