import Link from "next/link";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { Logo } from "@/components/Logo";
import { LogoutButton } from "@/components/LogoutButton";
import { pageMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: "Адмінка",
  description: "Адмін-панель flixмаркет",
  path: "/admin",
  noIndex: true,
});

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = await currentUser();
  if (!me) redirect("/login");
  if (!me.isAdmin) redirect("/cabinet");

  return (
    <div className="adm">
      <aside className="adm-side">
        <div style={{ padding: "0 6px" }}>
          <Logo size={18} tag="АДМІНКА" inv />
        </div>
        <nav className="adm-nav">
          <div className="adm-lbl">ОГЛЯД</div>
          <Link href="/admin">Дашборд</Link>
          <Link href="/admin/orders">Платежі</Link>
          <div className="adm-lbl">КАТАЛОГ</div>
          <Link href="/admin/products">Товари</Link>
          <Link href="/admin/categories">Категорії</Link>
          <div className="adm-lbl">ЛЮДИ</div>
          <Link href="/admin/clients">Клієнти</Link>
          <div className="adm-lbl">САЙТ</div>
          <Link href="/">На сайт</Link>
        </nav>
        <div style={{ marginTop: "auto" }}>
          <LogoutButton compact />
        </div>
      </aside>
      <main className="adm-main">{children}</main>
    </div>
  );
}
