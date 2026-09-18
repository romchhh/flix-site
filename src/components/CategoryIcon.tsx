"use client";
import { useState } from "react";

/** Slug Simple Icons — латиниця, цифри, крапка й дефіс. Усе інше вважаємо емодзі. */
const isSlug = (v: string) => /^[a-z0-9.-]{2,40}$/.test(v);

export function CategoryIcon({ icon, color, size = 18 }:
  { icon: string; color: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (!icon) return null;

  if (!isSlug(icon) || failed) {
    return <span style={{ fontSize: size, lineHeight: 1 }} aria-hidden>{icon}</span>;
  }

  return (
    <img
      src={`/api/icon/${icon}?c=${color.replace("#", "")}`}
      alt=""
      width={size}
      height={size}
      onError={() => setFailed(true)}
      style={{ width: size, height: size, objectFit: "contain", display: "block" }}
    />
  );
}
