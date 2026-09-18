import { parseDescription } from "@/lib/description";

export function ProductDescription({
  text,
  className = "prose-desc",
}: {
  text: string;
  className?: string;
}) {
  const blocks = parseDescription(text);
  if (!blocks.length) return null;

  return (
    <div className={className}>
      {blocks.map((block, i) => {
        if (block.type === "list") {
          return (
            <ul key={i}>
              {block.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          );
        }
        return <p key={i}>{block.text}</p>;
      })}
    </div>
  );
}
