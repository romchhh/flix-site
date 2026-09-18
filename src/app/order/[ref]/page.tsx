import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { OrderClient } from "./OrderClient";
import { pageMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata: Metadata = pageMetadata({
  title: "Замовлення",
  description: "Статус оплати та доступ до підписки flixмаркет.",
  path: "/order",
  noIndex: true,
});

export default async function OrderPage({ params }: { params: Promise<{ ref: string }> }) {
  const { ref } = await params;
  return (
    <>
      <SiteHeader />
      <div className="wrap">
        <OrderClient orderRef={decodeURIComponent(ref)} />
        <SiteFooter />
      </div>
    </>
  );
}
