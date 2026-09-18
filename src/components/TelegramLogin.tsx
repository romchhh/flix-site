"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TgIcon } from "./Logo";

/** Прибирає зламаний офіційний віджет (Bot domain invalid) — вхід лише через бота. */
function removeTelegramWidget() {
  document
    .querySelectorAll(
      'script[src*="telegram-widget"], iframe[src*="oauth.telegram.org"], .tgme_widget_login, [id^="telegram-login"]',
    )
    .forEach((el) => el.remove());
}

export function openTelegram(url: string, botName: string) {
  const start = (() => {
    try { return new URL(url).searchParams.get("start") || ""; }
    catch { return ""; }
  })();
  const domain = botName.replace(/^@/, "");
  // Спочатку deep-link у застосунок — саме з payload
  if (start) {
    window.location.href = `tg://resolve?domain=${encodeURIComponent(domain)}&start=${encodeURIComponent(start)}`;
  }
  // Fallback у браузері / якщо tg:// не спрацював
  setTimeout(() => {
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }, 400);
}

/** Вхід через бота (t.me/...?start=payload), без офіційного Login Widget. */
export function TelegramLogin({ botName, label, onDone, next = "/cabinet" }:
  { botName: string; label: string; onDone?: (r: { imported?: number; linked?: boolean }) => void; next?: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [botUrl, setBotUrl] = useState<string | null>(null);
  const [payloadHint, setPayloadHint] = useState<string | null>(null);

  async function finish(data: { imported?: number; linked?: boolean }) {
    if (onDone) onDone(data);
    else { router.push(next); router.refresh(); }
  }

  useEffect(() => {
    removeTelegramWidget();
    const observer = new MutationObserver(removeTelegramWidget);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  async function viaBot() {
    setBusy(true);
    setError(null);
    setPayloadHint(null);
    try {
      const res = await fetch("/api/auth/telegram/start", { method: "POST" });
      let data: { error?: string; url?: string; token?: string; ok?: boolean } = {};
      try { data = await res.json(); } catch { /* non-json */ }
      if (!res.ok) {
        setError(
          data.error
          ?? (res.status >= 500
            ? "Сервер API не відповідає. Перевір, що FastAPI (порт 8000) запущений."
            : "Не вдалось відкрити Telegram"),
        );
        return;
      }
      if (!data.url || !data.token) {
        setError("Некоректна відповідь сервера логіну.");
        return;
      }
      try {
        const start = new URL(data.url).searchParams.get("start") || "";
        if (start) setPayloadHint(start);
      } catch { /* ignore */ }
      setWaiting(true);
      setBotUrl(data.url);
      openTelegram(data.url, botName);
      const started = Date.now();
      while (Date.now() - started < 10 * 60 * 1000) {
        await new Promise((r) => setTimeout(r, 1500));
        const st = await fetch(`/api/auth/telegram/status?token=${encodeURIComponent(data.token!)}`);
        let body: { error?: string; status?: string; ok?: boolean; login?: boolean } = {};
        try { body = await st.json(); } catch { continue; }
        if (!st.ok) { setError(body.error ?? "Не вдалось перевірити вхід"); break; }
        if (body.status === "expired") { setError("Посилання протухло. Натисни кнопку ще раз."); break; }
        if (body.ok || body.login) { await finish({}); return; }
        const me = await fetch("/api/me");
        if (me.ok) { await finish({}); return; }
      }
      setError("Не дочекались підтвердження. Натисни кнопку ще раз.");
    } catch {
      setError("Мережа не відповідає. Спробуй ще раз.");
    } finally {
      setBusy(false);
      setWaiting(false);
    }
  }

  return (
    <div>
      <button type="button" className="tg-btn" onClick={viaBot} disabled={busy || waiting}>
        <TgIcon />
        {waiting ? "Чекаємо підтвердження в Telegram…" : "Увійти через Telegram"}
      </button>
      {waiting && botUrl && (
        <p className="tg-note">
          1) Відкрий{" "}
          <a href={botUrl} target="_blank" rel="noopener">це посилання</a>
          {" "}і натисни синю <b>Start</b>.
          <br />
          2) Не пиши /start вручну — тоді код входу зникає.
          {payloadHint && (
            <>
              <br />
              Якщо бот уже відкритий — надішли йому цей текст: <code>{payloadHint}</code>
            </>
          )}
        </p>
      )}
      <p className="tg-note">
        {waiting ? "Після Start у боті повернись сюди — кабінет відкриється сам." : label}
      </p>
      {error && <p className="err" style={{ textAlign: "center" }}>{error}</p>}
    </div>
  );
}
