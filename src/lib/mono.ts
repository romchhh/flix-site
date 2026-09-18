import crypto from "crypto";
import { env } from "./env";

const API = "https://api.monobank.ua/api/merchant";

export type MonoInvoice = { invoiceId: string; pageUrl: string };

/**
 * Створює інвойс. Сума — в копійках.
 * reference — наш номер замовлення, він повернеться у вебхуку.
 */
export async function createInvoice(opts: {
  amount: number;
  reference: string;
  destination: string;
  redirectUrl: string;
  webHookUrl: string;
}): Promise<MonoInvoice> {
  const res = await fetch(`${API}/invoice/create`, {
    method: "POST",
    headers: { "X-Token": env.monoToken(), "Content-Type": "application/json" },
    body: JSON.stringify({
      amount: opts.amount,
      ccy: 980,
      merchantPaymInfo: {
        reference: opts.reference,
        destination: opts.destination,
      },
      redirectUrl: opts.redirectUrl,
      webHookUrl: opts.webHookUrl,
      validity: 3600,
      paymentType: "debit",
    }),
    cache: "no-store",
  });

  if (!res.ok) throw new Error(`Monobank: ${res.status} ${await res.text()}`);
  return res.json();
}

let pubKeyCache: { key: string; at: number } | null = null;

async function publicKey(): Promise<string> {
  // Ключ змінюється рідко, але кешувати назавжди не можна
  if (pubKeyCache && Date.now() - pubKeyCache.at < 60 * 60 * 1000) return pubKeyCache.key;
  const res = await fetch(`${API}/pubkey`, {
    headers: { "X-Token": env.monoToken() },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Monobank pubkey: ${res.status}`);
  const { key } = (await res.json()) as { key: string };
  pubKeyCache = { key, at: Date.now() };
  return key;
}

/**
 * Перевірка підпису вебхука.
 * Без неї будь-хто може надіслати «оплачено» і забрати товар безкоштовно.
 */
export async function verifyWebhook(rawBody: string, xSign: string | null): Promise<boolean> {
  if (!xSign) return false;
  try {
    const pem = Buffer.from(await publicKey(), "base64").toString("utf8");
    return crypto.verify(
      "SHA256",
      Buffer.from(rawBody),
      { key: pem, dsaEncoding: "der" },
      Buffer.from(xSign, "base64"),
    );
  } catch {
    return false;
  }
}

export type MonoStatus =
  | "created" | "processing" | "hold" | "success"
  | "failure" | "reversed" | "expired";
