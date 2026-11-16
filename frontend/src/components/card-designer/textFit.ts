// Shrink-to-fit for the on-screen card, mirroring apps/card_designs/rendering_text.py so
// the designer shows what prints: wrap at the design size and shrink in 0.5 pt steps
// until the lines fit the box (6 pt floor), but keep a short value such as a name on
// ONE line, down to 60 % of its size, whenever wrapping would have to shrink it anyway.

export const MIN_PT = 6;
export const ONE_LINE_FLOOR = 0.6;

export type FitStyle = { family: string; weight: number; sizePt: number; lineHeight: number; trackingPt: number;
  uppercase?: boolean; shrink: boolean };
export type Measure = (text: string, sizePt: number) => number; // width in pt

let context: CanvasRenderingContext2D | null | undefined;

/** A canvas measurer for one family/weight; widths in points (1 CSS px is treated as 1 pt). */
export function canvasMeasure(style: Pick<FitStyle, "family" | "weight" | "trackingPt">): Measure | null {
  if (context === undefined) {
    try {
      context = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
    } catch { context = null; }
  }
  const ctx = context;
  if (!ctx) return null;
  return (text, sizePt) => {
    ctx.font = `${style.weight} ${sizePt}px "${style.family}", sans-serif`;
    return ctx.measureText(text).width + Math.max(0, [...text].length - 1) * style.trackingPt;
  };
}

export function wrap(text: string, sizePt: number, boxWidth: number, measure: Measure) {
  const lines: string[] = [];
  for (const paragraph of text.split("\n")) {
    let line = "";
    for (const word of paragraph.split(" ")) {
      const candidate = line ? `${line} ${word}` : word;
      if (measure(candidate, sizePt) <= boxWidth) { line = candidate; continue; }
      if (line) lines.push(line);
      line = "";
      for (const char of [...word]) {
        if (line && measure(line + char, sizePt) > boxWidth) { lines.push(line); line = ""; }
        line += char;
      }
    }
    lines.push(line);
  }
  return lines;
}

/** -> the size to draw at, and whether the text must stay on one line. Box sizes are in points. */
export function fitText(text: string, style: FitStyle, boxWidth: number, boxHeight: number, measure: Measure | null) {
  const value = style.uppercase ? text.toUpperCase() : text;
  if (!measure || !value) return { sizePt: style.sizePt, oneLine: false };
  let size = style.sizePt;
  let lines = wrap(value, size, boxWidth, measure);
  while (style.shrink && size > MIN_PT && lines.length * size * style.lineHeight > boxHeight) {
    size = Math.max(MIN_PT, size - 0.5);
    lines = wrap(value, size, boxWidth, measure);
  }
  if (lines.length > 1 && style.shrink && !value.includes("\n")) {
    const floor = Math.max(MIN_PT, style.sizePt * ONE_LINE_FLOOR);
    for (let single = style.sizePt; single >= floor - 0.001; single -= 0.25) {
      if (single * style.lineHeight <= boxHeight + 0.01 && measure(value, single) <= boxWidth) {
        return single >= size ? { sizePt: single, oneLine: true } : { sizePt: size, oneLine: false };
      }
    }
  }
  return { sizePt: size, oneLine: lines.length === 1 };
}
