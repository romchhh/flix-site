"use client";
import { useState } from "react";

/**
 * Логотип сервісу.
 *
 * Картинка показується одразу, а літера-замінник зʼявляється лише коли
 * зображення не завантажилось. Навпаки робити не можна: при гідратації
 * onLoad часто встигає спрацювати до того, як React навісить обробник,
 * і тоді іконка лишається схованою назавжди.
 */
export function ServiceIcon({ slug, color, letter, size = 34 }:
  { slug?: string | null; color: string; letter: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  const src = slug ? `/api/icon/${slug}?c=${color.replace("#", "")}` : null;
  const showLetter = !src || failed;

  return (
    <span
      className="ic"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.44,
        background: showLetter ? color : "transparent",
        borderRadius: showLetter ? 10 : 0,
      }}
      role="img"
      aria-label={letter}
    >
      {showLetter ? letter : (
        <img
          src={src!}
          alt=""
          width={size}
          height={size}
          onError={() => setFailed(true)}
          style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
        />
      )}
    </span>
  );
}
