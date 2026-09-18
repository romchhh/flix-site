"use client";
import { useState } from "react";

export function VerifyBar({ email }: { email: string }) {
  const [state, setState] = useState<"idle" | "busy" | "sent" | "fail">("idle");
  const [msg, setMsg] = useState("");

  async function resend() {
    setState("busy");
    try {
      const res = await fetch("/api/auth/resend", { method: "POST" });
      const data = await res.json();
      if (!res.ok) { setMsg(data.error ?? "Не вдалось надіслати"); setState("fail"); return; }
      setState("sent");
    } catch {
      setMsg("Мережа не відповідає"); setState("fail");
    }
  }

  return (
    <div className="import" style={{ background: "#FDEDDF" }}>
      <div className="grow">
        <b style={{ color: "#8A4208" }}>Пошту ще не підтверджено</b>
        <p style={{ color: "#A2561A" }}>
          {state === "sent"
            ? `Надіслали лист на ${email}.`
            : state === "fail" ? msg
            : `Надіслали лист на ${email}. Без підтвердження не вийде відновити пароль.`}
        </p>
        <p style={{ color: "#A2561A", fontSize: 12.5, fontWeight: 600, marginTop: 6, lineHeight: 1.45 }}>
          Немає у вхідних — глянь у «Спам» і натисни там «Не спам», інакше наступні листи теж губитимуться.
        </p>
      </div>
      {state !== "sent" && (
        <button className="btn dark" onClick={resend} disabled={state === "busy"}>
          {state === "busy" ? "…" : "Надіслати ще раз"}
        </button>
      )}
    </div>
  );
}
