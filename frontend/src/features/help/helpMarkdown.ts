// The guide's Markdown vocabulary, deliberately small: no HTML is parsed and React escapes all text.
//   ## Heading / ### Subheading
//   1. numbered step          - bullet
//   > A note. Lines starting with ">" form one note; "> **Who can do this:** ..." leads with a label.
//   ![Screenshot: what it shows](screenshot:key)   on its own line: a placeholder until P16
//   **bold**, `a label or command`, [another article](help:section/slug), [a site](https://...)

export type HelpInline =
  | { kind: "text" | "strong" | "code"; text: string }
  | { kind: "article"; text: string; target: string }
  | { kind: "external"; text: string; url: string };

export type HelpBlock =
  | { kind: "heading"; level: 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "note"; text: string }
  | { kind: "steps"; items: string[] }
  | { kind: "bullets"; items: string[] }
  | { kind: "screenshot"; alt: string; key: string };

const SCREENSHOT = /^!\[([^\]]+)\]\(screenshot:([a-z0-9-]+)\)$/;

export function parseHelpBlocks(body: string): HelpBlock[] {
  const blocks: HelpBlock[] = [];
  const lines = body.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;
  const collect = (test: (line: string) => boolean, strip: (line: string) => string) => {
    const items: string[] = [];
    while (index < lines.length && test(lines[index].trim())) items.push(strip(lines[index++].trim()));
    return items;
  };
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index++; continue; }
    const heading = /^(#{2,3})\s+(.+)$/.exec(line);
    const shot = SCREENSHOT.exec(line);
    if (heading) { blocks.push({ kind: "heading", level: heading[1].length as 2 | 3, text: heading[2] }); index++; }
    else if (shot) { blocks.push({ kind: "screenshot", alt: shot[1], key: shot[2] }); index++; }
    else if (/^\d+\.\s/.test(line)) blocks.push({ kind: "steps", items: collect(item => /^\d+\.\s/.test(item), item => item.replace(/^\d+\.\s+/, "")) });
    else if (/^-\s/.test(line)) blocks.push({ kind: "bullets", items: collect(item => /^-\s/.test(item), item => item.slice(2)) });
    else if (line.startsWith(">")) blocks.push({ kind: "note", text: collect(item => item.startsWith(">"), item => item.replace(/^>\s?/, "")).join(" ") });
    else blocks.push({ kind: "paragraph", text: collect(item => Boolean(item) && !/^(#{2,3}\s|\d+\.\s|-\s|>)/.test(item) && !SCREENSHOT.test(item), item => item).join(" ") });
  }
  return blocks;
}

function safeExternal(url: string) {
  try { return new URL(url).protocol === "https:" ? url : null; } catch { return null; }
}

export function parseHelpInline(text: string): HelpInline[] {
  const parts: HelpInline[] = [];
  const pattern = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) parts.push({ kind: "text", text: text.slice(cursor, match.index) });
    const [, strong, code, label, target] = match;
    if (strong) parts.push({ kind: "strong", text: strong });
    else if (code) parts.push({ kind: "code", text: code });
    else if (target.startsWith("help:")) parts.push({ kind: "article", text: label, target: target.slice(5) });
    else {
      const url = safeExternal(target);
      parts.push(url ? { kind: "external", text: label, url } : { kind: "text", text: label });
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) parts.push({ kind: "text", text: text.slice(cursor) });
  return parts;
}

/** Every `help:` link target in a body, for the deep-link guard test. */
export function helpLinkTargets(body: string): string[] {
  return [...body.matchAll(/\]\(help:([^)\s]+)\)/g)].map(match => match[1]);
}
