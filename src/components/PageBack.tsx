"use client";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { BackArrow } from "./Logo";

function backHref(pathname: string, cat: string | null): string | null {
  if (!pathname || pathname === "/") return null;
  if (pathname.startsWith("/buy/")) return cat ? `/catalog?cat=${encodeURIComponent(cat)}` : "/catalog";
  if (pathname.startsWith("/order/")) return "/catalog";
  if (pathname === "/catalog") return cat ? "/catalog" : "/";
  if (pathname.startsWith("/admin")) return pathname === "/admin" ? "/" : "/admin";
  return "/";
}

export function PageBack({ className = "" }: { className?: string }) {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const href = backHref(pathname, searchParams.get("cat"));
  if (!href) return null;

  return (
    <Link href={href} className={`page-back${className ? ` ${className}` : ""}`} aria-label="Назад">
      <BackArrow />
    </Link>
  );
}
