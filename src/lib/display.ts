/** Літера-запасний варіант, якщо іконка сервісу не завантажилась */
export const letterOf = (p: { name: string }) => p.name.charAt(0).toUpperCase();

export function badgeLabel(badge?: string | null) {
  if (!badge) return null;
  if (badge === "hot") return "Гаряча пропозиція";
  if (badge === "bestseller") return "Бестселер";
  if (badge === "new") return "Нове";
  return null;
}

export function badgeClass(badge?: string | null) {
  if (badge === "hot") return "badge badge-hot";
  if (badge === "bestseller") return "badge badge-bestseller";
  if (badge === "new") return "badge badge-new";
  return "badge";
}

export const uah = (kop: number) =>
  (kop / 100).toLocaleString("uk-UA", { maximumFractionDigits: 0 });

const MONTHS = ["січня","лютого","березня","квітня","травня","червня",
                "липня","серпня","вересня","жовтня","листопада","грудня"];

export const dateUk = (d: Date) => `${d.getDate()} ${MONTHS[d.getMonth()]}`;

export const dateTimeUk = (d: Date) => {
  const hh = d.getHours().toString().padStart(2, "0");
  const mm = d.getMinutes().toString().padStart(2, "0");
  return `${dateUk(d)} о ${hh}:${mm}`;
};

export function productPhotoUrl(photoUrl?: string | null, productId?: string | number | null) {
  const idFromUrl = photoUrl?.match(/\/product\/(\d+)/)?.[1];
  const id = (productId != null && String(productId)) || idFromUrl;
  if (id) return `/api/media/product/${id}`;
  if (photoUrl?.startsWith("/api/media/")) return photoUrl;
  return null;
}

export function formatCard(masked?: string | null, type?: string | null) {
  if (!masked) return null;
  const digits = masked.replace(/\D/g, "");
  const last4 = digits.slice(-4);
  const label = last4 ? `•••• ${last4}` : masked;
  const raw = (type || "").trim();
  const known = raw && !/^(unknown|none|null|n\/a)$/i.test(raw);
  return known ? `${label} · ${raw.toUpperCase()}` : label;
}

const PAY_STATUS: Record<string, string> = {
  success: "Успішно",
  failed: "Невдало",
  error: "Помилка",
  processing: "В обробці",
  pending: "Очікується",
};

export function payStatusLabel(status?: string | null) {
  const key = (status || "").toLowerCase();
  return PAY_STATUS[key] || status || "—";
}

export function daysLeft(expiresAt: Date): number {
  return Math.max(0, Math.ceil((expiresAt.getTime() - Date.now()) / 86400_000));
}

/** Скільки строку вже минуло, 0–100 */
export function progress(startsAt: Date, expiresAt: Date): number {
  const all = expiresAt.getTime() - startsAt.getTime();
  const left = expiresAt.getTime() - Date.now();
  if (all <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((left / all) * 100)));
}

export const plural = (n: number, one: string, few: string, many: string) => {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return few;
  return many;
};
