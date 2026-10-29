/**
 * Worker-side checks before a KiCad file reaches the renderer, which parses on the main thread.
 * Only shape is checked here: strict UTF-8, the size bound, the KiCad 6+ header, balanced
 * s-expressions (quotes respected) and a token budget, so pathological input never freezes the page.
 */
export const KICAD_PREVIEW_MAX_BYTES = 10 * 1024 ** 2;
export const KICAD_TOKEN_BUDGET = 2_000_000;
export type KicadVariant = "pcb" | "sch";
export type KicadChecked = { text: string; variant: KicadVariant };

const VARIANTS: Record<string, KicadVariant> = { kicad_pcb: "pcb", kicad_sch: "sch" };

export function kicadVariant(extension: string): KicadVariant | null {
  return VARIANTS[extension] ?? null;
}

export function checkKicad(buffer: ArrayBuffer, extension: string, budget = KICAD_TOKEN_BUDGET): KicadChecked {
  const variant = kicadVariant(extension);
  if (!variant) throw new Error("Not a previewable KiCad file.");
  if (!buffer.byteLength || buffer.byteLength > KICAD_PREVIEW_MAX_BYTES) throw new Error("KiCad preview size limit.");
  const text = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(buffer);
  if (!new RegExp(`^\\s*\\(kicad_${variant}\\s`).test(text)) throw new Error("Not a KiCad 6 or later file.");
  let depth = 0, tokens = 0, closed = false, atom = false, quoted = false, escaped = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === "\"") quoted = false;
      continue;
    }
    const space = c === " " || c === "\n" || c === "\r" || c === "\t";
    if (closed && !space) throw new Error("Content after the KiCad document.");
    if (c === "(" || c === ")" || c === "\"") {
      atom = false;
      if (++tokens > budget) throw new Error("KiCad preview token limit.");
      if (c === "\"") quoted = true;
      else if (c === "(") depth++;
      else if (--depth < 0) throw new Error("Unbalanced KiCad file.");
      else if (depth === 0) closed = true;
    } else if (space) atom = false;
    else if (!atom) {
      atom = true;
      if (++tokens > budget) throw new Error("KiCad preview token limit.");
    }
  }
  if (quoted || depth !== 0 || !closed) throw new Error("Unbalanced KiCad file.");
  return { text, variant };
}
