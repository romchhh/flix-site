"use client";
import { useState } from "react";
import { deleteProduct } from "../actions";

/**
 * Видалення з підтвердженням.
 * Якщо товар уже в замовленнях, дія його не видалить, а лише сховає —
 * і про це сказано до натискання, а не після.
 */
export function DeleteProduct({ id, name, used }: { id: string; name: string; used: boolean }) {
  const [ask, setAsk] = useState(false);

  if (!ask) {
    return (
      <button className="btn sm ghost" style={{ color: "var(--red)" }} onClick={() => setAsk(true)}>
        Видалити
      </button>
    );
  }

  return (
    <>
      <div onClick={() => setAsk(false)}
        style={{ position: "fixed", inset: 0, background: "rgba(10,11,14,.42)", zIndex: 40 }} />
      <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)",
        width: "min(420px,92vw)", background: "#fff", borderRadius: 24, padding: 26, zIndex: 50,
        boxShadow: "0 30px 70px rgba(0,0,0,.3)" }}>
        <h3 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em", marginBottom: 10 }}>
          {used ? "Сховати товар?" : "Видалити товар?"}
        </h3>

        <p style={{ fontSize: 15, lineHeight: 1.55, color: "var(--muted)", fontWeight: 500, marginBottom: 20 }}>
          {used
            ? `«${name}» вже є в замовленнях, тому видалити його не можна — зникла б історія покупок і підписки клієнтів. Замість цього товар зникне з каталогу.`
            : `«${name}» буде видалено назавжди разом з акаунтами на складі, які до нього привʼязані. Скасувати не вийде.`}
        </p>

        <div style={{ display: "flex", gap: 10 }}>
          <form action={deleteProduct.bind(null, id)} style={{ flex: 1 }}>
            <button className="btn block" type="submit"
              style={{ background: used ? "var(--ink)" : "var(--red)" }}>
              {used ? "Сховати" : "Видалити"}
            </button>
          </form>
          <button className="btn ghost" onClick={() => setAsk(false)}>Скасувати</button>
        </div>
      </div>
    </>
  );
}
