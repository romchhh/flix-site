import type { Metadata } from "next";
import type { CatalogCategory, CatalogProduct } from "./types";
import { plans } from "./pricing";

export const SITE_NAME = "flixмаркет";
export const SITE_TAGLINE = "підписки, які просто працюють";
export const SITE_DESCRIPTION =
  "Netflix, ChatGPT, Claude, HBO Max та інші підписки. Оплата карткою через Monobank, доступ у кабінеті за пару хвилин. Купував у боті — підписки теж підтягнуться.";
export const SITE_LOCALE = "uk_UA";
export const SUPPORT_TG = "https://t.me/kinomanage";
export const BOT_TG = "https://t.me/FlixMarketBot";
export const VPN_TG = "https://t.me/FlixVPNBot";

export function siteUrl(): string {
  return (process.env.APP_URL || "https://flix-market.com").replace(/\/$/, "");
}

export function absUrl(path = "/"): string {
  const base = siteUrl();
  if (!path || path === "/") return base;
  return path.startsWith("http") ? path : `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function truncate(text: string, max = 160): string {
  const clean = (text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1).trimEnd()}…`;
}

type PageMetaOpts = {
  title?: string;
  description?: string;
  path?: string;
  image?: string | null;
  keywords?: string[];
  noIndex?: boolean;
  type?: "website" | "article";
};

export function pageMetadata({
  title,
  description = SITE_DESCRIPTION,
  path = "/",
  image,
  keywords,
  noIndex = false,
  type = "website",
}: PageMetaOpts = {}): Metadata {
  const url = absUrl(path);
  const short = (title || "").replace(/\s*[—–-]\s*flixмаркет\s*$/i, "").trim();
  const fullTitle = short
    ? `${short} — ${SITE_NAME}`
    : `${SITE_NAME} — ${SITE_TAGLINE}`;
  const desc = truncate(description);
  const ogImage = image ? absUrl(image) : undefined;

  return {
    title: short || { absolute: fullTitle },
    description: desc,
    ...(keywords?.length ? { keywords } : {}),
    alternates: { canonical: url },
    robots: noIndex
      ? { index: false, follow: false, googleBot: { index: false, follow: false } }
      : { index: true, follow: true },
    openGraph: {
      title: fullTitle,
      description: desc,
      url,
      siteName: SITE_NAME,
      locale: SITE_LOCALE,
      type,
      ...(ogImage
        ? { images: [{ url: ogImage, width: 1200, height: 630, alt: SITE_NAME }] }
        : {}),
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description: desc,
      ...(ogImage ? { images: [ogImage] } : {}),
    },
  };
}

export function rootMetadata(): Metadata {
  const base = siteUrl();
  return {
    metadataBase: new URL(base),
    title: {
      default: `${SITE_NAME} — ${SITE_TAGLINE}`,
      template: `%s — ${SITE_NAME}`,
    },
    description: SITE_DESCRIPTION,
    applicationName: SITE_NAME,
    keywords: [
      "підписки",
      "Netflix",
      "ChatGPT",
      "Claude",
      "HBO Max",
      "Spotify",
      "flixмаркет",
      "flixmarket",
      "купити підписку",
      "Monobank",
      "Telegram бот",
    ],
    authors: [{ name: SITE_NAME, url: base }],
    creator: SITE_NAME,
    publisher: SITE_NAME,
    category: "shopping",
    formatDetection: { telephone: false, email: false, address: false },
    alternates: {
      canonical: base,
      languages: { uk: base, "x-default": base },
    },
    openGraph: {
      title: `${SITE_NAME} — ${SITE_TAGLINE}`,
      description: SITE_DESCRIPTION,
      url: base,
      siteName: SITE_NAME,
      locale: SITE_LOCALE,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: `${SITE_NAME} — ${SITE_TAGLINE}`,
      description: SITE_DESCRIPTION,
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-image-preview": "large",
        "max-snippet": -1,
        "max-video-preview": -1,
      },
    },
    icons: {
      icon: [
        { url: "/icon.svg", type: "image/svg+xml" },
        { url: "/icon.svg", sizes: "32x32", type: "image/svg+xml" },
      ],
      apple: [{ url: "/apple-icon.svg", type: "image/svg+xml" }],
      shortcut: ["/icon.svg"],
    },
    other: {
      "theme-color": "#2B5CF6",
    },
  };
}

export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: siteUrl(),
    logo: absUrl("/icon.svg"),
    description: SITE_DESCRIPTION,
    sameAs: [BOT_TG, VPN_TG, SUPPORT_TG],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer support",
        url: SUPPORT_TG,
        availableLanguage: ["Ukrainian", "Russian"],
      },
    ],
  };
}

