"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { TgIcon } from "./Logo";

declare global {
  interface Window { onTelegramAuth?: (u: Record<string, string>) => void }
}

export function openTelegram(url: string, botName: string) {
  const start = (() => {
    try { return new URL(url).searchParams.get("start") || ""; }
    catch { return ""; }
  })();
  const domain = botName.replace(/^@/, "");
  if (start) {
    const native = document.createElement("iframe");
    native.style.display = "none";
    native.src = `tg://resolve?domain=${encodeURIComponent(domain)}&start=${encodeURIComponent(start)}`;
    document.body.appendChild(native);
    setTimeout(() => native.remove(), 2500);
  }
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

/**
 * Вхід через бота (t.me/...?start=payload).
 * Офіційний віджет — лише на постійному HTTPS-домені з /setdomain у BotFather.
 */
export function TelegramLogin({ botName, label, onDone, next = "/cabinet" }:
  { botName: string; label: string; onDone?: (r: { imported?: number; linked?: boolean }) => void; next?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [botUrl, setBotUrl] = useState<string | null>(null);

  async function finish(data: { imported?: number; linked?: boolean }) {
    if (onDone) onDone(data);
    else { router.push(next); router.refresh(); }
  }

  useEffect(() => {
    window.onTelegramAuth = async (user) => {
      setBusy(true);
      setError(null);
      try {
        const res = await fetch("/api/auth/telegram", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(user),
        });
        const data = await res.json();
        if (!res.ok) { setError(data.error ?? "Не вдалось увійти"); return; }
        await finish(data);
      } catch {
        setError("Мережа не відповідає. Спробуй ще раз.");
      } finally {
        setBusy(false);
      }
    };

    const host = window.location.hostname;
    const https = window.location.protocol === "https:";
    const local = host === "localhost" || host === "127.0.0.1";
    const tunnel = /ngrok|localhost.run|cloudflared|loca.lt/i.test(host);
    if (!https || local || tunnel || !box.current || box.current.childElementCount) return;
    const s = document.createElement("script");
    s.src = "https://telegram.org/js/telegram-widget.js?22";
    s.async = true;
    s.setAttribute("data-telegram-login", botName);
    s.setAttribute("data-size", "large");
    s.setAttribute("data-radius", "20");
    s.setAttribute("data-onauth", "onTelegramAuth(user)");
    s.setAttribute("data-request-access", "write");
    s.setAttribute("data-userpic", "true");
    box.current.appendChild(s);
  }, [botName, onDone, router, next]);

  async function viaBot() {
    setBusy(true);
    setError(null);
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
        if (body.ok || body.login) { await finish(body); return; }
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
      <div ref={box} style={{ display: "flex", justifyContent: "center" }} />
      <button type="button" className="tg-btn" onClick={viaBot} disabled={busy || waiting}>
        <TgIcon />
        {waiting ? "Чекаємо підтвердження в Telegram…" : "Увійти через Telegram"}
      </button>
      {waiting && botUrl && (
        <p className="tg-note">
          Якщо бот відкрився без кнопки Start —{" "}
          <a href={botUrl} target="_blank" rel="noopener">відкрий посилання ще раз</a>
          {" "}і натисни синю <b>Start</b>, не надсилай просто /start.
        </p>
      )}
      <p className="tg-note">
        {waiting ? "У Telegram натисни Start — і повернись сюди, кабінет відкриється сам." : label}
      </p>
      {error && <p className="err" style={{ textAlign: "center" }}>{error}</p>}
    </div>
  );
}
