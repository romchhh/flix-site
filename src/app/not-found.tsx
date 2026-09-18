import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function NotFound() {
  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
          <Logo size={22} tag={null} />
        </div>
        <h1 style={{ fontSize: 34, marginBottom: 10 }}>Немає такої<br />сторінки</h1>
        <p style={{ fontSize: 15, color: "var(--muted)", fontWeight: 500, marginBottom: 22 }}>
          Можливо, посилання застаріло.
        </p>
        <Link className="btn block" href="/">На головну</Link>
      </div>
    </div>
  );
}
