export const env = {
  appUrl: process.env.APP_URL ?? "http://localhost:3000",
  botName: process.env.TELEGRAM_BOT_NAME ?? "FlixMarketBot",
  adminTelegramIds: (process.env.ADMIN_TELEGRAM_IDS ?? "")
    .split(",").map((s) => s.trim()).filter(Boolean),
  adminEmails: (process.env.ADMIN_EMAILS ?? "")
    .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean),
};
