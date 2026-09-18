import { uah } from "./display";
import type { Plan } from "./plan-types";
import type { CatalogProduct } from "./types";

export type { Plan };

function build(months: number, total: number, label: string, monthly: number): Plan {
  return {
    months,
    label,
    total,
    perMonth: Math.round(total / months),
    off: monthly > 0 ? Math.max(0, Math.round((1 - total / (monthly * months)) * 100)) : 0,
  };
}

/** Ціни рахуються на боті. Клієнт присилає лише місяці. */
export function plans(p: CatalogProduct): Plan[] {
  if (p.plans?.length) return p.plans;
  if (p.recurring) return [build(1, p.price, "щомісяця", p.price)];
  return (
    [
      [3, p.price3, "3 місяці"] as const,
      [6, p.price6, "6 місяців"] as const,
      [12, p.price12, "12 місяців"] as const,
    ]
      .filter(([, total]) => total > 0)
      .map(([months, total, label]) => build(months, total, label, p.price))
  );
}

function cheapestPlan(p: CatalogProduct): Plan | null {
  if (p.plans?.length) {
    return [...p.plans].filter((x) => x.total > 0).sort((a, b) => a.total - b.total)[0] ?? null;
  }
  return null;
}

/** Підпис ціни в картці каталогу */
export function cardPrice(p: CatalogProduct): { main: string; note: string } {
  if (p.recurring && p.price) return { main: `${uah(p.price)} ₴`, note: "щомісяця" };
  const cheapest = cheapestPlan(p);
  if (cheapest) return { main: `від ${uah(cheapest.total)} ₴`, note: `за ${cheapest.months} міс` };
  const fallback = [p.price, p.price3, p.price6, p.price12].filter((v) => v > 0).sort((a, b) => a - b)[0];
  return fallback ? { main: `від ${uah(fallback)} ₴`, note: "" } : { main: "—", note: "немає цін" };
}

export function priceCaption(p: CatalogProduct): string {
  if (p.recurring && p.price) return `${uah(p.price)} ₴ / міс`;
  const cheapest = cheapestPlan(p);
  if (cheapest) return `від ${uah(cheapest.total)} ₴`;
  const fallback = [p.price, p.price3, p.price6, p.price12].filter((v) => v > 0).sort((a, b) => a - b)[0];
  return fallback ? `від ${uah(fallback)} ₴` : "—";
}
