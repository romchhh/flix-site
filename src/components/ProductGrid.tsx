import { CatalogCard } from "./CatalogCard";
import { cardPrice } from "@/lib/pricing";
import type { CatalogProduct } from "@/lib/types";

export function ProductGrid({ products, catSlug }: { products: CatalogProduct[]; catSlug?: string | null }) {
  const catQ = catSlug ? `?cat=${encodeURIComponent(catSlug)}` : "";
  return (
    <div className="cards catalog">
      {products.map((p) => {
        const price = cardPrice(p);
        return (
          <CatalogCard
            key={p.id}
            name={p.name}
            icon={p.icon}
            color={p.color}
            description={p.description}
            features={p.features}
            priceMain={price.main}
            priceNote={price.note}
            href={`/buy/${p.slug}${catQ}`}
            photoUrl={p.photoUrl}
            badge={p.badge}
          />
        );
      })}
    </div>
  );
}
