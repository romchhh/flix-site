import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { plans, priceCaption } from "@/lib/pricing";
import { CoverPhoto } from "@/components/CoverPhoto";
import { currentUser } from "@/lib/session";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { ServiceIcon } from "@/components/ServiceIcon";
import { Faq } from "@/components/Faq";
import { parseFaq } from "@/lib/faq";
import { letterOf, badgeClass, badgeLabel } from "@/lib/display";
import { BuyForm } from "./BuyForm";
import { backendJson } from "@/lib/backend";
import type { CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

async function loadProduct(slug: string) {
  const data = await backendJson<{ products: CatalogProduct[] }>("/api/catalog");
  return data?.products.find((p) => p.slug === slug || p.id === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const p = await loadProduct(slug);
  if (!p) return { title: "Товар не знайдено" };
  return {
    title: `${p.name} — flixмаркет`,
    description: (p.description || "").slice(0, 160),
  };
}

export default async function BuyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await backendJson<{ products: CatalogProduct[] }>("/api/catalog");
  const products = data?.products ?? [];
  const product = products.find((p) => p.slug === slug || p.id === slug);
  if (!product || !product.visible) notFound();

  const me = await currentUser();
  const options = plans(product);
  const faq = parseFaq(product.faq);
  const others = products.filter((p) => p.id !== product.id).slice(0, 4);

  return (
    <div className="wrap">
      <SiteHeader />

      <p className="crumbs">
        <Link href="/catalog">Каталог</Link> → {product.name}
      </p>

      <div className="buy-grid">
        <div>
          {product.photoUrl && (
            <div className="p-photo">
              <img src={product.photoUrl} alt={product.name} />
              {badgeLabel(product.badge) && (
                <span className={badgeClass(product.badge)}>{badgeLabel(product.badge)}</span>
              )}
            </div>
          )}
          <div className="p-head">
            <ServiceIcon slug={product.icon} color={product.color} letter={letterOf(product)} size={46} />
            <h1>{product.name}</h1>
          </div>

          <p className="p-lede">{product.description}</p>

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

        <div className="sticky">
          <div className="card">
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
        </div>
      </div>

      <SiteFooter />
    </div>
  );
}
