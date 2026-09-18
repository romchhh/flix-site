import crypto from "crypto";
import { env } from "./env";

export type TgUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
};

/**
 * Дані від Telegram Login Widget.
 * Підпис перевіряється на сервері — клієнтським полям не вірить ніхто.
 */
export function verifyLoginWidget(data: Record<string, string>): TgUser | null {
  const { hash, ...rest } = data;
  if (!hash) return null;

  const dcs = Object.keys(rest).sort().map((k) => `${k}=${rest[k]}`).join("\n");
  const secret = crypto.createHash("sha256").update(env.botToken()).digest();
  const sign = crypto.createHmac("sha256", secret).update(dcs).digest("hex");

  const a = Buffer.from(sign, "hex");
  const b = Buffer.from(hash, "hex");
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;

  // Ліміт на вік підпису: інакше перехоплений URL працює вічно
  const age = Date.now() / 1000 - Number(rest.auth_date);
  if (!Number.isFinite(age) || age > 300) return null;

  return {
    id: Number(rest.id),
    first_name: rest.first_name,
    last_name: rest.last_name,
    username: rest.username,
    photo_url: rest.photo_url,
    auth_date: Number(rest.auth_date),
  };
}

/** Те саме для Mini App: інший вивід ключа, решта однакова */
export function verifyInitData(initData: string): TgUser | null {
  const params = new URLSearchParams(initData);
  const hash = params.get("hash");
  if (!hash) return null;
  params.delete("hash");

  const dcs = [...params.entries()].sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`).join("\n");

  const secret = crypto.createHmac("sha256", "WebAppData").update(env.botToken()).digest();
  const sign = crypto.createHmac("sha256", secret).update(dcs).digest("hex");
  if (sign !== hash) return null;

  const authDate = Number(params.get("auth_date"));
  if (Date.now() / 1000 - authDate > 300) return null;

  try {
    return { ...JSON.parse(params.get("user") ?? "{}"), auth_date: authDate };
  } catch {
    return null;
  }
}
