import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { env } from "@/lib/env";
import { Logo } from "@/components/Logo";
import { AuthForm } from "./AuthForm";

export const dynamic = "force-dynamic";

export default async function LoginPage({ searchParams }:
  { searchParams: Promise<{ mode?: string; verify?: string; next?: string }> }) {
  const me = await currentUser();
  if (me) redirect("/cabinet");

  const { mode, verify, next } = await searchParams;

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
          <Logo size={22} tag={null} />
        </div>
        {verify === "fail" && (
          <p className="err" style={{ textAlign: "center", marginBottom: 14 }}>
            Посилання для підтвердження протухло. Увійди і запроси нове.
          </p>
        )}
        <AuthForm botName={env.botName} initialMode={mode === "reg" ? "reg" : "login"} next={next ?? "/cabinet"} />
      </div>
    </div>
  );
}
