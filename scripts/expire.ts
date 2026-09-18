import { PrismaClient } from "@prisma/client";

const db = new PrismaClient();

/**
 * Крон раз на годину:
 *  — нагадує за 3 дні до кінця строку
 *  — закриває підписки, що спливли, і звільняє слоти на складі
 */
async function main() {
  const now = new Date();
  const in3 = new Date(now.getTime() + 3 * 86400_000);

  const soon = await db.subscription.findMany({
    where: { status: "ACTIVE", expiresAt: { gt: now, lt: in3 } },
    include: { user: true, product: true },
  });

  const { mail } = await import("../src/lib/mail");
  for (const s of soon) {
    if (!s.user.email) continue;
    const days = Math.ceil((s.expiresAt.getTime() - now.getTime()) / 86400_000);
    await mail.expiring(s.user.email, s.product.name, days);
  }

  const expired = await db.subscription.findMany({
    where: { status: "ACTIVE", expiresAt: { lte: now } },
  });

  for (const s of expired) {
    await db.$transaction([
      db.subscription.update({ where: { id: s.id }, data: { status: "EXPIRED" } }),
      ...(s.credentialId
        ? [db.credential.update({ where: { id: s.credentialId }, data: { slotsUsed: { decrement: 1 } } })]
        : []),
    ]);
  }

  console.log(`Нагадувань: ${soon.length}, завершено: ${expired.length}`);
}

main().finally(() => db.$disconnect());
