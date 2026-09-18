import type { Metadata } from "next";
import { Manrope, Montserrat } from "next/font/google";
import "./globals.css";

const manrope = Manrope({ subsets: ["latin", "cyrillic"], weight: ["400","500","700","800"], variable: "--font-manrope" });
const montserrat = Montserrat({ subsets: ["latin", "cyrillic"], weight: ["600"], variable: "--font-montserrat" });

export const metadata: Metadata = {
  title: "flixмаркет — підписки, які просто працюють",
  description: "Netflix, ChatGPT, Claude та інші підписки. Оплата карткою, доступ у кабінеті за пару хвилин.",
  openGraph: {
    title: "flixмаркет",
    description: "Підписки, які просто працюють",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="uk" className={`${manrope.variable} ${montserrat.variable}`}>
      <body>{children}</body>
    </html>
  );
}
