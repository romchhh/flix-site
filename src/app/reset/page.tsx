import { Suspense } from "react";
import { Logo } from "@/components/Logo";
import { PageBack } from "@/components/PageBack";
import { ResetForm } from "./ResetForm";
import { SpamHint } from "@/components/SpamHint";

export const dynamic = "force-dynamic";

export default async function ResetPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;

  return (
    <div className="auth-wrap">
      <Suspense fallback={null}>
        <PageBack className="auth-back" />
      </Suspense>
      <div className="auth-card">
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
          <Logo size={22} tag={null} />
        </div>
        <h1 style={{ fontSize: 32, marginBottom: 10, textAlign: "center" }}>Новий пароль</h1>
        <p style={{ fontSize: 15, color: "var(--muted)", fontWeight: 500, marginBottom: 24,
          textAlign: "center", maxWidth: "34ch", marginLeft: "auto", marginRight: "auto" }}>
          Придумай пароль, який не використовуєш більше ніде.
        </p>
        <ResetForm token={token ?? ""} />
        {!token && <SpamHint />}
      </div>
    </div>
  );
}
