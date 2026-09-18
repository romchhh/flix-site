export type DescriptionBlock =
  | { type: "p"; text: string }
  | { type: "list"; items: string[] };

/** Розбиває опис на абзаци й списки для читабельного виводу. */
export function parseDescription(raw: string): DescriptionBlock[] {
  let text = (raw || "").replace(/\r\n/g, "\n").trim();
  if (!text) return [];

  if (!text.includes("\n")) {
    text = text
      .replace(/\s+(Що входить:)/g, "\n\n$1")
      .replace(/\s+(Важливо:)/gi, "\n\n$1")
      .replace(/\s+•\s+/g, "\n• ");
  }

  const paragraphs = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const blocks: DescriptionBlock[] = [];

  for (const paragraph of paragraphs) {
    const lines = paragraph.split("\n").map((l) => l.trim()).filter(Boolean);
    const bulletLines = lines.filter((l) => /^[•\-–—*✓]\s*/.test(l));

    if (lines.length > 1 && bulletLines.length >= Math.max(1, lines.length - 1)) {
      blocks.push({
        type: "list",
        items: lines.map((l) => l.replace(/^([•\-–—*✓]\s*)/, "").trim()),
      });
      continue;
    }

    if (paragraph.includes("•") && !paragraph.includes("\n")) {
      const [head, ...tail] = paragraph.split(/\s*•\s*/).map((s) => s.trim()).filter(Boolean);
      if (tail.length) {
        if (head) blocks.push({ type: "p", text: head });
        blocks.push({ type: "list", items: tail });
        continue;
      }
    }

    blocks.push({ type: "p", text: lines.join(" ") });
  }

  return blocks.length ? blocks : [{ type: "p", text }];
}
