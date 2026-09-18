const WRAP = (inner: string, preheader: string) => `<!DOCTYPE html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting"></head>
<body style="margin:0;padding:0;background:#EEF1FA;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">${preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#EEF1FA;">
<tr><td align="center" style="padding:28px 14px 60px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:540px;">
<tr><td style="padding:0 6px 18px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:20px;font-weight:bold;letter-spacing:-0.5px;color:#0A0B0E;">flix<span style="color:#2B5CF6;">маркет</span></td></tr>
<tr><td style="background:#FFFFFF;border-radius:24px;padding:34px 30px;">${inner}</td></tr>
<tr><td style="padding:18px 6px 0;font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;line-height:1.6;color:#8A92A8;">
Підтримка: <a href="https://t.me/FlixMarketBot" style="color:#5A6275;">@FlixMarketBot</a></td></tr>
</table></td></tr></table></body></html>`;

const H = (a: string, b: string) =>
  `<p style="margin:0 0 16px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:30px;line-height:0.95;font-weight:bold;letter-spacing:-1px;color:#0A0B0E;text-transform:uppercase;">${a}<br><span style="color:#2B5CF6;">${b}</span></p>`;

const P = (t: string) =>
  `<p style="margin:0 0 16px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:16px;line-height:1.55;color:#232838;">${t}</p>`;

const SMALL = (t: string) =>
  `<p style="margin:0 0 6px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:14px;line-height:1.55;color:#5A6275;">${t}</p>`;

const BTN = (url: string, label: string) =>
  `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 22px;"><tr>
   <td style="background:#2B5CF6;border-radius:999px;"><a href="${url}" style="display:inline-block;padding:15px 30px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:16px;font-weight:bold;color:#FFFFFF;text-decoration:none;">${label}</a></td>
   </tr></table>`;

export const verifyEmail = (url: string) =>
  WRAP(
    H("Підтверди", "пошту") + P("Один клік — і акаунт активний.") + BTN(url, "Підтвердити пошту") +
    SMALL("Посилання живе 24 години.") +
    SMALL("Знайшов цей лист у «Спамі»? Натисни там «Не спам» — інакше наступні листи від нас теж туди потраплять.") +
    SMALL("Не реєструвався у нас? Просто закрий цей лист."),
    "Один клік — і акаунт активний.",
  );

export const welcomeEmail = (url: string) =>
  WRAP(
    H("Привіт,", "ти з нами") +
    P("Акаунт створено. У кабінеті видно всі підписки, дані для входу і скільки днів кожній лишилось.") +
    P("Купував у нашому боті? Зайди через Telegram — ті підписки зʼявляться тут самі.") +
    BTN(url, "Відкрити кабінет") +
    SMALL("Ми продаємо підписки на сервіси, які в Україні або не оформити, або коштують як половина комуналки.") +
    SMALL("Щось відвалилось — напиши, ми справді відповідаємо."),
    "Тепер у тебе є кабінет із усіма підписками.",
  );

export const resetEmail = (url: string, email: string) =>
  WRAP(
    H("Новий", "пароль") +
    P(`Хтось попросив скинути пароль до акаунта ${email}. Якщо це ти — тисни кнопку.`) +
    BTN(url, "Задати новий пароль") +
    SMALL("Посилання дійсне годину і спрацює один раз.") +
    SMALL("Лист прийшов у «Спам»? Натисни «Не спам», щоб наступні не губились.") +
    SMALL("Це був не ти? Нічого не роби — старий пароль лишиться на місці."),
    "Посилання дійсне годину.",
  );

export const expiringEmail = (product: string, days: number, url: string) =>
  WRAP(
    H(product, `спливає через ${days} дн`) +
    P("Щоб доступ не переривався, продовж підписку до кінця строку.") +
    BTN(url, "Продовжити"),
    `${product}: лишилось ${days} дн.`,
  );

const LIST = (items: string[]) =>
  items.map((t) =>
    `<p style="margin:0 0 10px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;line-height:1.5;color:#232838;">
     <b style="color:#2B5CF6;">·</b>&nbsp; ${t}</p>`).join("");

const BOX = (inner: string) =>
  `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F6F8FD;border-radius:18px;margin:6px 0 20px;">
   <tr><td style="padding:18px 20px;">${inner}</td></tr></table>`;

/** Після покупки: що саме купив, до якої дати і що робити далі */
export const purchaseEmail = (o: {
  product: string; months: number; until: string; amount: string; ref: string; url: string;
}) =>
  WRAP(
    H("Доступ", "готовий") +
    P(`${o.product} — твій до ${o.until}. Усе, що потрібно для входу, лежить у кабінеті.`) +
    BOX(
      `<p style="margin:0 0 6px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:14px;color:#5A6275;font-weight:bold;">ЗАМОВЛЕННЯ ${o.ref}</p>
       <p style="margin:0;font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;color:#232838;">
       ${o.product} · ${o.months} міс · ${o.amount}</p>`,
    ) +
    BTN(o.url, "Відкрити кабінет") +
    `<p style="margin:0 0 12px;font-family:'Helvetica Neue',Arial,sans-serif;font-size:13px;font-weight:bold;letter-spacing:0.3px;color:#5A6275;">ЩОБ НЕ ВИНИКЛО ПИТАНЬ</p>` +
    LIST([
      "Код підтвердження береться кнопкою в кабінеті — він живе 30 секунд.",
      "Не змінюй пароль і пошту на акаунті сервісу: доступ злетить у всіх.",
      "За три дні до кінця строку нагадаємо про продовження.",
      "Щось пішло не так — напиши в бот, ми справді відповідаємо.",
    ]) +
    SMALL("Дякуємо, що обрав нас."),
    `${o.product} готовий, діє до ${o.until}.`,
  );

/** Сповіщення про вхід із нового пристрою */
export const loginEmail = (o: { when: string; ip: string; url: string }) =>
  WRAP(
    H("Новий", "вхід") +
    P("Хтось увійшов у твій акаунт flixмаркет.") +
    BOX(
      `<p style="margin:0;font-family:'Helvetica Neue',Arial,sans-serif;font-size:15px;color:#232838;line-height:1.6;">
       Коли: ${o.when}<br>Звідки: ${o.ip}</p>`,
    ) +
    SMALL("Це ти — нічого робити не треба, лист можна просто видалити.") +
    SMALL("Це не ти — одразу зміни пароль і напиши нам у бот.") +
    BTN(o.url, "Змінити пароль"),
    "Вхід у твій акаунт flixмаркет.",
  );
