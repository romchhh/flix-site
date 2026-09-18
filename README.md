# flixмаркет

Сайт — точка входу. Каталог, оплати, автосписання і підписки живуть у **FlixMarketBot**.
Сайт лише створює рахунок через API бота і показує той самий стан клієнту.

Бекенд сайту — Python (FastAPI) + SQLite (акаунти поштою). Вітрина — Next.js.

## Запуск

Три процеси.

**1. Бот (і публічне API)**

```bash
cd FlixMarketBot/bot
pip install -r requirements.txt
python main.py
```

API піднімається на `http://127.0.0.1:8088`. Потрібні `API_KEY`, `XTOKEN` (Monobank) у `FlixMarketBot/.env`.

**2. Python-бекенд сайту**

```bash
cd flixmarket-code-site
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env   # BOT_API_KEY = API_KEY бота, TELEGRAM_BOT_TOKEN = BOT_TOKEN
uvicorn backend.app:app --reload --port 8000
```

**3. Фронт**

```bash
cd flixmarket-code-site
npm install
npm run dev
```

Відкрий `http://localhost:3000`.

## Що як працює

- Каталог і ціни — з SQLite бота (`database/data.db`).
- «Оплатити» на сайті → API бота створює інвойс Monobank (разова оплата або токенізація картки).
- Успіх перевіряє бот (вебхук або крон кожні 30 с) і створює підписку / recurring.
- Автосписання — кроном бота, як і раніше.
- Привʼязка Telegram у кабінеті імпортує підписки клієнта з бота.

Для вебхука Monobank вистав `PUBLIC_API_URL` у боті на публічну адресу API, наприклад `https://api.flix-market.com`. Без цього бот усе одно підхопить оплату поллінгом.

Адмінка сайту читає дані бота. Редагування товарів — у Telegram-адмінці бота.
