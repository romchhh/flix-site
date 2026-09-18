"use client";
import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { ServiceIcon } from "./ServiceIcon";
import { Arrow } from "./Logo";
import { badgeClass, badgeLabel } from "@/lib/display";
import { ProductDescription } from "./ProductDescription";

/**
 * Картка каталогу.
 *
 * Згорнута має фіксовану висоту — і місце під кнопку «Ще» резервується завжди,
 * навіть коли ховати нічого. Інакше картки без кнопки виходять нижчими за сусідні.
 * Факт обрізки міряється по реальній висоті тексту, а не вгадується по довжині:
 * рядки переносяться по-різному на різних екранах.
 */
export function CatalogCard({ name, icon, color, description, features, priceMain, priceNote, href, photoUrl, badge }: {
  name: string; icon: string; color: string; description: string; features: string[];
  priceMain: string; priceNote: string; href: string; photoUrl?: string | null; badge?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const body = useRef<HTMLDivElement>(null);
  const showPhoto = Boolean(photoUrl) && !imgFailed;
  const tag = badgeLabel(badge);

  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const check = () => setCut(el.scrollHeight > el.clientHeight + 4);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [showPhoto]);

  return (
    <div className={`card cat-card${showPhoto ? " has-photo" : ""}${open ? "" : " is-closed"}`}>
      {showPhoto && (
        <div className="cat-card-photo">
          <img src={photoUrl!} alt="" onError={() => setImgFailed(true)} />
          {tag && <span className={badgeClass(badge)}>{tag}</span>}
        </div>
      )}

      <div className="brand">
        {!showPhoto && (
          <ServiceIcon slug={icon} color={color} letter={name.charAt(0)} size={30} />
        )}
        <h3>{name}</h3>
      </div>
      {!showPhoto && tag && <span className={badgeClass(badge)} style={{ alignSelf: "flex-start", marginBottom: 10 }}>{tag}</span>}

      <div ref={body} className={open ? "cb" : "cb cb-cut"}>
        {description && <ProductDescription text={description} className="prose-desc prose-desc-compact" />}
        {features.length > 0 && (
          <div className="feat">
            {features.map((f, i) => <span key={i}><i>✓</i> {f}</span>)}
          </div>
        )}
      </div>

      <div className="cb-toggle">
        {(cut || open) && (
          <button className="more-btn" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? "Згорнути" : "Ще"}
            <svg viewBox="0 0 24 24" className={open ? "up" : ""}>
              <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.4"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>

      <div className="price">
        <b>{priceMain}</b>
        <small>{priceNote}</small>
      </div>

      <Link className="btn sm block cat-card-btn" href={href}>
        Оформити<span className="dot"><Arrow /></span>
      </Link>
    </div>
  );
}
