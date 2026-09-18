"use client";
import { useState } from "react";
import { ServiceIcon } from "@/components/ServiceIcon";
import { productPhotoUrl } from "@/lib/display";

export function SubPhoto({
  name,
  icon,
  color,
  photoUrl,
  productId,
  size = 48,
}: {
  name: string;
  icon: string;
  color: string;
  photoUrl?: string | null;
  productId?: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const src = productPhotoUrl(photoUrl, productId);
  const show = Boolean(src) && !failed;

  return (
    <aside className="sub-media" aria-hidden={!show}>
      {show ? (
        <img
          className="sub-photo-fit"
          src={src!}
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        <div
          className="sub-media-fallback"
          style={{ background: `linear-gradient(145deg, ${color}18 0%, ${color}36 100%)` }}
        >
          <ServiceIcon slug={icon} color={color} letter={name.charAt(0)} size={size} />
        </div>
      )}
    </aside>
  );
}
