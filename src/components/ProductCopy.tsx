import { splitProductCopy } from "@/lib/description";

/** Сторінка товару: міні-опис + деталі з галочками. */
export function ProductCopy({
  description,
  features = "",
  className = "",
}: {
  description: string;
  features?: string;
  className?: string;
}) {
  const { lede, features: fromDesc } = splitProductCopy(description);
  const extra = features
    .split("\n")
    .map((f) => f.trim())
    .filter(Boolean);
  const items = [...fromDesc, ...extra];

  if (!lede && !items.length) return null;

  return (
    <div className={`product-copy${className ? ` ${className}` : ""}`}>
      {lede && <p className="p-lede">{lede}</p>}
      {items.length > 0 && (
        <div className="feat product-feat">
          {items.map((f, i) => (
            <span key={i}><i>✓</i> {f}</span>
          ))}
        </div>
      )}
    </div>
  );
}
