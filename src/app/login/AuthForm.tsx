"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { SpamHint } from "@/components/SpamHint";
import { TelegramLogin } from "@/components/TelegramLogin";

type Mode = "login" | "reg" | "forgot";

export function AuthForm({ botName, initialMode, next }:
  { botName: string; initialMode: Mode; next: string }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [peek, setPeek] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit() {
    setBusy(true); setError(null); setDone(null);
    const path = mode === "login" ? "/api/auth/login"
      : mode === "reg" ? "/api/auth/register" : "/api/auth/forgot";
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mode === "forgot" ? { email } : { email, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Щось пішло не так"); return; }

      if (mode === "forgot") setDone("Якщо такий акаунт є, лист уже летить.");
      else { router.push(next); router.refresh(); }
    } catch {
      setError("Мережа не відповідає. Спробуй ще раз.");
    } finally {
      setBusy(false);
    }
  }

  const titles: Record<Mode, string> = {
    login: "З поверненням",
    reg: "Створити акаунт",
    forgot: "Забув пароль",
  };
  const subs: Record<Mode, string> = {
    login: "Увійди через Telegram — якщо купував у боті, підписки зʼявляться самі.",
    reg: "Хвилина — і в тебе є кабінет. Або одразу через Telegram, якщо вже є в боті.",
    forgot: "Введи пошту — надішлемо посилання для нового пароля.",
  };

  return (
    <div>
      <h1 style={{ fontSize: 32, marginBottom: 10, textAlign: "center" }}>{titles[mode]}</h1>
      <p style={{ fontSize: 15, color: "var(--muted)", fontWeight: 500, lineHeight: 1.5,
        marginBottom: 24, textAlign: "center", maxWidth: "36ch", marginLeft: "auto", marginRight: "auto" }}>
        {subs[mode]}
      </p>

      {mode !== "forgot" && (
        <>
          <TelegramLogin
            botName={botName}
            label="Відкриється бот. Підтверди вхід — і підписки зʼявляться самі."
            next={next}
          />
          <div className="or">або поштою</div>
        </>
      )}

      <div className="field">
        <label htmlFor="email">Пошта</label>
        <input id="email" type="email" autoComplete="email" placeholder="ti@example.com"
          value={email} onChange={(e) => { setEmail(e.target.value); setError(null); }}
          aria-invalid={!!error} />
      </div>

      {mode !== "forgot" && (
        <div className="field">
          <label htmlFor="pw">Пароль</label>
          <div style={{ position: "relative" }}>
            <input id="pw" type={peek ? "text" : "password"}
              autoComplete={mode === "reg" ? "new-password" : "current-password"}
              placeholder={mode === "reg" ? "мінімум 8 символів" : "••••••••"}
              value={password} onChange={(e) => { setPassword(e.target.value); setError(null); }}
              aria-invalid={!!error} />
            <button type="button" onClick={() => setPeek(!peek)}
              style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                background: "none", border: 0, cursor: "pointer", fontFamily: "inherit",
                fontSize: 13, fontWeight: 800, color: "var(--muted)", padding: "6px 8px" }}>
              {peek ? "сховати" : "показати"}
            </button>
          </div>
        </div>
      )}

      {mode === "reg" && (
        <>
          <p style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600, margin: "-8px 0 0 2px" }}>
            Надішлемо лист — треба буде підтвердити пошту.
          </p>
          <SpamHint />
          <div style={{ height: 16 }} />
        </>
      )}

      <button className="btn block" onClick={submit} disabled={busy}>
        {busy ? "Хвилинку…" : mode === "login" ? "Увійти" : mode === "reg" ? "Створити акаунт" : "Надіслати посилання"}
      </button>

      {error && <p className="err">{error}</p>}
      {done && <p className="ok-msg">{done}</p>}
      {done && mode === "forgot" && <SpamHint />}

      {mode === "reg" && (
        <p className="terms">Реєструючись, ти погоджуєшся з умовами користування та політикою конфіденційності.</p>
      )}

      <p className="foot-note">
        {mode === "login" && (
          <>
            <button className="link-btn" onClick={() => setMode("forgot")}>Забув пароль</button><br />
            Ще немає акаунта? <button className="link-btn" onClick={() => setMode("reg")}>Зареєструватись</button>
          </>
        )}
        {mode === "reg" && (<>Вже є акаунт? <button className="link-btn" onClick={() => setMode("login")}>Увійти</button></>)}
        {mode === "forgot" && (<button className="link-btn" onClick={() => setMode("login")}>Повернутись до входу</button>)}
      </p>
    </div>
  );
}
