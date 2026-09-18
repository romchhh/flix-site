import { PrismaClient } from "@prisma/client";
import { encrypt } from "../src/lib/crypto";

const db = new PrismaClient();

const products = [
  { slug: "netflix", name: "Netflix Premium", icon: "netflix", color: "#E50914",
    price: 14900, recurring: true, price3: 0, price6: 0, price12: 0,
    description: "Окремий профіль зі своїм PIN, ніхто не зайде і не змінить тобі мову.",
    features: "4K та HDR\nдва пристрої одночасно\nкоди входу в кабінеті", sortOrder: 1,
    deliveryNote: "Доступ приходить за 2–5 хвилин", faq: 'Це мій особистий акаунт?\nПрофіль лише твій, зі своїм PIN. Ніхто не змінить тобі мову і не зіпсує рекомендації.\n\nА якщо перестане працювати?\nНапиши в бот — замінимо доступ або повернемо гроші за невикористані дні.\n\nЩо робити, коли просять код підтвердження?\nБереш його кнопкою в кабінеті, він дійсний 30 секунд. Для кількох сервісів код видаємо ми вручну — тоді просто напиши в бот.\n\nЧи потрібен VPN?\nЗдебільшого ні. Якщо сервіс пише, що недоступний у твоєму регіоні — у нас є FlixVPN.' },
  { slug: "netflix-term", name: "Netflix Premium на строк", icon: "netflix", color: "#E50914",
    price: 14900, recurring: false, price3: 42000, price6: 79000, price12: 149000,
    description: "Той самий Netflix, але одним платежем і без автосписань.",
    features: "4K та HDR\nдва пристрої одночасно\nбез щомісячних списань", sortOrder: 2,
    deliveryNote: "Доступ приходить за 2–5 хвилин", faq: 'Це мій особистий акаунт?\nПрофіль лише твій, зі своїм PIN. Ніхто не змінить тобі мову і не зіпсує рекомендації.\n\nА якщо перестане працювати?\nНапиши в бот — замінимо доступ або повернемо гроші за невикористані дні.\n\nЩо робити, коли просять код підтвердження?\nБереш його кнопкою в кабінеті, він дійсний 30 секунд. Для кількох сервісів код видаємо ми вручну — тоді просто напиши в бот.\n\nЧи потрібен VPN?\nЗдебільшого ні. Якщо сервіс пише, що недоступний у твоєму регіоні — у нас є FlixVPN.' },
  { slug: "chatgpt", name: "ChatGPT Plus", icon: "openai", color: "#10A37F",
    price: 39900, recurring: false, price3: 115000, price6: 219000, price12: 419000,
    description: "Особистий акаунт, а не спільний. Історія чатів лишається твоєю.",
    features: "актуальні моделі\nбез черг у пікові години", sortOrder: 3 },
  { slug: "claude", name: "Claude Pro", icon: "claude", color: "#D97757",
    price: 39900, recurring: false, price3: 115000, price6: 219000, price12: 419000,
    description: "Для довгих задач і великих документів.",
    features: "підвищені ліміти\nробота з файлами", sortOrder: 4 },
  { slug: "flixvpn", name: "FlixVPN", icon: "", color: "#2B5CF6",
    price: 9900, recurring: false, price3: 27000, price6: 49000, price12: 89000,
    description: "Наш власний VPN на VLESS Reality.",
    features: "до 3 пристроїв\nбез логів\nконфіг у кабінеті", sortOrder: 5 },
];

async function main() {
  for (const p of products) {
    await db.product.upsert({ where: { slug: p.slug }, update: p, create: p });
  }

  const netflix = await db.product.findUnique({ where: { slug: "netflix" } });
  if (netflix) {
    await db.credential.create({
      data: {
        productId: netflix.id,
        login: "demo.netflix@example.com",
        secretEnc: encrypt("demo-password"),
        totpEnc: encrypt("JBSWY3DPEHPK3PXP"),
        slotsTotal: 5,
      },
    });
  }

  await db.promo.upsert({
    where: { code: "FLIX10" },
    update: {},
    create: { code: "FLIX10", percentOff: 10, firstOnly: true, maxUses: 500 },
  });

  console.log("Готово: товари, демо-акаунт і промокод FLIX10");
}

main().finally(() => db.$disconnect());