export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: SITE_NAME,
    url: siteUrl(),
    description: SITE_DESCRIPTION,
    inLanguage: "uk-UA",
    publisher: { "@type": "Organization", name: SITE_NAME, url: siteUrl() },
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${siteUrl()}/catalog`,
      },
      "query-input": "required name=search_term_string",
    },
  };
}

export function breadcrumbJsonLd(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: absUrl(item.path),
    })),
  };
}

export function productJsonLd(product: CatalogProduct) {
  const options = plans(product);
  const cheapest = [...options].filter((p) => p.total > 0).sort((a, b) => a.total - b.total)[0];
  const price = cheapest ? (cheapest.total / 100).toFixed(2) : undefined;
  const desc = truncate(product.description || `${product.name} у ${SITE_NAME}`, 300);

  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: desc,
    image: product.photoUrl ? absUrl(product.photoUrl) : absUrl("/og.png"),
    sku: product.id,
    brand: { "@type": "Brand", name: SITE_NAME },
    url: absUrl(`/buy/${product.slug}`),
    category: product.categoryName || undefined,
    offers: price
      ? {
          "@type": "Offer",
          url: absUrl(`/buy/${product.slug}`),
          priceCurrency: "UAH",
          price,
          availability: "https://schema.org/InStock",
          seller: { "@type": "Organization", name: SITE_NAME },
        }
      : undefined,
  };
}

export function faqJsonLd(items: { q: string; a: string }[]) {
  if (!items.length) return null;
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };
}

export function itemListJsonLd(
  products: CatalogProduct[],
  opts: { name: string; path: string },
) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: opts.name,
    url: absUrl(opts.path),
    numberOfItems: products.length,
    itemListElement: products.slice(0, 50).map((p, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: absUrl(`/buy/${p.slug}`),
      name: p.name,
    })),
  };
}

function productCountLabel(count: number): string {
  if (count === 1) return "1 підписка";
  if (count < 5) return `${count} підписки`;
  return `${count} підписок`;
}

export function categorySeo(category: CatalogCategory, products: CatalogProduct[]) {
  const names = products.map((p) => p.name);
  const sample = names.slice(0, 4).join(", ");
  const extra = names.length > 4 ? " та інші" : "";
  const description = products.length
    ? `Купити ${category.name.toLowerCase()} у flixмаркет: ${sample}${extra}. ${productCountLabel(products.length)}. Оплата карткою Monobank, доступ у кабінеті.`
    : `Підписки ${category.name} у flixмаркет. Оплата карткою, доступ у кабінеті.`;
  const keywords = [
    category.name,
    `купити ${category.name}`,
    "підписка",
    "flixмаркет",
    "flixmarket",
    ...names,
  ];

  return {
    title: `${category.name} — каталог`,
    description: truncate(description, 160),
    keywords: [...new Set(keywords.map((k) => k.trim()).filter(Boolean))],
    image: category.photoUrl,
  };
}

export function productSeo(product: CatalogProduct) {
  const pricePart = product.price > 0 ? ` від ${product.price} ₴` : "";
  const categoryPart = product.categoryName ? ` Категорія: ${product.categoryName}.` : "";
  const description = truncate(
    product.description ||
      `Купити ${product.name}${pricePart} на flixмаркет.${categoryPart} Оплата карткою Monobank, доступ у кабінеті за кілька хвилин.`,
    160,
  );
  const keywords = [
    product.name,
    `купити ${product.name}`,
    product.categoryName || "",
    "підписка",
    "flixмаркет",
    "flixmarket",
    product.recurring ? "щомісячна підписка" : "разова оплата",
    "Monobank",
  ];

  return {
    title: product.name,
    description,
    keywords: [...new Set(keywords.map((k) => k.trim()).filter(Boolean))],
    image: product.photoUrl,
  };
}

export function collectionPageJsonLd(
  category: CatalogCategory,
  products: CatalogProduct[],
  path: string,
) {
  const list = itemListJsonLd(products, {
    name: `Підписки ${category.name}`,
    path,
  });

  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${category.name} — каталог`,
    description: truncate(`Підписки ${category.name} у flixмаркет`, 300),
    url: absUrl(path),
    inLanguage: "uk-UA",
    isPartOf: { "@type": "WebSite", name: SITE_NAME, url: siteUrl() },
    ...(category.photoUrl ? { image: absUrl(category.photoUrl) } : {}),
    mainEntity: list,
  };
}
