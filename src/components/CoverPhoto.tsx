"use client";
import { useState } from "react";

/** Фото з API; якщо файлу немає — показує запасний варіант. */
export function CoverPhoto({ src, className, alt = "", fallback }: {
  src?: string | null; className?: string; alt?: string; fallback: React.ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <>{fallback}</>;
  return <img src={src} alt={alt} className={className} onError={() => setFailed(true)} />;
}
