import { NextRequest, NextResponse } from "next/server";

/**
 * Проксі для логотипів сервісів.
 *
 * Джерел кілька: структура пакета simple-icons між версіями мінялась,
 * і покладатись на один шлях означає одного дня лишитись без усіх іконок.
 * Перше, що віддало валідний SVG, — те й беремо.
 */
const SOURCES = (slug: string, color: string) => [
  `https://cdn.simpleicons.org/${slug}/${color}`,
  `https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/${slug}.svg`,
  `https://cdn.jsdelivr.net/npm/simple-icons/icons/${slug}.svg`,
  `https://unpkg.com/simple-icons@latest/icons/${slug}.svg`,
];

export async function GET(req: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  if (!/^[a-z0-9.-]{1,40}$/.test(slug)) {
    return new NextResponse("bad slug", { status: 400 });
  }

  const color =
    (req.nextUrl.searchParams.get("c") ?? "000000").replace(/[^0-9a-fA-F]/g, "").slice(0, 6) || "000000";

  const tried: string[] = [];

  for (const url of SOURCES(slug, color)) {
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": "flixmarket/1.0" },
        next: { revalidate: 60 * 60 * 24 * 7 },
      });
      if (!res.ok) { tried.push(`${url} → ${res.status}`); continue; }

      const svg = await res.text();
      if (!svg.trimStart().startsWith("<svg")) { tried.push(`${url} → not svg`); continue; }

      // cdn.simpleicons.org уже віддає пофарбований; решта — чорні
      const painted = svg.includes("fill=") ? svg : svg.replace("<svg", `<svg fill="#${color}"`);

      return new NextResponse(painted, {
        headers: {
          "Content-Type": "image/svg+xml",
          "Cache-Control": "public, max-age=604800",
          "X-Icon-Source": new URL(url).host,
        },
      });
    } catch (e) {
      tried.push(`${url} → ${(e as Error).message}`);
    }
  }

  // Діагностика лишається в логах: мовчазна відсутність іконок — найгірший варіант
  console.error(`[icon] ${slug}: жодне джерело не відповіло\n  ${tried.join("\n  ")}`);
  return new NextResponse("not found", { status: 404, headers: { "X-Icon-Tried": String(tried.length) } });
}
