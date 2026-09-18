"use client";
import { useState } from "react";

import type { QA } from "@/lib/faq";

export function Faq({ items }: { items: QA[] }) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="faq">
      {items.map((it, i) => (
        <div className={`faq-item${open === i ? " on" : ""}`} key={i}>
          <button className="faq-q" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
            <span>{it.q}</span>
            <span className="faq-sign" aria-hidden>{open === i ? "−" : "+"}</span>
          </button>
          {open === i && <p className="faq-a">{it.a}</p>}
        </div>
      ))}
    </div>
  );
}
