/**
 * Text edits for the broadcast toolbar (parity E-F3, B21). Each returns the new text and the selection to
 * restore, so the textarea stays the single source of truth and Undo in the browser keeps working.
 * Only the server's safe subset is produced: emphasis, `#`-`###` headings, `>` quotes, `-` and `1.` lists,
 * and `[label](https://... | mailto:... | {{ placeholder }})` links.
 */
export type TextEdit = { text: string; start: number; end: number };

export function wrapSelection(text: string, start: number, end: number, marker: string, fallback: string): TextEdit {
  const chosen = text.slice(start, end) || fallback;
  const before = text.slice(0, start), after = text.slice(end);
  if (before.endsWith(marker) && after.startsWith(marker)) {  // toggling off
    return { text: before.slice(0, -marker.length) + chosen + after.slice(marker.length), start: start - marker.length, end: start - marker.length + chosen.length };
  }
  return { text: before + marker + chosen + marker + after, start: start + marker.length, end: start + marker.length + chosen.length };
}

const LINE_PREFIX = /^(#{1,3} |> |- |\d+\. )/;

/** Put `prefix` at the start of every selected line (numbered lists count up); applying it again removes it. */
export function prefixLines(text: string, start: number, end: number, prefix: "# " | "## " | "### " | "> " | "- " | "1. "): TextEdit {
  const lineStart = text.lastIndexOf("\n", start - 1) + 1;
  const nextBreak = text.indexOf("\n", end);
  const lineEnd = nextBreak === -1 ? text.length : nextBreak;
  const lines = text.slice(lineStart, lineEnd).split("\n");
  const matches = (line: string) => prefix === "1. " ? /^\d+\. /.test(line) : line.startsWith(prefix);
  const removing = lines.every(line => !line.trim() || matches(line));
  let number = 0;
  const changed = lines.map(line => {
    if (!line.trim()) return line;
    const bare = line.replace(LINE_PREFIX, "");
    if (removing) return bare;
    number += 1;
    return (prefix === "1. " ? `${number}. ` : prefix) + bare;
  }).join("\n");
  return { text: text.slice(0, lineStart) + changed + text.slice(lineEnd), start: lineStart, end: lineStart + changed.length };
}

export function insertAt(text: string, start: number, end: number, value: string): TextEdit {
  const caret = start + value.length;
  return { text: text.slice(0, start) + value + text.slice(end), start: caret, end: caret };
}

export const LINK_PLACEHOLDERS = ["event_url", "ticket_url", "schedule_url", "feedback_url"] as const;
export const TEXT_PLACEHOLDERS = ["name", "event_title", "event_date", "event_location", "organization"] as const;

/** A link target the server accepts: https, mailto, or one of the link placeholders. */
export function linkTargetOk(target: string) {
  if ((LINK_PLACEHOLDERS as readonly string[]).some(key => target === `{{ ${key} }}`)) return true;
  if (/^mailto:[^\s@]+@[^\s@]+\.[^\s@]+$/.test(target)) return true;
  try { const url = new URL(target); return url.protocol === "https:" && !url.username && !url.password; } catch { return false; }
}

export function linkMarkdown(label: string, target: string) {
  return `[${label.replace(/[[\]\n]/g, "").slice(0, 80)}](${target})`;
}
