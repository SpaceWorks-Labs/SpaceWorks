// Rich-text layout for the Card Studio: the TypeScript twin of apps/card_designs/rendering_rich.py `plan()`
// (decision 314, spec section 5), checked against the golden fixtures. Pure and measure-injected so tests run
// without a canvas. All plan values are in POINTS relative to the layer box, exactly like the server's plan.
import type { Highlight, Layer, Span, TextStroke, Underline } from "./cardTypes";
import { PT_TO_MM } from "./cardGeometry";
import { merge } from "./dataFields";

export const MIN_PT = 6;
export const ONE_LINE_FLOOR = 0.6;
export const ASCENT = 0.9;
export const DESCENT = 0.25;
export const PT_PER_MM = 1 / PT_TO_MM;

/** A span after translation, merge tags and uppercase. */
export type RichSpan = { text: string; family: string; weight: number; colour: string; size: number; tracking: number };
/** Width in points of `text` set in `span` at `sizePt`, WITHOUT letter-spacing (the plan adds that per character). */
export type MeasureText = (text: string, span: RichSpan, sizePt: number) => number;
export type PlanPart = { text: string; span: number; x: number; width: number };
export type PlanLine = { baseline: number; x: number; width: number; size: number; parts: PlanPart[] };
export type RichPlan = { scale: number; lines: PlanLine[];
  bars: { x: number; y: number; w: number; h: number; radius: number }[];
  rules: { x: number; y: number; w: number; thickness: number }[] };
export type RichLayerStyle = { font_size_pt: number; line_height: number; align: "left" | "center" | "right";
  valign: "top" | "middle" | "bottom"; shrink_to_fit: boolean; highlight?: Highlight | null; underline?: Underline | null };

/** The layer's spans after translation, merge tags and uppercase (server `resolve`). */
export function resolveSpans(layer: Layer, values: Record<string, string>, locale?: string): RichSpan[] {
  const translated = locale ? layer.translations?.[locale] : undefined;
  const spans: Span[] = translated !== undefined ? [{ text: translated }] : layer.spans?.length ? layer.spans : [{ text: layer.text ?? "" }];
  return spans.map((span) => {
    const value = merge(span.text, values);
    const upper = span.uppercase ?? layer.uppercase ?? false;
    return { text: upper ? value.toUpperCase() : value, family: span.font_family || layer.font_family || "Outfit",
      weight: span.font_weight || layer.font_weight || 400, colour: span.colour || layer.colour || "#142C2A",
      size: span.size_pt || (layer.font_size_pt ?? 10) * (span.size_scale ?? 1),
      tracking: span.tracking_pt ?? layer.tracking_pt ?? 0 };
  });
}

type Unit = { kind: "word" | "space" | "break"; parts: { text: string; span: number }[] };
function units(spans: RichSpan[]): Unit[] {
  const out: Unit[] = [];
  let current: { text: string; span: number }[] = [];
  const flush = () => { if (current.length) { out.push({ kind: "word", parts: current }); current = []; } };
  spans.forEach((span, index) => {
    for (const piece of span.text.split(/( |\n)/)) {
      if (piece === "") continue;
      if (piece === " ") { flush(); out.push({ kind: "space", parts: [{ text: " ", span: index }] }); }
      else if (piece === "\n") { flush(); out.push({ kind: "break", parts: [] }); }
      else current.push({ text: piece, span: index });
    }
  });
  flush();
  return out;
}

type Placed = { text: string; span: number; width: number };
const length = (text: string) => [...text].length;

function layout(spans: RichSpan[], list: Unit[], scale: number, boxW: number, measure: MeasureText): Placed[][] {
  const lines: Placed[][] = [];
  let line: Placed[] = [];
  let used = 0;
  const close = () => {
    while (line.length && line[line.length - 1].text.trim() === "") line.pop();
    lines.push(line);
    line = []; used = 0;
  };
  for (const unit of list) {
    if (unit.kind === "break") { close(); continue; }
    const widths = unit.parts.map((part) => {
      const span = spans[part.span];
      return measure(part.text, span, span.size * scale) + length(part.text) * span.tracking;
    });
    const total = widths.reduce((sum, value) => sum + value, 0);
    if (unit.kind === "space") {
      if (line.length) { line.push({ text: " ", span: unit.parts[0].span, width: total }); used += total; }
      continue;
    }
    if (line.length && used + total > boxW + 0.01) close();
    unit.parts.forEach((part, index) => line.push({ text: part.text, span: part.span, width: widths[index] }));
    used += total;
  }
  close();
  return lines;
}

