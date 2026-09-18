"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function LogoutButton({ compact = false }: { compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function out() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      router.push("/");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  if (compact) {
    return (
      <button className="logout-x" onClick={out} disabled={busy} title="Вийти" aria-label="Вийти">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
             strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
      </button>
    );
  }

  return (
    <button className="btn soft" onClick={out} disabled={busy}>
      {busy ? "Виходимо…" : "Вийти з акаунта"}
    </button>
  );
}
