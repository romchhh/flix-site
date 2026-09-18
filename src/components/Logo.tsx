import Link from "next/link";

export function Logo({ size = 24, tag = "підписки, які просто працюють", inv = false }:
  { size?: number; tag?: string | null; inv?: boolean }) {
  return (
    <Link className={`fm${inv ? " inv" : ""}`} href="/" style={{ fontSize: size }}>
      <span className="fm-play">
        <svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z" /></svg>
      </span>
      <span className="fm-txt">
        <span className="fm-name">flixмаркет</span>
        {tag && <span className="fm-tag">{tag}</span>}
      </span>
    </Link>
  );
}

export const TgIcon = () => (
  <svg viewBox="0 0 24 24"><path d="M9.8 16.1 9.6 20c.4 0 .6-.2.8-.4l2-1.9 4.1 3c.8.4 1.3.2 1.5-.7l2.7-12.6c.2-1-.4-1.5-1.1-1.2L3.4 10.5c-1 .4-1 .9-.2 1.2l4.2 1.3 9.7-6.1c.5-.3.9-.1.5.2z" /></svg>
);

export const Arrow = () => (
  <svg className="arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
);

export const BackArrow = () => (
  <svg className="arrow" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M19 12H5M11 6l-6 6 6 6" fill="none" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Chevron = () => (
  <svg className="arrow" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6" /></svg>
);
