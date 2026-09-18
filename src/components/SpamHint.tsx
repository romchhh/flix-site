/**
 * Підказка про спам.
 * Просити натиснути «Не спам» важливіше, ніж просто сказати «перевір теку»:
 * інакше наступні листи — код підтвердження, скидання пароля — теж губитимуться.
 */
export function SpamHint({ compact = false }: { compact?: boolean }) {
  return (
    <p className={compact ? "spam-hint compact" : "spam-hint"}>
      <span className="spam-ico" aria-hidden>✉</span>
      <span>
        Лист може потрапити в теку «Спам». Якщо знайдеш його там — натисни{" "}
        <b>«Не спам»</b>, щоб наступні листи приходили нормально.
      </span>
    </p>
  );
}
