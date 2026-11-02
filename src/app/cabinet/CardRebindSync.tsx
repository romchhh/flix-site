"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const KEY = "flix_card_rebind";

async function finish(invoiceId: string) {
  const res = await fetch("/api/card/rebind/finish", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ invoiceId }),
  });
  return res.json();
}

export function CardRebindSync() {
  const router = useRouter();
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    const invoiceId = sessionStorage.getItem(KEY);
    if (!invoiceId) return;
    let stop = false;
    const returned = new URLSearchParams(window.location.search).get("card") === "1";

    (async () => {
      for (let attempt = 0; attempt < 4 && !stop; attempt += 1) {
        try {
          const data = await finish(invoiceId);
          if (stop) return;
          if (data.done) {
            sessionStorage.removeItem(KEY);
            setNote(
              data.maskedCard
                ? `Картку змінено на ${data.maskedCard}. Блокування 1 грн знято.`
                : "Картку змінено. Блокування 1 грн знято.",
            );
            router.refresh();
            return;
          }
          const status = String(data.status || "").toLowerCase();
          if (data.pending && (status === "hold" || status === "success" || !status)) {
            setNote("Картку прийнято, знімаємо блокування 1 грн…");
            await new Promise((r) => setTimeout(r, 2500));
            continue;
          }
          if (!returned && (status === "created" || status === "processing" || !status)) {
            return;
          }
          if (status === "created" || status === "processing") {
            setNote("Підтвердження ще не завершене. Якщо вікно Monobank закрилось — натисни «Змінити картку» ще раз.");
            return;
          }
          sessionStorage.removeItem(KEY);
          setNote(data.error || "Не вдалось змінити картку. Спробуй ще раз.");
          return;
        } catch {
          if (!stop) setNote("Не вдалось підтвердити картку. Онови сторінку.");
          return;
        }
      }
    })();
    return () => { stop = true; };
  }, [router]);

  if (!note) return null;
  return <p className="buy-form-note buy-form-note-box" style={{ margin: "0 0 16px" }}>{note}</p>;
}
