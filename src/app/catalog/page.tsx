import Link from "next/link";
import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { CategoryRow } from "@/components/CategoryRow";
import { ProductGrid } from "@/components/ProductGrid";
import { Arrow, TgIcon } from "@/components/Logo";
import { JsonLd } from "@/components/JsonLd";
import { backendJson } from "@/lib/backend";
import { breadcrumbJsonLd, itemListJsonLd, pageMetadata } from "@/lib/seo";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ cat?: string }> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { cat } = await searchParams;
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const categories = data?.categories ?? [];
  const current = cat ? categories.find((c) => c.slug === cat || c.id === cat) : null;
  if (current) {
    return pageMetadata({
      title: `${current.name} — каталог`,
      description: `Підписки ${current.name} у flixмаркет. Оплата карткою, доступ у кабінеті.`,
      path: `/catalog?cat=${encodeURIComponent(cat!)}`,
    });
  }
  return pageMetadata({
    title: "Каталог підписок",
    description: "Netflix, ChatGPT, Claude, HBO Max та інші підписки. Оплата карткою, доступ у кабінеті.",
    path: "/catalog",
  });
}

export default async function CatalogPage({ searchParams }: Props) {
  const { cat } = await searchParams;
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const categories = data?.categories ?? [];
  const all = data?.products ?? [];
  const products = cat ? all.filter((p) => p.categoryId === cat || categories.find((c) => c.slug === cat)?.id === p.categoryId) : all;
  const current = cat ? categories.find((c) => c.slug === cat || c.id === cat) : null;
  const listPath = cat ? `/catalog?cat=${encodeURIComponent(cat)}` : "/catalog";

  return (
    <div className="wrap">
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Головна", path: "/" },
            { name: current?.name || "Каталог", path: listPath },
          ]),
          itemListJsonLd(products, {
            name: current ? `Підписки ${current.name}` : "Каталог підписок flixмаркет",
            path: listPath,
          }),
        ]}
      />
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
