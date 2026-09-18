import type { MetadataRoute } from "next";
import { SITE_NAME, SITE_TAGLINE, siteUrl } from "@/lib/seo";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: SITE_NAME,
    description: SITE_TAGLINE,
    start_url: "/",
    display: "standalone",
    background_color: "#EEF1FA",
    theme_color: "#2B5CF6",
    lang: "uk",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
    id: siteUrl(),
  };
}
