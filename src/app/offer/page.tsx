import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { LegalText } from "@/components/LegalText";
import { OFFER, OFFER_UPDATED } from "@/content/offer";
import { pageMetadata } from "@/lib/seo";

export const metadata: Metadata = pageMetadata({
  title: "Публічна оферта",
  description: "Умови користування сервісом flixмаркет: оплата, видача доступу, повернення коштів.",
  path: "/offer",
});

export default function OfferPage() {
  return (
    <>
      <SiteHeader />
      <div className="wrap">
      <div className="legal">
        <h1 className="h-sm" style={{ margin: "28px 0 8px" }}>Публічна<br /><em>оферта</em></h1>
        <p className="legal-date">Оновлено {OFFER_UPDATED}</p>
        <div className="legal-body"><LegalText raw={OFFER} /></div>
      </div>
      <SiteFooter />
      </div>
    </>
  );
}
