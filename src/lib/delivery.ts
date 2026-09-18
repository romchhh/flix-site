import { db } from "./db";
import { mail } from "./mail";
import { uah, dateUk } from "./display";

type Result = { ok: boolean; reason?: string };

/**
 * Видача доступу після оплати.
 *
 * Бере вільний слот зі складу і створює підписку. Якщо слота немає,
 * замовлення лишається в статусі PAID і спливає в адмінці як «потребує видачі» —
 * гроші вже отримані, тому мовчазна помилка тут неприпустима.
 *
 * Сама видача йде в транзакції: два одночасні замовлення не заберуть
 * той самий останній слот.
 */
export async function deliverOrder(orderId: string): Promise<Result> {
  const res = await db.$transaction(async (tx) => {
    const order = await tx.order.findUnique({
      where: { id: orderId },
      include: { product: true, subscription: true },
    });

    if (!order) return { ok: false, reason: "Замовлення не знайдено", fresh: false };
    if (order.subscription) return { ok: true, fresh: false };          // вже видано
    if (order.status !== "PAID") return { ok: false, reason: "Замовлення не оплачене", fresh: false };
    if (!order.product.autoIssue) return { ok: false, reason: "Товар видається вручну", fresh: false };

    const cred = await tx.credential.findFirst({
      where: {
        productId: order.productId,
        active: true,
        slotsUsed: { lt: db.credential.fields.slotsTotal },
      },
      orderBy: { slotsUsed: "desc" },   // добиваємо початі акаунти, а не розпорошуємось
    });

    if (!cred) return { ok: false, reason: "Немає вільних слотів на складі", fresh: false };

    await tx.credential.update({
      where: { id: cred.id },
      data: { slotsUsed: { increment: 1 } },
    });

    await tx.subscription.create({
      data: {
        userId: order.userId,
        productId: order.productId,
        orderId: order.id,
        credentialId: cred.id,
        profileName: `Профіль ${cred.slotsUsed + 1}`,
        expiresAt: new Date(Date.now() + order.product.days * order.months * 86400_000),
        source: "site",
      },
    });

    await tx.order.update({ where: { id: order.id }, data: { status: "DELIVERED" } });
    return { ok: true, fresh: true };
  });

  // Лист шлеться після транзакції: доступ уже видано,
  // і збій пошти не має скасовувати покупку
  if (res.ok && res.fresh) await sendPurchaseMail(orderId);

  return { ok: res.ok, reason: res.reason };
}

async function sendPurchaseMail(orderId: string) {
  try {
    const order = await db.order.findUnique({
      where: { id: orderId },
      include: { user: true, product: true, subscription: true },
    });
    if (!order?.user.email || !order.subscription) return;

    await mail.purchase(order.user.email, {
      product: order.product.name,
      months: order.months,
      until: dateUk(order.subscription.expiresAt),
      amount: `${uah(order.amount)} ₴`,
      ref: order.ref,
    });
  } catch (e) {
    console.error("[mail] purchase:", e);
  }
}

/** Звільняє слот, коли підписка завершилась або її скасували */
export async function releaseSlot(subscriptionId: string) {
  const sub = await db.subscription.findUnique({ where: { id: subscriptionId } });
  if (!sub?.credentialId) return;
  await db.credential.update({
    where: { id: sub.credentialId },
    data: { slotsUsed: { decrement: 1 } },
  });
}
