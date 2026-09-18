/**
 * Рендерить правовий текст із простого формату:
 *  «1. Заголовок» на окремому рядку — розділ,
 *  рядок із «• » — пункт списку,
 *  решта — абзаци.
 *
 * Так текст лишається звичайним текстом: правити його можна не чіпаючи розмітку.
 */
export function LegalText({ raw }: { raw: string }) {
  const lines = raw.trim().split("\n").map((l) => l.trim());
  const out: React.ReactNode[] = [];
  let bullets: string[] = [];

  const flush = () => {
    if (!bullets.length) return;
    out.push(<ul key={`u${out.length}`}>{bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>);
    bullets = [];
  };

  lines.forEach((line, i) => {
    if (!line) return;

    if (line.startsWith("• ")) {
      bullets.push(line.slice(2));
      return;
    }
    flush();

    if (/^\d{1,2}\.\s+\D/.test(line) && line.length < 90) {
      out.push(<h2 key={i}>{line}</h2>);
      return;
    }

    out.push(<p key={i}>{line}</p>);
  });

  flush();
  return <>{out}</>;
}