function metrics(lines: Placed[][], spans: RichSpan[], scale: number, lineHeight: number) {
  return lines.map((line) => {
    const size = line.length ? Math.max(...line.map((part) => spans[part.span].size * scale)) : spans[0].size * scale;
    let width = line.reduce((sum, part) => sum + part.width, 0);
    if (line.length) width -= spans[line[line.length - 1].span].tracking;  // the last glyph's tracking is not visible
    return { size, leading: size * lineHeight, width };
  });
}

const round = (value: number, places: number) => Math.round(value * 10 ** places) / 10 ** places;

/** Fit and lay out the spans in a box of `boxW` x `boxH` points. */
export function planRich(spans: RichSpan[], layer: RichLayerStyle, boxW: number, boxH: number, measure: MeasureText): RichPlan {
  const list = units(spans);
  const size0 = layer.font_size_pt;
  const smallest = Math.min(...spans.map((span) => span.size)) || size0;
  const floor = Math.min(1, Math.max(ONE_LINE_FLOOR, MIN_PT / smallest));
  const step = 0.5 / size0;
  let scale = 1;
  let lines = layout(spans, list, scale, boxW, measure);
  let rows = metrics(lines, spans, scale, layer.line_height);
  const stack = () => rows.reduce((sum, row) => sum + row.leading, 0);
  while (stack() > boxH + 0.01 && layer.shrink_to_fit && scale > floor + 1e-6) {
    scale = Math.max(floor, scale - step);
    lines = layout(spans, list, scale, boxW, measure);
    rows = metrics(lines, spans, scale, layer.line_height);
  }
  if (lines.length > 1 && layer.shrink_to_fit && !list.some((unit) => unit.kind === "break")) {
    for (let trial = 1; trial >= floor - 1e-6; trial -= step) {
      const one = layout(spans, list, trial, boxW, measure);
      const oneRows = metrics(one, spans, trial, layer.line_height);
      if (one.length === 1 && oneRows[0].leading <= boxH + 0.01 && oneRows[0].width <= boxW + 0.01) {
        if (trial >= scale) { lines = one; rows = oneRows; scale = trial; }
        break;
      }
    }
  }
  while (lines.length > 1 && stack() > boxH + 0.01) { lines.pop(); rows.pop(); }
  const block = stack();
  const start = Math.max(0, { top: 0, middle: (boxH - block) / 2, bottom: boxH - block }[layer.valign]);
  const plan: RichPlan = { scale: round(scale, 4), lines: [], bars: [], rules: [] };
  let cursor = start;
  lines.forEach((line, at) => {
    const row = rows[at];
    const baseline = cursor + row.size * ASCENT;
    const shift = { left: 0, center: (boxW - row.width) / 2, right: boxW - row.width }[layer.align];
    let x = shift;
    const parts = line.map((part) => { const placed = { text: part.text, span: part.span, x, width: part.width }; x += part.width; return placed; });
    plan.lines.push({ baseline, x: shift, width: row.width, size: row.size, parts });
    if (layer.highlight && line.length) {
      const padX = layer.highlight.pad_x_mm * PT_PER_MM, padY = layer.highlight.pad_y_mm * PT_PER_MM;
      plan.bars.push({ x: shift - padX, y: baseline - row.size * ASCENT - padY, w: row.width + 2 * padX,
        h: row.size * (ASCENT + DESCENT) + 2 * padY, radius: layer.highlight.radius_mm * PT_PER_MM });
    }
    if (layer.underline && line.length) {
      plan.rules.push({ x: shift, y: baseline + layer.underline.offset_pt, w: row.width, thickness: layer.underline.thickness_pt });
    }
    cursor += row.leading;
  });
  return plan;
}

