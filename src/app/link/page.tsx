import { redirect } from "next/navigation";
import { currentUser } from "@/lib/session";
import { env } from "@/lib/env";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { LinkForm } from "./LinkForm";

export const dynamic = "force-dynamic";

export default async function LinkPage() {
  const me = await currentUser();
  if (!me) redirect("/login");
  if (me.telegramId) redirect("/cabinet");

  return (
    <div className="wrap-narrow">
      <SiteHeader />
      <h1 className="h-sm" style={{ margin: "28px 0 20px" }}>
        Підтягнути покупки<br />з <em>бота</em>
      </h1>
      <LinkForm botName={env.botName} />
      <SiteFooter />
    </div>
  );
}
