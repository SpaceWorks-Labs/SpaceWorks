// LOCAL test fixtures (never committed): tiny card documents for the designer tests.
import { expect, it } from "vitest";

import type { CardDocument, Layer, Side } from "./cardTypes";

let counter = 0;
export function layer(partial: Partial<Layer> = {}): Layer {
  counter += 1;
  return { id: partial.id ?? `l${counter}`, kind: "shape", name: "", x_mm: 10, y_mm: 10, w_mm: 10, h_mm: 10, rotation: 0,
    opacity: 100, locked: false, hidden: false, fill: "#E7F3F1", ...partial };
}

export function side(layers: Layer[], width = 85.6, height = 53.98): Side {
  return { page_width_mm: width, page_height_mm: height, background: { kind: "colour", colour: "#FFFFFF" }, layers };
}

export function doc(front: Layer[], back: Layer[] = [], extra: Partial<CardDocument> = {}): CardDocument {
  return { version: 2, stock: "cr80-landscape", back_enabled: back.length > 0, mono: false,
    watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: 0, colour: "#000000" },
    front: side(front), back: side(back), ...extra };
}

it("builds a two-sided document when the back has layers", () => {
  expect(doc([layer()], [layer()]).back_enabled).toBe(true);
});
