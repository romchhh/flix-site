import nodemailer, { type Transporter } from "nodemailer";
import { env } from "./env";
import {
  welcomeEmail, verifyEmail, resetEmail, expiringEmail, purchaseEmail, loginEmail,
} from "@/emails/templates";

/**
 * Відправка листів.
 *
 * Спершу HTTP API Resend: хостери на кшталт DigitalOcean блокують вихідні
 * SMTP-порти (25, 465, 587), і зʼєднання просто відвалюється по таймауту.
 * HTTP іде через 443, який відкритий завжди.
 *
 * SMTP лишається запасним шляхом — на випадок іншого провайдера пошти.
 */
const RESEND_KEY = process.env.RESEND_API_KEY ?? "";
const FROM = process.env.MAIL_FROM ?? "flixмаркет <hi@flix-market.com>";

async function sendViaResend(to: string, subject: string, html: string) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${RESEND_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ from: FROM, to: [to], subject, html }),
  });

  if (!res.ok) {
    throw new Error(`Resend ${res.status}: ${await res.text()}`);
  }
}

let transport: Transporter | null = null;

async function sendViaSmtp(to: string, subject: string, html: string) {
  if (!transport) {
    transport = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: Number(process.env.SMTP_PORT ?? 465),
      secure: Number(process.env.SMTP_PORT ?? 465) === 465,
      auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS },
    });
  }
  await transport.sendMail({ from: FROM, to, subject, html });
}

async function send(to: string, subject: string, html: string) {
  if (RESEND_KEY) return sendViaResend(to, subject, html);
  if (process.env.SMTP_HOST) return sendViaSmtp(to, subject, html);
  console.log(`[mail:dev] → ${to} · ${subject}`);
}

export const mail = {
  verify: (to: string, token: string) =>
    send(to, "Підтверди пошту", verifyEmail(`${env.appUrl}/api/auth/verify?token=${token}`)),

  welcome: (to: string) => send(to, "Привіт, ти з нами", welcomeEmail(`${env.appUrl}/cabinet`)),

  reset: (to: string, token: string) =>
    send(to, "Скидання пароля", resetEmail(`${env.appUrl}/reset?token=${token}`, to)),

  expiring: (to: string, product: string, days: number) =>
    send(to, `${product} спливає через ${days} дн`, expiringEmail(product, days, `${env.appUrl}/cabinet`)),

  purchase: (to: string, o: { product: string; months: number; until: string; amount: string; ref: string }) =>
    send(to, `${o.product} — доступ готовий`, purchaseEmail({ ...o, url: `${env.appUrl}/cabinet` })),

  newLogin: (to: string, o: { when: string; ip: string }) =>
    send(to, "Новий вхід у твій акаунт", loginEmail({ ...o, url: `${env.appUrl}/login` })),
};
