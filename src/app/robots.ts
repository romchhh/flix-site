import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  const base = siteUrl();
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/admin/", "/cabinet", "/link", "/reset"],
      },
      {
        userAgent: "GPTBot",
        allow: ["/", "/catalog", "/buy/", "/offer", "/privacy", "/llms.txt"],
        disallow: ["/api/", "/admin/", "/cabinet", "/login", "/link", "/reset"],
      },
      {
        userAgent: "ChatGPT-User",
        allow: ["/", "/catalog", "/buy/", "/offer", "/privacy", "/llms.txt"],
        disallow: ["/api/", "/admin/", "/cabinet"],
      },
      {
        userAgent: "Google-Extended",
        allow: ["/", "/catalog", "/buy/", "/offer", "/privacy", "/llms.txt"],
        disallow: ["/api/", "/admin/", "/cabinet"],
      },
      {
        userAgent: "anthropic-ai",
        allow: ["/", "/catalog", "/buy/", "/offer", "/privacy", "/llms.txt"],
        disallow: ["/api/", "/admin/", "/cabinet"],
      },
      {
        userAgent: "ClaudeBot",
        allow: ["/", "/catalog", "/buy/", "/offer", "/privacy", "/llms.txt"],
        disallow: ["/api/", "/admin/", "/cabinet"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
