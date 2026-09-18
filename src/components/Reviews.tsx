"use client";
import { useState, useEffect } from "react";
import { ServiceIcon } from "./ServiceIcon";

const SHOTS = [
  { src: "/reviews/1.jpg", who: "Netflix", icon: "netflix", color: "#E50914", note: "майже рік із нами",
    alt: "Майже рік користуюсь вашою підпискою на Netflix, усе добре працює" },
  { src: "/reviews/2.jpg", who: "ChatGPT Plus", icon: "openai", color: "#10A37F", note: "перша покупка",
    alt: "Замовив преміум ChatGPT. Сервіс у хлопців просто вогонь, допомогли розібратись зі входом" },
  { src: "/reviews/3.jpg", who: "Постійний клієнт", icon: "", color: "#1DAA53", note: "не перше замовлення",
    alt: "Как всегда всё на высшем уровне, с вами приятно иметь дело" },
  { src: "/reviews/4.jpg", who: "Олег", icon: "", color: "#2B5CF6", note: "не перший рік",
    alt: "Не перший рік з вами працюю, все супер. Сервіс просто космічний" },
  { src: "/reviews/5.jpg", who: "Netflix", icon: "netflix", color: "#E50914", note: "відгук о 00:49",
    alt: "Велике дякую за швидкий та якісний сервіс" },
];

export function Reviews() {
  const [open, setOpen] = useState<number | null>(null);

  useEffect(() => {
    if (open === null) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(null); };
    document.addEventListener("keydown", esc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", esc);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <section id="reviews">
      <h2>Що кажуть<br /><em>клієнти</em></h2>
      <p className="sec-sub">Скриншоти листування в Telegram. Натисни, щоб прочитати повністю.</p>

      <div className="rev-row">
        {SHOTS.map((s, i) => (
          <button className="rev-card" key={s.src} onClick={() => setOpen(i)}
            aria-label={`Відгук: ${s.alt}`}>
            <span className="rev-thumb">
              <img src={s.src} alt="" loading="lazy" />
            </span>
            <span className="rev-cap">
              {s.icon
                ? <ServiceIcon slug={s.icon} color={s.color} letter={s.who.charAt(0)} size={22} />
                : <span className="rev-letter" style={{ background: s.color }}>{s.who.charAt(0)}</span>}
              <span className="rev-meta">
                <b>{s.who}</b>
                <small>{s.note}</small>
              </span>
            </span>
          </button>
        ))}
      </div>

      {open !== null && (
        <div className="rev-modal" onClick={() => setOpen(null)} role="dialog" aria-modal="true">
          <button className="rev-close" aria-label="Закрити">×</button>
          <img src={SHOTS[open].src} alt={SHOTS[open].alt} onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </section>
  );
}
