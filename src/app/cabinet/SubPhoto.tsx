"use client";
import { useState, type ReactNode } from "react";
import { ServiceIcon } from "@/components/ServiceIcon";
import { productPhotoUrl } from "@/lib/display";

export function SubPhoto({
  name,
  icon,
  color,
  photoUrl,
  productId,
  size = 48,
  badge,
  variant = "card",
}: {
  name: string;
  icon: string;
  color: string;
  photoUrl?: string | null;
  productId?: string;
  size?: number;
  badge?: ReactNode;
  variant?: "card" | "row";
}) {
  const [failed, setFailed] = useState(false);
  const src = productPhotoUrl(photoUrl, productId);
  const show = Boolean(src) && !failed;

  if (variant === "row") {
    if (show) {
      return <img className="sub-row-thumb" src={src!} alt="" onError={() => setFailed(true)} />;
    }
    return (
      <div
        className="sub-row-thumb sub-row-thumb-fallback"
        style={{ background: `linear-gradient(145deg, ${color}28 0%, ${color}50 100%)` }}
      >
        <ServiceIcon slug={icon} color={color} letter={name.charAt(0)} size={size} />
      </div>
    );
  }

  return (
    <div className="cat-card-photo sub-card-photo">
      {show ? (
        <img src={src!} alt="" onError={() => setFailed(true)} />
      ) : (
        <div
          className="sub-media-fallback"
          style={{ background: `linear-gradient(145deg, ${color}22 0%, ${color}44 100%)` }}
        >
          <ServiceIcon slug={icon} color={color} letter={name.charAt(0)} size={size} />
        </div>
      )}
      {badge}
    </div>
  );
}
