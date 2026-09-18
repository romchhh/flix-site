export type QA = { q: string; a: string };

/** Розбір тексту з адмінки: блоки через порожній рядок, перший рядок — питання */
export function parseFaq(raw: string): QA[] {
  return raw
    .split(/\n\s*\n/)
    .map((block) => block.split("\n").filter((l) => l.trim()))
    .filter((lines) => lines.length >= 2)
    .map((lines) => ({ q: lines[0].trim(), a: lines.slice(1).join(" ").trim() }));
}
