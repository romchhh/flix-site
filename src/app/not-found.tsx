import Link from "next/link";
import type { Metadata } from "next";
import { Logo, Arrow } from "@/components/Logo";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Сторінку не знайдено",
  description: "Такої сторінки немає на flixмаркет. Повернись на головну або в каталог підписок.",
  path: "/404",
  noIndex: true,
});

export default function NotFound() {
  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
          <Logo size={22} tag={null} />
        </div>
        <p style={{ fontSize: 13, fontWeight: 800, color: "var(--blue)", letterSpacing: ".08em", marginBottom: 10 }}>
          404
        </p>
        <h1 style={{ fontSize: 34, marginBottom: 10 }}>Немає такої<br />сторінки</h1>
        <p style={{ fontSize: 15, color: "var(--muted)", fontWeight: 500, marginBottom: 22, lineHeight: 1.5 }}>
          Посилання застаріло або адресу набрали з помилкою.
          Обери підписку в каталозі — або повернись на головну.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Link className="btn block" href="/catalog">
            До каталогу<span className="dot"><Arrow /></span>
          </Link>
          <Link className="btn ghost block" href="/">На головну</Link>
        </div>
      </div>
    </div>
  );
}
