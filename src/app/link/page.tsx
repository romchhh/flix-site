import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { currentUser } from "@/lib/session";
import { env } from "@/lib/env";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { LinkForm } from "./LinkForm";
import { pageMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: "Привʼязати Telegram",
  description: "Підтягни покупки з бота FlixMarket у кабінет на сайті.",
  path: "/link",
  noIndex: true,
});

export default async function LinkPage() {
  const me = await currentUser();
  if (!me) redirect("/login");
  if (me.telegramId) redirect("/cabinet");

  return (
    <>
      <SiteHeader />
      <div className="wrap-narrow">
      <h1 className="h-sm" style={{ margin: "28px 0 20px" }}>
        Підтягнути покупки<br />з <em>бота</em>
      </h1>
      <LinkForm botName={env.botName} />
      <SiteFooter />
      </div>
    </>
  );
}
