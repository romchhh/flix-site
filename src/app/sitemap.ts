import type { MetadataRoute } from "next";
import { backendJson } from "@/lib/backend";
import { absUrl } from "@/lib/seo";
import type { CatalogCategory, CatalogProduct } from "@/lib/types";

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

  const data = await backendJson<{ products: CatalogProduct[]; categories: CatalogCategory[] }>("/api/catalog");
  const products = (data?.products ?? []).filter((p) => p.visible && p.slug);
  const categories = (data?.categories ?? []).filter((c) => c.active && c.slug);

  const categoryPages: MetadataRoute.Sitemap = categories.map((c) => ({
    url: absUrl(`/catalog?cat=${encodeURIComponent(c.slug)}`),
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.85,
  }));

  const productPages: MetadataRoute.Sitemap = products.map((p) => ({
    url: absUrl(`/buy/${p.slug}`),
    lastModified: now,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  return [...staticPages, ...categoryPages, ...productPages];
}
