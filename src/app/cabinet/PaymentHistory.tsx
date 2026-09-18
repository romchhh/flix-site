"use client";
import { useState } from "react";
import { dateTimeUk, payStatusLabel } from "@/lib/display";
import type { BillingEntry } from "@/lib/types";

function statusClass(status: string) {
  const s = status.toLowerCase();
  if (s === "success") return "pay-ok";
  if (s === "failed" || s === "error") return "pay-bad";
  if (s === "processing" || s === "pending") return "pay-wait";
  return "";
}

export function PaymentHistory({
  items,
  title = "Історія платежів",
  limit = 6,
  compact = false,
}: {
  items: BillingEntry[];
  title?: string;
  limit?: number;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;

  const shown = open ? items : items.slice(0, limit);
  const hasMore = items.length > limit;

  return (
    <div className={`pay-history${compact ? " compact" : ""}`}>
      {title && (
        <div className="pay-history-head">
          <b>{title}</b>
          <small>{items.length} запис{items.length === 1 ? "" : items.length < 5 ? "и" : "ів"}</small>
        </div>
      )}
      <ul className="pay-list">
        {shown.map((p) => {
          const dt = p.createdAt ? new Date(p.createdAt) : null;
          const when = dt && !Number.isNaN(dt.getTime()) ? dateTimeUk(dt) : "—";
          return (
            <li key={p.id} className="pay-row">
              <div className="pay-main">
                <span className="pay-name">{p.productName}</span>
                <span className="pay-meta">
                  {p.kind === "charge" ? "Автосписання" : "Покупка"}
                  {p.invoiceId ? ` · ${p.invoiceId.slice(0, 12)}…` : ""}
                </span>
              </div>
              <div className="pay-side">
                <span className="pay-amt">{p.amount}₴</span>
                <span className={`pay-st ${statusClass(p.status)}`}>{payStatusLabel(p.status)}</span>
                <span className="pay-when">{when}</span>
              </div>
            </li>
          );
        })}
      </ul>
      {hasMore && (
        <button type="button" className="pay-more" onClick={() => setOpen(!open)}>
          {open ? "Згорнути" : `Ще ${items.length - limit}`}
        </button>
      )}
      {items.some((p) => p.errorMessage) && open && (
        <p className="pay-note">Невдалі списання повторюються автоматично або після звернення до менеджера.</p>
      )}
    </div>
  );
}
