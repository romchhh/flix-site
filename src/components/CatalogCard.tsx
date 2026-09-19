"use client";
import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { ServiceIcon } from "./ServiceIcon";
import { Arrow } from "./Logo";
import { badgeClass, badgeLabel } from "@/lib/display";
import { ProductCopy } from "./ProductCopy";

/**
 * Картка каталогу — увесь клік веде на сторінку товару.
 * «Ще» показується, коли опис обрізаний, і теж відкриває сторінку товару.
 */
export function CatalogCard({ name, icon, color, description, features, priceMain, priceNote, href, photoUrl, badge }: {
  name: string; icon: string; color: string; description: string; features: string;
  priceMain: string; priceNote: string; href: string; photoUrl?: string | null; badge?: string | null;
}) {
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
  }, [showPhoto, description, features]);

  return (
    <Link href={href} className={`card cat-card is-closed${showPhoto ? " has-photo" : ""}`}>
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

      <div ref={body} className="cb cb-cut">
        <ProductCopy description={description} features={features} className="cat-card-copy" />
      </div>

      <div className="cb-toggle">
        {cut && (
          <span className="more-btn" aria-hidden="true">
            Ще
            <svg viewBox="0 0 24 24">
              <path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2.4"
                strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        )}
      </div>

      <div className="price">
        <b>{priceMain}</b>
        <small>{priceNote}</small>
      </div>

      <span className="btn sm block cat-card-btn">
        Оформити<span className="dot"><Arrow /></span>
      </span>
    </Link>
  );
}
