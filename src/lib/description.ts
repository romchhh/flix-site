export type DescriptionBlock =
  | { type: "p"; text: string }
  | { type: "list"; items: string[] };

const BULLET_RE = /^[•*\-–—✓]\s*/;

/** Сторінка товару: короткий лід + пункти з галочками. */
export function splitProductCopy(raw: string): { lede: string; features: string[] } {
  const text = (raw || "").replace(/\r\n/g, "\n").trim();
  if (!text) return { lede: "", features: [] };

  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const bulletLines = lines.filter((l) => BULLET_RE.test(l));
  if (bulletLines.length) {
    return {
      lede: lines.filter((l) => !BULLET_RE.test(l)).join(" ").trim(),
      features: bulletLines.map((l) => l.replace(BULLET_RE, "").trim()),
    };
  }

  if (text.includes("•")) {
    const parts = text.split(/\s*•\s*/).map((s) => s.trim()).filter(Boolean);
    if (parts.length > 1) {
      return { lede: parts[0], features: parts.slice(1) };
    }
  }

  if (/\s\*\s+/.test(text)) {
    const parts = text.split(/\s*\*\s+/).map((s) => s.trim()).filter(Boolean);
    if (parts.length > 1) {
      return { lede: parts[0], features: parts.slice(1) };
    }
  }

  const paragraphs = text.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  if (paragraphs.length > 1) {
    return {
      lede: paragraphs[0].replace(/\s+/g, " "),
      features: paragraphs.slice(1).map((p) => p.replace(/\s+/g, " ")),
    };
  }

  const important = text.match(/^(.+?)(\s+Важливо:\s*.+)$/i);
  if (important) {
    const head = important[1].trim();
    const tail = important[2].trim();
    const inline = head.split(/\s*•\s*/);
    if (inline.length > 1) {
      return { lede: inline[0], features: [...inline.slice(1), tail] };
    }
    return { lede: head, features: [tail] };
  }

  return { lede: text.replace(/\s+/g, " "), features: [] };
}

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
