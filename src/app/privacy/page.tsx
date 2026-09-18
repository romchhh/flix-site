import type { Metadata } from "next";
import { SiteHeader, SiteFooter } from "@/components/SiteHeader";
import { LegalText } from "@/components/LegalText";
import { PRIVACY, PRIVACY_UPDATED } from "@/content/privacy";

export const metadata: Metadata = {
  title: "Політика конфіденційності — flixмаркет",
  description: "Які дані збирає flixмаркет, навіщо, кому передає і як довго зберігає.",
};

export default function PrivacyPage() {
  return (
    <div className="wrap">
      <SiteHeader />
      <div className="legal">
        <h1 className="h-sm" style={{ margin: "28px 0 8px" }}>Політика<br /><em>конфіденційності</em></h1>
        <p className="legal-date">Оновлено {PRIVACY_UPDATED}</p>
        <div className="legal-body"><LegalText raw={PRIVACY} /></div>
      </div>
      <SiteFooter />
    </div>
  );
}
