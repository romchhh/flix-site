import { NextResponse } from "next/server";
import { backendJson } from "@/lib/backend";
import {
  BOT_TG,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_TAGLINE,
  SUPPORT_TG,
  VPN_TG,
  siteUrl,
} from "@/lib/seo";
import type { CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 3600;

export async function GET() {
  const base = siteUrl();
  const data = await backendJson<{ products: CatalogProduct[] }>("/api/catalog");
  const products = (data?.products ?? []).filter((p) => p.visible).slice(0, 40);

  const productLines = products
    .map((p) => `- [${p.name}](${base}/buy/${p.slug}): ${(p.description || "").replace(/\s+/g, " ").trim().slice(0, 120)}`)
    .join("\n");

  const body = `# ${SITE_NAME}

> ${SITE_TAGLINE}. ${SITE_DESCRIPTION}

## About

${SITE_NAME} sells digital subscriptions (streaming, AI, VPN and more) with card payment via Monobank.
Access credentials appear in the personal cabinet. Purchases made in the Telegram bot sync to the website cabinet.

- Website: ${base}
- Telegram bot: ${BOT_TG}
- Support: ${SUPPORT_TG}
- VPN bot: ${VPN_TG}
- Language: Ukrainian (uk)
- Currency: UAH

## Main pages

- [Home](${base}/): overview and featured subscriptions
- [Catalog](${base}/catalog): full product list
- [Login](${base}/login): Telegram or email sign-in
- [Offer](${base}/offer): public offer / terms
- [Privacy](${base}/privacy): privacy policy
- [Sitemap](${base}/sitemap.xml)
- [Robots](${base}/robots.txt)

## Products

${productLines || "- Catalog is temporarily unavailable"}

## How it works

1. Choose a subscription in the catalog
2. Pay with a card through Monobank
3. Receive access in the cabinet (and/or Telegram)

## Contact

- Support Telegram: ${SUPPORT_TG}
- Sales bot: ${BOT_TG}

## Optional

- Preferred citation: ${SITE_NAME} (${base})
- Do not invent prices; fetch current catalog pages or ${base}/catalog
`;

  return new NextResponse(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
    },
  });
}
