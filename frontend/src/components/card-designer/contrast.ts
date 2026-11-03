// WCAG text contrast against the colour under a text layer, the same maths as
// apps/card_designs/contrast.py, so the designer warns before the server refuses (4.5:1).
import type { Background, Side } from "./cardTypes";

export const MINIMUM_RATIO = 4.5;
type RGB = [number, number, number];

export function rgb(hex: string): RGB {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16)) as RGB;
}

export function luminance([r, g, b]: RGB) {
  const channel = (c: number) => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

export function ratio(a: RGB, b: RGB) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const blend = (under: RGB, over: RGB, alpha: number) => under.map((u, i) => u * (1 - alpha) + over[i] * alpha) as RGB;

function backgroundAt(background: Background, x: number, y: number, width: number, height: number,
  assetColours: Record<string, string>): RGB {
  if (background.kind === "colour") return rgb(background.colour);
  if (background.kind === "image") return blend(rgb(assetColours[background.asset_id] ?? "#808080"), [0, 0, 0], background.dim_pct / 100);
  const stops = [...background.stops].sort((a, b) => a.at - b.at);
  let t: number;
  if (background.type === "radial") {
    t = Math.hypot(x - width / 2, y - height / 2) / (Math.hypot(width / 2, height / 2) || 1);
  } else {
    const angle = background.angle_deg * Math.PI / 180;
    const dx = Math.sin(angle), dy = -Math.cos(angle);
    t = ((x - width / 2) * dx + (y - height / 2) * dy) / ((Math.abs(width * dx) + Math.abs(height * dy)) || 1) + 0.5;
  }
  t = Math.min(1, Math.max(0, t)) * 100;
  let previous = stops[0];
  for (const stop of stops) {
    if (t <= stop.at) return blend(rgb(previous.colour), rgb(stop.colour), (t - previous.at) / ((stop.at - previous.at) || 1));
    previous = stop;
  }
  return rgb(stops[stops.length - 1].colour);
}

/** The contrast ratio of the text layer at `index`, or null for a non-text layer. */
export function layerContrast(side: Side, index: number, assetColours: Record<string, string> = {}) {
  const layer = side.layers[index];
  if (!layer || (layer.kind !== "text" && layer.kind !== "data_field") || !layer.colour) return null;
  const x = layer.x_mm + layer.w_mm / 2, y = layer.y_mm + layer.h_mm / 2;
  let under = backgroundAt(side.background, x, y, side.page_width_mm, side.page_height_mm, assetColours);
  for (const below of side.layers.slice(0, index)) {
    if (below.hidden || !below.fill || (below.kind !== "shape" && below.kind !== "band") || below.shape === "line") continue;
    if (x >= below.x_mm && x <= below.x_mm + below.w_mm && y >= below.y_mm && y <= below.y_mm + below.h_mm) {
      under = blend(under, rgb(below.fill), (below.opacity ?? 100) / 100);
    }
  }
  const text = blend(under, rgb(layer.colour), (layer.opacity ?? 100) / 100);
  return ratio(text, under);
}

export function unreadable(side: Side, assetColours: Record<string, string> = {}) {
  return side.layers.filter((layer, index) => !layer.hidden && (layerContrast(side, index, assetColours) ?? 99) < MINIMUM_RATIO);
}
