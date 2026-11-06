// Pure layout maths for the certificate and badge designer: snapping with guides, aspect-locked
// resize, rotation steps, page alignment and text contrast. Millimetres throughout.
import type { Layer, LayerDocument } from "../layout";

export type Box = { x_mm: number; y_mm: number; width_mm: number; height_mm: number };
export type Guide = { axis: "x" | "y"; at: number };

/** Layers whose content is a picture or code: corners keep their shape unless Shift stretches them. */
export const ASPECT_LOCKED: ReadonlySet<Layer["type"]> = new Set(["image", "logo", "photo", "signature", "certificate_qr", "event_credential_qr"]);
export const isQr = (layer: Layer) => layer.type === "certificate_qr" || layer.type === "event_credential_qr";
export const minSide = (layer: Layer) => isQr(layer) ? 20 : layer.type === "signature" ? 10 : 2;

const round = (value: number) => Math.round(value * 10) / 10;
const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), Math.max(low, high));

function stops(start: number, size: number) { return [start, start + size / 2, start + size]; }

/** Snap a moving box to the page centre/edges and to other layers' edges and centres, on both axes. */
export function snapMove(box: Box, others: Box[], page: { width: number; height: number }, threshold: number) {
  const guides: Guide[] = [];
  const axis = (key: "x" | "y") => {
    const start = key === "x" ? box.x_mm : box.y_mm;
    const size = key === "x" ? box.width_mm : box.height_mm;
    const pageSize = key === "x" ? page.width : page.height;
    const targets = [0, pageSize / 2, pageSize, ...others.flatMap((row) => key === "x" ? stops(row.x_mm, row.width_mm) : stops(row.y_mm, row.height_mm))];
    let best: { delta: number; at: number } | null = null;
    for (const point of stops(start, size)) {
      for (const target of targets) {
        const delta = target - point;
        if (Math.abs(delta) <= threshold && (!best || Math.abs(delta) < Math.abs(best.delta))) best = { delta, at: target };
      }
    }
    if (best) guides.push({ axis: key, at: best.at });
    return clamp(start + (best?.delta ?? 0), 0, pageSize - size);
  };
  return { box: { ...box, x_mm: round(axis("x")), y_mm: round(axis("y")) }, guides };
}

export type Corner = "nw" | "ne" | "sw" | "se";

/** Resize from a corner; the opposite corner stays put. `free` (Shift) drops the aspect lock. */
export function resizeFromCorner(start: Box, corner: Corner, dx: number, dy: number, layer: Layer,
  page: { width: number; height: number }, free: boolean): Box {
  const left = corner.endsWith("w"), top = corner.startsWith("n");
  let width = start.width_mm + (left ? -dx : dx);
  let height = start.height_mm + (top ? -dy : dy);
  const lock = isQr(layer) || (ASPECT_LOCKED.has(layer.type) && !free);
  if (lock) {
    const ratio = isQr(layer) ? 1 : start.width_mm / start.height_mm;
    const scale = Math.max(width / start.width_mm, height / start.height_mm);
    width = start.width_mm * scale; height = width / ratio;
  }
  const minimum = minSide(layer);
  const right = start.x_mm + start.width_mm, bottom = start.y_mm + start.height_mm;
  const maxWidth = left ? right : page.width - start.x_mm, maxHeight = top ? bottom : page.height - start.y_mm;
  width = clamp(width, minimum, maxWidth); height = clamp(height, minimum, maxHeight);
  if (lock) { const ratio = isQr(layer) ? 1 : start.width_mm / start.height_mm; const fit = Math.min(width, height * ratio); width = fit; height = fit / ratio; }
  return { x_mm: round(left ? right - width : start.x_mm), y_mm: round(top ? bottom - height : start.y_mm),
    width_mm: round(width), height_mm: round(height) };
}

/** Degrees from the box centre to the pointer, 0 = straight up. Shift snaps to 15°; QR codes to 90°. */
export function rotationFrom(center: { x: number; y: number }, pointer: { x: number; y: number }, layer: Layer, stepped: boolean) {
  const raw = Math.atan2(pointer.x - center.x, center.y - pointer.y) * 180 / Math.PI;
  const step = isQr(layer) ? 90 : stepped ? 15 : 1;
  const value = Math.round(raw / step) * step;
  return value > 180 ? value - 360 : value <= -180 ? value + 360 : value;
}

export type Alignment = "left" | "center" | "right" | "top" | "middle" | "bottom";

export function alignToPage(box: Box, page: { width: number; height: number }, how: Alignment): Partial<Box> {
  switch (how) {
    case "left": return { x_mm: 0 };
    case "center": return { x_mm: round((page.width - box.width_mm) / 2) };
    case "right": return { x_mm: round(page.width - box.width_mm) };
    case "top": return { y_mm: 0 };
    case "middle": return { y_mm: round((page.height - box.height_mm) / 2) };
    default: return { y_mm: round(page.height - box.height_mm) };
  }
}

/** Keep a box on the page after a keyboard nudge or a numeric edit. */
export function keepOnPage(box: Box, page: { width: number; height: number }): Box {
  const width = clamp(box.width_mm, 0.1, page.width), height = clamp(box.height_mm, 0.1, page.height);
  return { width_mm: round(width), height_mm: round(height),
    x_mm: round(clamp(box.x_mm, 0, page.width - width)), y_mm: round(clamp(box.y_mm, 0, page.height - height)) };
}

function luminance(hex: string) {
  const channels = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255)
    .map((value) => value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

/** WCAG contrast ratio of two #RRGGBB colours. */
export function contrast(foreground: string, background: string) {
  const [a, b] = [luminance(foreground), luminance(background)].sort((x, y) => y - x);
  return Math.round(((a + 0.05) / (b + 0.05)) * 100) / 100;
}

/** The page colour behind text is only measurable when no full-page picture covers it. */
export function measurablePaper(document: LayerDocument) {
  return !document.layers.some((layer) => !layer.hidden && layer.type === "image"
    && layer.width_mm >= document.page_width_mm * 0.9 && layer.height_mm >= document.page_height_mm * 0.9);
}

export function hasNameTag(document: LayerDocument) {
  return document.layers.some((layer) => !layer.hidden && layer.type === "text" && /{{\s*name\s*}}/.test(layer.text ?? ""));
}
