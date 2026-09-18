import Link from "next/link";
import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { CategoryRow } from "@/components/CategoryRow";
import { ProductGrid } from "@/components/ProductGrid";
import { Arrow, TgIcon } from "@/components/Logo";
import { JsonLd } from "@/components/JsonLd";
import { backendJson } from "@/lib/backend";
import { breadcrumbJsonLd, categorySeo, collectionPageJsonLd, itemListJsonLd, pageMetadata, truncate } from "@/lib/seo";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ cat?: string }> };

function categoryProducts(
  all: CatalogProduct[],
  categories: CatalogCategory[],
  cat?: string,
) {
  if (!cat) return all;
  const current = categories.find((c) => c.slug === cat || c.id === cat);
  return all.filter((p) => p.categoryId === cat || current?.id === p.categoryId);
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const { cat } = await searchParams;
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const categories = data?.categories ?? [];
  const all = data?.products ?? [];
  const current = cat ? categories.find((c) => c.slug === cat || c.id === cat) : null;
  if (current) {
    const products = categoryProducts(all, categories, cat);
    const seo = categorySeo(current, products);
    return pageMetadata({
      title: seo.title,
      description: seo.description,
      keywords: seo.keywords,
      image: seo.image,
      path: `/catalog?cat=${encodeURIComponent(current.slug)}`,
    });
  }
  const names = all.map((p) => p.name).slice(0, 6).join(", ");
  return pageMetadata({
    title: "Каталог підписок",
    description: truncate(
      `Netflix, ChatGPT, Claude, HBO Max та інші підписки: ${names}. Оплата карткою Monobank, доступ у кабінеті.`,
      160,
    ),
    keywords: ["каталог підписок", "flixмаркет", "купити підписку", ...all.map((p) => p.name)],
    path: "/catalog",
  });
}

export default async function CatalogPage({ searchParams }: Props) {
  const { cat } = await searchParams;
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const categories = data?.categories ?? [];
  const all = data?.products ?? [];
  const current = cat ? categories.find((c) => c.slug === cat || c.id === cat) : null;
  const products = categoryProducts(all, categories, cat);
  const listPath = current ? `/catalog?cat=${encodeURIComponent(current.slug)}` : "/catalog";

  const jsonLd = [
    breadcrumbJsonLd([
      { name: "Головна", path: "/" },
      { name: "Каталог", path: "/catalog" },
      ...(current ? [{ name: current.name, path: listPath }] : []),
    ]),
    itemListJsonLd(products, {
      name: current ? `Підписки ${current.name}` : "Каталог підписок flixмаркет",
      path: listPath,
    }),
    ...(current ? [collectionPageJsonLd(current, products, listPath)] : []),
  ];

  return (
    <>
      <JsonLd data={jsonLd} />
      <SiteHeader />
      <div className="wrap">
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
          <ProductGrid products={products} catSlug={current?.slug ?? null} />
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
    </>
  );
}
