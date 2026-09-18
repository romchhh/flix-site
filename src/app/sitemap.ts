import type { MetadataRoute } from "next";
import { backendJson } from "@/lib/backend";
import { absUrl } from "@/lib/seo";
import type { CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const staticPages: MetadataRoute.Sitemap = [
    { url: absUrl("/"), lastModified: now, changeFrequency: "daily", priority: 1 },
    { url: absUrl("/catalog"), lastModified: now, changeFrequency: "daily", priority: 0.95 },
    { url: absUrl("/login"), lastModified: now, changeFrequency: "monthly", priority: 0.4 },
    { url: absUrl("/offer"), lastModified: now, changeFrequency: "yearly", priority: 0.3 },
    { url: absUrl("/privacy"), lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];

  const data = await backendJson<{ products: CatalogProduct[] }>("/api/catalog");
  const products = (data?.products ?? []).filter((p) => p.visible && p.slug);

  const productPages: MetadataRoute.Sitemap = products.map((p) => ({
    url: absUrl(`/buy/${p.slug}`),
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  return [...staticPages, ...productPages];
}
