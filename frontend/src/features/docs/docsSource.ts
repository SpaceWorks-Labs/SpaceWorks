// Pure Markdown helpers shared by the build-time docs index (scripts/docs-plugin.ts) and the
// in-app renderer, so a heading's search link and its rendered anchor always agree.
// No DOM and no Node APIs here: this file runs in both places.

export type FrontMatter = Record<string, string>;

const FRONT = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/;

function unquote(value: string) {
  const trimmed = value.trim();
  const quoted = /^(["'])(.*)\1$/.exec(trimmed);
  return quoted ? quoted[2] : trimmed;
}

/** Flat `key: value` YAML front matter: the only shape the docs use (title, group, order, summary, updated). */
export function parseFrontMatter(raw: string): { data: FrontMatter; body: string } {
  const text = raw.replace(/^\uFEFF/, "");
  const match = FRONT.exec(text);
  if (!match) return { data: {}, body: text };
  const data: FrontMatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    const colon = line.indexOf(":");
    if (colon > 0 && !/^\s/.test(line)) data[line.slice(0, colon).trim()] = unquote(line.slice(colon + 1));
  }
  return { data, body: text.slice(match[0].length) };
}

/** The body the renderer shows: front matter removed and the leading `# Title` dropped (the page prints its own h1). */
export function articleBody(raw: string) {
  const { body } = parseFrontMatter(raw);
  return body.replace(/^\s*#\s+[^\n]*\n?/, "");
}

/** Visible text of an inline Markdown string: code ticks, links, images and emphasis removed. */
export function plainText(markdown: string) {
  return markdown
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, "")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(^|[^\w*])[*_]([^*_]+)[*_](?=[^\w*]|$)/g, "$1$2")
    .replace(/\\([\\`*_{}[\]()#+\-.!])/g, "$1")
    .trim();
}

/** GitHub-style anchor: lower case, punctuation dropped, spaces to hyphens. */
export function slugify(text: string) {
  return plainText(text).toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, "").trim().replace(/\s/g, "-");
}

/** Hands out unique anchors in document order, the way GitHub suffixes repeats (-1, -2…). */
export function createSlugger() {
  const seen = new Map<string, number>();
  return (text: string) => {
    const base = slugify(text) || "section";
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    return count ? `${base}-${count}` : base;
  };
}

/** Lines outside fenced code blocks, so a `# comment` inside a shell snippet is never a heading. */
function proseLines(body: string) {
  const lines: string[] = [];
  let fence: string | null = null;
  for (const line of body.split(/\r?\n/)) {
    const marker = /^\s{0,3}(`{3,}|~{3,})/.exec(line)?.[1];
    if (marker && (!fence || marker[0] === fence[0] && marker.length >= fence.length)) {
      fence = fence ? null : marker;
      continue;
    }
    if (!fence) lines.push(line);
  }
  return lines;
}

export function documentTitle(body: string) {
  const line = proseLines(body).find(item => /^#\s+\S/.test(item));
  return line ? plainText(line.replace(/^#\s+/, "").replace(/\s+#+\s*$/, "")) : "";
}

/** h2 and h3 headings with the anchors the renderer gives them (the h1 is skipped, as the renderer drops it). */
export function extractHeadings(body: string) {
  const next = createSlugger();
  const headings: { depth: 2 | 3; text: string; id: string }[] = [];
  for (const line of proseLines(articleBody(body))) {
    const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (!match) continue;
    const id = next(match[2]);
    if (match[1].length === 2 || match[1].length === 3) {
      headings.push({ depth: match[1].length as 2 | 3, text: plainText(match[2]), id });
    }
  }
  return headings;
}

/** First prose paragraph, flattened, for pages without a `summary`. */
export function firstParagraph(body: string) {
  const paragraph: string[] = [];
  for (const line of proseLines(articleBody(body))) {
    const trimmed = line.trim();
    if (!trimmed) { if (paragraph.length) break; continue; }
    if (/^(#|>|[-*+]\s|\d+\.\s|\||<|!\[)/.test(trimmed)) { if (paragraph.length) break; continue; }
    paragraph.push(trimmed);
  }
  const text = plainText(paragraph.join(" "));
  return text.length > 220 ? `${text.slice(0, 217).replace(/\s+\S*$/, "")}…` : text;
}
