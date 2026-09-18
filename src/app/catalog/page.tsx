import Link from "next/link";
import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { CategoryRow } from "@/components/CategoryRow";
import { ProductGrid } from "@/components/ProductGrid";
import { Arrow, TgIcon } from "@/components/Logo";
import { backendJson } from "@/lib/backend";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Каталог підписок — flixмаркет",
  description: "Netflix, ChatGPT, Claude, HBO Max та інші підписки. Оплата карткою, доступ у кабінеті.",
};

export default async function CatalogPage({ searchParams }:
  { searchParams: Promise<{ cat?: string }> }) {
  const { cat } = await searchParams;
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const categories = data?.categories ?? [];
  const all = data?.products ?? [];
  const products = cat ? all.filter((p) => p.categoryId === cat || categories.find((c) => c.slug === cat)?.id === p.categoryId) : all;
  const current = cat ? categories.find((c) => c.slug === cat || c.id === cat) : null;

  return (
    <div className="wrap">
      <SiteHeader />

      <section style={{ paddingTop: 44, paddingBottom: 30 }}>
        <h1 className="h-sm" style={{ marginBottom: 10 }}>
          {current ? <>{current.name}</> : <>Усі<br /><em>підписки</em></>}
        </h1>
        <p className="sec-sub">
          {products.length} {products.length === 1 ? "товар" : products.length < 5 ? "товари" : "товарів"}
          {current ? " у цій категорії" : " у каталозі"}
        </p>

        <CategoryRow
          categories={categories.map((c) => ({
            id: c.id, slug: c.slug, name: c.name, icon: c.icon, color: c.color, photoUrl: c.photoUrl,
          }))}
          active={cat ?? null}
        />

        {products.length === 0 ? (
          <div className="empty">
            <h3>Тут поки порожньо</h3>
            <p>У цій категорії ще немає товарів. Подивись інші або напиши в підтримку.</p>
            <Link className="btn" href="/catalog">Усі підписки<span className="dot"><Arrow /></span></Link>
          </div>
        ) : (
          <ProductGrid products={products} />
        )}

        <div className="vpn">
          <span className="v">V</span>
          <div className="txt">
            <b>Свій VPN у нас теж є</b>
            <small>FlixVPN — щоб сервіси відкривались звідусіль і не вередували.</small>
          </div>
          <a href="https://t.me/FlixVPNBot"><TgIcon /> Бот VPN</a>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
