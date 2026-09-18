import { db } from "./db";

/** Скільки разів можна попросити 2FA-код: захист і від перебору, і від злитого доступу */
export async function canRequestCode(userId: string, subscriptionId: string) {
  const since = new Date(Date.now() - 60 * 60 * 1000);
  const [perSub, perUser] = await Promise.all([
    db.codeLog.count({ where: { subscriptionId, createdAt: { gte: since } } }),
    db.codeLog.count({ where: { userId, createdAt: { gte: since } } }),
  ]);
  if (perSub >= 10) return { ok: false, reason: "Забагато запитів за цією підпискою. Спробуй за годину." };
  if (perUser >= 30) return { ok: false, reason: "Забагато запитів. Спробуй за годину." };
  return { ok: true as const };
}

const hits = new Map<string, { n: number; until: number }>();

/** Простий лічильник у памʼяті для форм входу. Для кількох інстансів — винести в Redis. */
export function throttle(key: string, limit: number, windowMs: number) {
  const now = Date.now();
  const rec = hits.get(key);
  if (!rec || rec.until < now) {
    hits.set(key, { n: 1, until: now + windowMs });
    return { ok: true as const };
  }
  rec.n += 1;
  if (rec.n > limit) return { ok: false as const, retryIn: Math.ceil((rec.until - now) / 1000) };
  return { ok: true as const };
}
