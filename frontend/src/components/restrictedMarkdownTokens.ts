export type MarkdownToken = { kind: "text" | "strong"; text: string } | { kind: "link"; text: string; url: string };

function safeTarget(value: string) {
  if (value.length > 500 || !/^https?:\/\//i.test(value) || /[\u0000-\u0020\u007f]/.test(value)) return false;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password
      && !/[\u0000-\u0020\u007f]/.test(decodeURIComponent(value));
  } catch { return false; }
}

/** Small bounded tokenizer shared by all public/preview surfaces. No HTML parser or remote content. */
export function markdownInlineTokens(text: string): MarkdownToken[] {
  const tokens: MarkdownToken[] = [];
  let literal = ""; let cursor = 0;
  const emit = (token: MarkdownToken) => { if (literal) { tokens.push({ kind: "text", text: literal }); literal = ""; } tokens.push(token); };
  while (cursor < text.length) {
    if (text.startsWith("**", cursor)) {
      const end = text.indexOf("**", cursor + 2);
      const body = end >= 0 ? text.slice(cursor + 2, end) : "";
      if (body && !/[\n*]/.test(body)) { emit({ kind: "strong", text: body }); cursor = end + 2; continue; }
    }
    if (text[cursor] === "[" && text[cursor - 1] !== "!") {
      const labelEnd = text.indexOf("](", cursor + 1);
      const label = labelEnd >= 0 ? text.slice(cursor + 1, labelEnd) : "";
      if (label && label.length <= 200 && !/[\n\[\]]/.test(label)) {
        const start = labelEnd + 2;
        let end = start; let depth = 0;
        while (end < text.length && end - start <= 500 && !/\s/.test(text[end])) {
          if (text[end] === "(" && ++depth > 8) break;
          if (text[end] === ")") { if (depth === 0) break; depth--; }
          end++;
        }
        const url = text.slice(start, end);
        if (text[end] === ")" && depth === 0 && safeTarget(url)) {
          emit({ kind: "link", text: label, url }); cursor = end + 1; continue;
        }
      }
    }
    literal += text[cursor++];
  }
  if (literal) tokens.push({ kind: "text", text: literal });
  return tokens;
}

export function markdownExcerpt(text: string, policy?: "restricted" | "legacy_literal") {
  const plain = policy === "legacy_literal" ? text : markdownInlineTokens(text.replace(/^[-] /gm, "")).map(token => token.text).join("");
  return plain.replace(/\s+/g, " ").trim().slice(0, 300);
}
