"use client";
import { useEffect } from "react";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Підтвердити",
  cancelLabel = "Скасувати",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape" && !busy) onCancel(); };
    document.addEventListener("keydown", esc);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", esc);
      document.body.style.overflow = "";
    };
  }, [open, busy, onCancel]);

  if (!open) return null;

  return (
    <div className="dlg-backdrop" role="presentation" onClick={busy ? undefined : onCancel}>
      <div
        className="dlg-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dlg-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`dlg-icon${danger ? " danger" : ""}`} aria-hidden="true">
          {danger ? "!" : "?"}
        </div>
        <h3 id="dlg-title">{title}</h3>
        <p>{message}</p>
        <div className="dlg-acts">
          <button type="button" className="btn soft" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`btn sm${danger ? " danger" : ""}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Зачекай…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
