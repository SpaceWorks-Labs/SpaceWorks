// Marquee (rubber-band) selection: the layers whose boxes the dragged rectangle touches, expanded to whole groups.
import type { Layer } from "./cardTypes";

export type MarqueeRect = { x0: number; y0: number; x1: number; y1: number; additive: boolean };

/** A rectangle must be dragged at least this far (mm) to count as a marquee rather than a click. */
export const MARQUEE_MIN_MM = 1.5;

export function marqueeHits(layers: Layer[], rect: MarqueeRect): string[] {
  const left = Math.min(rect.x0, rect.x1), right = Math.max(rect.x0, rect.x1);
  const top = Math.min(rect.y0, rect.y1), bottom = Math.max(rect.y0, rect.y1);
  if (right - left < MARQUEE_MIN_MM && bottom - top < MARQUEE_MIN_MM) return [];
  const hit = layers.filter((layer) => !layer.hidden && !layer.locked
    && layer.x_mm < right && layer.x_mm + layer.w_mm > left && layer.y_mm < bottom && layer.y_mm + layer.h_mm > top);
  const groups = new Set(hit.map((layer) => layer.group).filter(Boolean));
  return layers.filter((layer) => hit.includes(layer) || (layer.group && groups.has(layer.group))).map((layer) => layer.id);
}
