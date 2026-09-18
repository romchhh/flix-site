import crypto from "crypto";
import { env } from "./env";

/**
 * Паролі від сервісів лежать у базі зашифрованими.
 * Ключ тримається в оточенні, окремо від дампів БД:
 * дамп без CREDENTIALS_KEY марний.
 */
function key(): Buffer {
  const k = Buffer.from(env.credentialsKey(), "base64");
  if (k.length !== 32) throw new Error("CREDENTIALS_KEY має бути 32 байти в base64");
  return k;
}

export function encrypt(plain: string): string {
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv("aes-256-gcm", key(), iv);
  const enc = Buffer.concat([c.update(plain, "utf8"), c.final()]);
  return [iv.toString("base64"), c.getAuthTag().toString("base64"), enc.toString("base64")].join(".");
}

export function decrypt(packed: string): string {
  const [iv, tag, data] = packed.split(".");
  const d = crypto.createDecipheriv("aes-256-gcm", key(), Buffer.from(iv, "base64"));
  d.setAuthTag(Buffer.from(tag, "base64"));
  return Buffer.concat([d.update(Buffer.from(data, "base64")), d.final()]).toString("utf8");
}

export function randomToken(bytes = 32): string {
  return crypto.randomBytes(bytes).toString("base64url");
}

/** Короткий код для привʼязки Telegram: без схожих символів */
export function shortCode(len = 6): string {
  const abc = "ACDEFGHJKLMNPQRTUVWXY34679";
  return Array.from(crypto.randomBytes(len)).map((b) => abc[b % abc.length]).join("");
}
