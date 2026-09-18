import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { plans, priceCaption } from "@/lib/pricing";
import { CoverPhoto } from "@/components/CoverPhoto";
import { currentUser } from "@/lib/session";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { ServiceIcon } from "@/components/ServiceIcon";
import { Faq } from "@/components/Faq";
import { JsonLd } from "@/components/JsonLd";
import { parseFaq } from "@/lib/faq";
import { letterOf, badgeClass, badgeLabel } from "@/lib/display";
import { breadcrumbJsonLd, faqJsonLd, pageMetadata, productJsonLd, productSeo } from "@/lib/seo";
import { ProductDescription } from "@/components/ProductDescription";
import { BuyForm } from "./BuyForm";
import { backendJson } from "@/lib/backend";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

async function loadCatalog() {
  return backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
}

async function loadProduct(slug: string) {
  const data = await loadCatalog();
  return data?.products.find((p) => p.slug === slug || p.id === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const p = await loadProduct(slug);
  if (!p) {
    return pageMetadata({
      title: "Товар не знайдено",
      description: "Такої підписки немає в каталозі flixмаркет.",
      path: `/buy/${slug}`,
      noIndex: true,
    });
  }
  const seo = productSeo(p);
  return pageMetadata({
    title: seo.title,
    description: seo.description,
    keywords: seo.keywords,
    path: `/buy/${p.slug}`,
    image: seo.image || undefined,
  });
}

export default async function BuyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await loadCatalog();
  const products = data?.products ?? [];
  const categories = data?.categories ?? [];
  const product = products.find((p) => p.slug === slug || p.id === slug);
  if (!product || !product.visible) notFound();

  const category = categories.find((c) => c.id === product.categoryId);
  const categoryPath = category ? `/catalog?cat=${encodeURIComponent(category.slug)}` : "/catalog";

  const me = await currentUser();
  const options = plans(product);
  const faq = parseFaq(product.faq);
  const others = products.filter((p) => p.id !== product.id).slice(0, 4);

  return (
    <>
      <JsonLd
        data={[
          breadcrumbJsonLd([
            { name: "Головна", path: "/" },
            { name: "Каталог", path: "/catalog" },
            ...(category ? [{ name: category.name, path: categoryPath }] : []),
            { name: product.name, path: `/buy/${product.slug}` },
          ]),
          productJsonLd(product),
          faqJsonLd(faq),
        ].filter(Boolean) as Record<string, unknown>[]}
      />
      <SiteHeader />
      <div className="wrap buy-page">
      <p className="crumbs">
        <Link href="/catalog">Каталог</Link>
        {category && (
          <> → <Link href={categoryPath}>{category.name}</Link></>
        )}
        {" → "}{product.name}
      </p>

      <div className="buy-grid">
        <div className="buy-main">
          <div className="p-head">
            <ServiceIcon slug={product.icon} color={product.color} letter={letterOf(product)} size={46} />
            <h1>{product.name}</h1>
          </div>

          {product.description && (
            <ProductDescription text={product.description} className="p-lede prose-desc" />
          )}

          {product.features && (
            <div className="feat" style={{ maxWidth: 520 }}>
              {product.features.split("\n").map((f) => f.trim()).filter(Boolean).map((f, i) => (
                <span key={i}><i>✓</i> {f}</span>
              ))}
            </div>
          )}

          <div className="p-sec">
            <h2>Як це буде</h2>
            <div className="p-steps">
              <div className="p-step">
                <b>1</b>
                <p>Обираєш строк і оплачуєш карткою через Monobank.</p>
              </div>
              <div className="p-step">
                <b>2</b>
                <p>Доступ зʼявляється в кабінеті — логін і все, що потрібно для входу.</p>
              </div>
              <div className="p-step">
                <b>3</b>
                <p>Якщо сервіс просить код підтвердження, береш його кнопкою в кабінеті.</p>
              </div>
            </div>
          </div>

          <div className="p-sec">
            <h2>Що ми обіцяємо</h2>
            <div className="assure">
              <div>
                <b>Заміна або повернення</b>
                <small>Відвалився доступ у межах оплаченого строку — міняємо чи повертаємо гроші за невикористані дні.</small>
              </div>
              <div>
                <b>Живий чат</b>
                <small>Відповідаємо самі. У робочий час — протягом 10 хвилин.</small>
              </div>
              <div>
                <b>Нічого зайвого</b>
                <small>Не просимо доступ до твоїх акаунтів і не питаємо дані картки — оплата йде через Monobank.</small>
              </div>
            </div>
          </div>

          {faq.length > 0 && (
            <div className="p-sec">
              <h2>Часті питання</h2>
              <Faq items={faq} />
            </div>
          )}

          {others.length > 0 && (
            <div className="p-sec">
              <h2>Інші підписки</h2>
              <div className="more">
                {others.map((o) => {
                  return (
                    <Link key={o.id} href={`/buy/${o.slug}`}>
                      <CoverPhoto
                        src={o.photoUrl}
                        className="more-photo"
                        fallback={<ServiceIcon slug={o.icon} color={o.color} letter={letterOf(o)} size={28} />}
                      />
                      <span>
                        <b>{o.name}</b>
                        <small>{priceCaption(o)}</small>
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <aside className="sticky buy-aside">
          <div className="card buy-checkout">
            <div className="buy-summary">
              <CoverPhoto
                src={product.photoUrl}
                className="buy-thumb"
                alt={product.name}
                fallback={(
                  <span className="buy-thumb buy-thumb-fallback">
                    <ServiceIcon slug={product.icon} color={product.color} letter={letterOf(product)} size={34} />
                  </span>
                )}
              />
              <div className="buy-summary-text">
                <h2>{product.name}</h2>
                <p>{priceCaption(product)}</p>
                {badgeLabel(product.badge) && (
                  <span className={badgeClass(product.badge)}>{badgeLabel(product.badge)}</span>
                )}
              </div>
            </div>
            <BuyForm
              productId={product.id}
              slug={product.slug}
              options={options}
              loggedIn={!!me}
              free={null}
              recurring={product.recurring}
              deliveryNote={product.deliveryNote}
            />
          </div>
        </aside>
      </div>

      <SiteFooter />
      </div>
    </>
  );
}