/** Plan a text layer from its own box and properties (millimetres in, points out). */
export function planLayer(layer: Layer, values: Record<string, string>, measure: MeasureText, locale?: string) {
  const spans = resolveSpans(layer, values, locale);
  const style: RichLayerStyle = { font_size_pt: layer.font_size_pt ?? 10, line_height: layer.line_height ?? 1.2, align: layer.align ?? "left",
    valign: layer.valign ?? "top", shrink_to_fit: layer.shrink_to_fit !== false, highlight: layer.highlight, underline: layer.underline };
  return { spans, plan: planRich(spans, style, layer.w_mm * PT_PER_MM, layer.h_mm * PT_PER_MM, measure) };
}

/** A layer's glyph stroke; shapes use `stroke` as a colour string instead. */
export const textStroke = (layer: Layer): TextStroke | null =>
  layer.stroke && typeof layer.stroke === "object" ? layer.stroke : null;
export const shapeStroke = (layer: Layer): string | null => (typeof layer.stroke === "string" ? layer.stroke : null);

/** Does this text layer use anything the plain one-style drawing cannot show? */
export const isRichText = (layer: Layer) =>
  Boolean(layer.spans?.length || textStroke(layer) || layer.shadow || layer.highlight || layer.underline);

/** Span editing: apply `patch` to the characters [start, end) of the concatenated text, splitting spans as needed. */
export function applyToRange(spans: Span[], start: number, end: number, patch: Partial<Span>): Span[] {
  if (end <= start) return spans;
  const out: Span[] = [];
  let at = 0;
  for (const span of spans) {
    const from = at, to = at + span.text.length;
    at = to;
    if (to <= start || from >= end) { out.push(span); continue; }
    const a = Math.max(start, from) - from, b = Math.min(end, to) - from;
    if (a > 0) out.push({ ...span, text: span.text.slice(0, a) });
    out.push({ ...span, ...patch, text: span.text.slice(a, b) });
    if (b < span.text.length) out.push({ ...span, text: span.text.slice(b) });
  }
  return mergeSpans(out);
}

/** Join neighbours that carry the same style so the list stays short (the server caps it at 20). */
export function mergeSpans(spans: Span[]): Span[] {
  const out: Span[] = [];
  for (const span of spans) {
    if (!span.text) continue;
    const last = out[out.length - 1];
    const { text: _a, ...rest } = span;
    const { text: _b, ...before } = last ?? { text: "" };
    if (last && JSON.stringify(rest) === JSON.stringify(before)) out[out.length - 1] = { ...last, text: last.text + span.text };
    else out.push(span);
  }
  return out;
}

export const spansText = (spans: Span[]) => spans.map((span) => span.text).join("");

/** Replace the whole text keeping each span's style where it still lines up (edits keep the first span's style at the edit). */
export function retypeSpans(spans: Span[], text: string): Span[] {
  const old = spansText(spans);
  let head = 0;
  while (head < old.length && head < text.length && old[head] === text[head]) head += 1;
  let tail = 0;
  while (tail < old.length - head && tail < text.length - head && old[old.length - 1 - tail] === text[text.length - 1 - tail]) tail += 1;
  const inserted = text.slice(head, text.length - tail);
  const out: Span[] = [];
  let at = 0, placed = false;
  for (const span of spans) {
    const from = at, to = at + span.text.length;
    at = to;
    const keepBefore = span.text.slice(0, Math.max(0, Math.min(span.text.length, head - from)));
    const keepAfter = span.text.slice(Math.max(0, Math.min(span.text.length, old.length - tail - from)));
    if (keepBefore) out.push({ ...span, text: keepBefore });
    if (!placed && head <= to && (head >= from)) {
      if (inserted) out.push({ ...span, text: inserted });
      placed = true;
    }
    if (keepAfter) out.push({ ...span, text: keepAfter });
  }
  if (!placed && inserted) out.push({ ...(spans[spans.length - 1] ?? {}), text: inserted });
  return mergeSpans(out.length ? out : [{ text }]);
}
