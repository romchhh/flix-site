import Link from "next/link";
import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { ServiceIcon } from "@/components/ServiceIcon";
import { CategoryRow } from "@/components/CategoryRow";
import { ProductGrid } from "@/components/ProductGrid";
import { CabinetPreview } from "@/components/CabinetPreview";
import { Reviews } from "@/components/Reviews";
import { Arrow, TgIcon } from "@/components/Logo";
import { JsonLd } from "@/components/JsonLd";
import { priceCaption } from "@/lib/pricing";
import { letterOf } from "@/lib/display";
import { backendJson } from "@/lib/backend";
import { itemListJsonLd, pageMetadata, SITE_DESCRIPTION, SUPPORT_TG } from "@/lib/seo";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";
import { CoverPhoto } from "@/components/CoverPhoto";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: undefined,
  description: SITE_DESCRIPTION,
  path: "/",
});

export default async function Home() {
  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const products = data?.products ?? [];
  const categories = data?.categories ?? [];

  const tiles = products.slice(0, 4);

  return (
    <>
      <JsonLd
        data={itemListJsonLd(products.filter((p) => p.visible), {
          name: "Каталог підписок flixмаркет",
          path: "/catalog",
        })}
      />
      <SiteHeader />
      <div className="wrap">
      <div style={{ padding: "56px 0 20px" }}>
        <div className="hero-grid" style={{ display: "grid", gridTemplateColumns: "1.1fr .9fr", gap: 40, alignItems: "center" }}>
          <div>
            <h1>Підписки<br />без зайвих<br />рухів</h1>
            <p className="lede">
              Оформив, зайшов, забув до наступного місяця. Купував у боті —
              воно теж підтягнеться сюди.
            </p>
            <div className="hero-acts">
              <Link className="btn" href="/catalog">Обрати підписку<span className="dot"><Arrow /></span></Link>
              <Link className="btn ghost" href="/cabinet">Мій кабінет<span className="dot"><Arrow /></span></Link>
            </div>
            <div className="stats">
              <div className="stat"><b>2 хв</b><small>від оплати до доступу</small></div>
              <div className="stat"><b>24/7</b><small>видача та підтримка</small></div>
            </div>
          </div>

          <div className="tiles">
            {tiles.map((p) => (
              <Link className="tile" key={p.id} href={`/buy/${p.slug}`}>
                <CoverPhoto
                  src={p.photoUrl}
                  className="tile-photo"
                  fallback={<ServiceIcon slug={p.icon} color={p.color} letter={letterOf(p)} />}
                />
                <div>
                  <b>{p.name}</b><br />
                  <small>{priceCaption(p)}</small>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <section id="catalog">
        <h2>Що можна взяти</h2>
        <p className="sec-sub">Від місяця до року — бери на той строк, на який зручно. На довших виходить помітно дешевше.</p>
        <CategoryRow
          categories={categories.map((c) => ({
            id: c.id, slug: c.slug, name: c.name, icon: c.icon, color: c.color, photoUrl: c.photoUrl,
          }))}
          showAll={false}
        />

        <ProductGrid products={products.slice(0, 4)} />

        {products.length > 4 && (
          <div className="more-row">
            <Link className="btn ghost" href="/catalog">
              Ще {products.length - 4} у каталозі<span className="dot"><Arrow /></span>
            </Link>
          </div>
        )}

        <div className="vpn">
          <span className="v">V</span>
          <div className="txt">
            <b>Свій VPN у нас теж є</b>
            <small>FlixVPN — щоб сервіси відкривались звідусіль і не вередували. Працює одразу після оплати.</small>
          </div>
          <a href="https://t.me/FlixVPNBot"><TgIcon /> Бот VPN</a>
        </div>
      </section>

      <section id="how">
        <h2>Три кроки</h2>
        <p className="sec-sub">І все опиняється в одному місці — з датами й кодами.</p>
        <div className="how-grid">
          <CabinetPreview />
          <div className="how-steps">
            <div className="step"><b>1</b><div><h3>Обираєш</h3><p>У каталозі видно наявність і ціну на сьогодні.</p></div></div>
            <div className="step"><b>2</b><div><h3>Оплачуєш</h3><p>Карткою через Monobank, у пару кліків.</p></div></div>
            <div className="step"><b>3</b><div><h3>Заходиш</h3><p>Дані для входу і коди підтвердження — у кабінеті, кнопкою.</p></div></div>
          </div>
        </div>
      </section>

      <Reviews />

      <section id="trust">
        <h2>Чому це не зникне<br />через тиждень</h2>
        <div className="cards">
          <div className="card">
            <h3 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 10 }}>Коди 2FA самообслуговуванням</h3>
            <p>Код підтвердження береш кнопкою в кабінеті, щойно сервіс його попросить. Є кілька сервісів, де код видаємо ми вручну — там просто напиши в підтримку, відповідаємо швидко.</p>
          </div>
          <div className="card">
            <h3 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 10 }}>Заміна при збої</h3>
            <p>Якщо доступ відвалився протягом оплаченого строку — міняємо або повертаємо гроші за невикористані дні.</p>
          </div>
          <div className="card">
            <h3 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 10 }}>Живий чат</h3>
            <p>Відповідаємо самі, без ботів-автовідповідачів по колу. У робочий час — протягом 10 хвилин. <a href={SUPPORT_TG} target="_blank" rel="noopener noreferrer" style={{ color: "var(--blue)", fontWeight: 800 }}>@kinomanage</a></p>
          </div>
        </div>
      </section>

      <section style={{ paddingTop: 40, paddingBottom: 20 }}>
        <div className="cta">
          <div className="cta-txt">
            <b>Готовий обрати підписку?</b>
            <small>Або зайди в бот, якщо звик до нього.</small>
          </div>
          <div className="cta-acts">
            <Link className="btn sm" href="/catalog">До каталогу<span className="dot"><Arrow /></span></Link>
            <a className="btn sm ghost" href="https://t.me/FlixMarketBot">Бот<span className="dot"><Arrow /></span></a>
          </div>
        </div>
      </section>

      <SiteFooter />
      </div>
    </>
  );
}
