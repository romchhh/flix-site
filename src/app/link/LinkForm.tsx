"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { TelegramLogin } from "@/components/TelegramLogin";
import { plural } from "@/lib/display";

export function LinkForm({ botName }: { botName: string }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submitCode() {
    setBusy(true); setError(null);
    try {
      const res = await fetch("/api/auth/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim().toUpperCase() }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Код не підійшов"); return; }
      setResult(data.imported ?? 0);
      router.refresh();
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setBusy(false);
    }
  }

  if (result !== null) {
    return (
      <div className="empty">
        <h3>Telegram привʼязано</h3>
        <p>
          {result > 0
            ? `Перенесли ${result} ${plural(result, "підписку", "підписки", "підписок")} у кабінет.`
            : "Покупок у боті не знайшли — але наступні зʼявляться тут автоматично."}
        </p>
        <button className="btn" onClick={() => router.push("/cabinet")}>До кабінету</button>
      </div>
    );
  }

  return (
    <div className="card">
      <p style={{ fontSize: 16, lineHeight: 1.55, color: "#232838", fontWeight: 500 }}>
        Купував у нашому боті? Привʼяжи Telegram — і ті підписки зʼявляться тут
        разом зі строками. Заходити можна і через Telegram, і поштою.
      </p>
      <p className="tip" style={{ marginBottom: 18 }}>
        Ми бачимо тільки твій нік та id. Листування, контакти й інші чати нам недоступні.
      </p>

      <TelegramLogin
        botName={botName}
        label="Одна кнопка — бот підтвердить вхід, покупки підтягнуться."
        onDone={(r) => { setResult(r.imported ?? 0); router.refresh(); }}
      />

      <div className="or">купував з чужого акаунта?</div>

      <p className="tip" style={{ marginTop: 0, marginBottom: 14 }}>
        Надішли боту команду <b style={{ color: "var(--ink)" }}>/link</b> — він дасть код на 10 хвилин.
      </p>

      <div className="promo-row">
        <input value={code} maxLength={8} placeholder="код з бота" autoComplete="off"
          style={{ letterSpacing: ".2em", textTransform: "uppercase", fontWeight: 800 }}
          onChange={(e) => { setCode(e.target.value); setError(null); }} />
        <button className="btn" onClick={submitCode} disabled={busy || code.trim().length < 4}>
          {busy ? "…" : "Готово"}
        </button>
      </div>

      {error && <p className="err">{error}</p>}
    </div>
  );
}
