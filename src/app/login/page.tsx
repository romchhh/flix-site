import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { currentUser } from "@/lib/session";
import { env } from "@/lib/env";
import { Suspense } from "react";
import { Logo } from "@/components/Logo";
import { PageBack } from "@/components/PageBack";
import { AuthForm } from "./AuthForm";
import { pageMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: "Увійти",
  description: "Увійди в flixмаркет через Telegram або пошту. Підписки з бота зʼявляться в кабінеті.",
  path: "/login",
  noIndex: true,
});

export default async function LoginPage({ searchParams }:
  { searchParams: Promise<{ mode?: string; verify?: string; next?: string }> }) {
  const me = await currentUser();
  if (me) redirect("/cabinet");

  const { mode, verify, next } = await searchParams;

  return (
    <div className="auth-wrap">
      <Suspense fallback={null}>
        <PageBack className="auth-back" />
      </Suspense>
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
