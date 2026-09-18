"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function ResetForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [peek, setPeek] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function submit() {
    setBusy(true); setError(null);
    try {
      const res = await fetch("/api/auth/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error ?? "Не вдалось змінити пароль"); return; }
      router.push("/cabinet");
      router.refresh();
    } catch {
      setError("Мережа не відповідає");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return <p className="err">Посилання неповне. Запроси скидання ще раз зі сторінки входу.</p>;
  }

  return (
    <div>
      <div className="field">
        <label htmlFor="np">Пароль</label>
        <div style={{ position: "relative" }}>
          <input id="np" type={peek ? "text" : "password"} autoComplete="new-password"
            placeholder="мінімум 8 символів" value={password}
            onChange={(e) => { setPassword(e.target.value); setError(null); }} />
          <button type="button" onClick={() => setPeek(!peek)}
            style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
              background: "none", border: 0, cursor: "pointer", fontFamily: "inherit",
              fontSize: 13, fontWeight: 800, color: "var(--muted)", padding: "6px 8px" }}>
            {peek ? "сховати" : "показати"}
          </button>
        </div>
      </div>
      <button className="btn block" onClick={submit} disabled={busy || password.length < 8}>
        {busy ? "Зберігаємо…" : "Зберегти пароль"}
      </button>
      {error && <p className="err">{error}</p>}
    </div>
  );
}
