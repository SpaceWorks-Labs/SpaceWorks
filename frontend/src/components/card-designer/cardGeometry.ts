// Card stocks, snapping and the safe area. Mirrors apps/card_designs/stocks.py.
import { t } from "@lingui/core/macro";
import type { Layer, Side } from "./cardTypes";

export const PT_TO_MM = 0.3528;
export const SAFE_AREA_MM = 3;
export const GRID_SIZES_MM = [1, 2, 5, 10] as const;

export type StockFamily = "card" | "badge" | "certificate";
export type Stock = { key: string; label: string; width: number; height: number; family: StockFamily };

const CARD_STOCKS: Omit<Stock, "family">[] = [
  { key: "cr80-landscape", label: t`ID card (CR80), landscape`, width: 85.6, height: 53.98 },
  { key: "cr80-portrait", label: t`ID card (CR80), portrait`, width: 53.98, height: 85.6 },
  { key: "cr79-landscape", label: t`Adhesive card (CR79), landscape`, width: 83.9, height: 52.1 },
  { key: "cr79-portrait", label: t`Adhesive card (CR79), portrait`, width: 52.1, height: 83.9 },
  { key: "cr100-landscape", label: t`Large ID (CR100), landscape`, width: 98.5, height: 67 },
  { key: "cr100-portrait", label: t`Large ID (CR100), portrait`, width: 67, height: 98.5 },
  { key: "a6-portrait", label: t`A6 badge, portrait`, width: 105, height: 148 },
  { key: "a6-landscape", label: t`A6 badge, landscape`, width: 148, height: 105 },
  { key: "4x3", label: t`4 × 3 in badge`, width: 101.6, height: 76.2 },
  { key: "3x4", label: t`3 × 4 in badge`, width: 76.2, height: 101.6 },
  { key: "4x6", label: t`4 × 6 in badge`, width: 101.6, height: 152.4 },
  { key: "6x4", label: t`6 × 4 in badge`, width: 152.4, height: 101.6 },
  { key: "badge-90x130", label: t`Badge 90 × 130 mm, portrait`, width: 90, height: 130 },
  { key: "badge-130x90", label: t`Badge 130 × 90 mm, landscape`, width: 130, height: 90 },
  { key: "a5-portrait", label: t`A5, portrait`, width: 148, height: 210 },
  { key: "a5-landscape", label: t`A5, landscape`, width: 210, height: 148 },
  { key: "a4-portrait", label: t`A4 certificate, portrait`, width: 210, height: 297 },
  { key: "a4-landscape", label: t`A4 certificate, landscape`, width: 297, height: 210 },
  { key: "letter-portrait", label: t`US Letter, portrait`, width: 215.9, height: 279.4 },
  { key: "letter-landscape", label: t`US Letter, landscape`, width: 279.4, height: 215.9 },
  { key: "custom", label: t`Custom size`, width: 85.6, height: 53.98 },
];

const familyOf = (key: string): StockFamily => (/^(a5|a4|letter)-/.test(key) ? "certificate"
  : /^(a6|4x|3x|6x|badge)/.test(key) ? "badge" : "card");
export const STOCKS: Stock[] = CARD_STOCKS.map((stock) => ({ ...stock, family: familyOf(stock.key) }));

/** The presets a document kind offers: certificates take paper sizes (custom 100-420 mm), cards take card and badge sizes. */
export function stocksFor(kind: "card" | "certificate" = "card") {
  return STOCKS.filter((stock) => stock.key === "custom" || (kind === "certificate" ? stock.family === "certificate"
    : stock.family !== "certificate" || /^a5-/.test(stock.key)));
}
export const customLimits = (kind: "card" | "certificate" = "card") => (kind === "certificate" ? { min: 100, max: 420 } : { min: 40, max: 300 });

export function stockSize(stock: string, width?: number, height?: number) {
  if (stock === "custom") return { width: width ?? 85.6, height: height ?? 53.98 };
  const found = STOCKS.find((item) => item.key === stock) ?? STOCKS[0];
  return { width: found.width, height: found.height };
}

export function qrMinimum(stock: string) {
  return /^cr(80|79|100)/.test(stock) ? 18 : 20;
}

export const round1 = (value: number) => Math.round(value * 10) / 10;
export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function snap(value: number, grid: number) {
  return round1(Math.round(value / grid) * grid);
}

/** Snap a moving layer's edges and centre to the card centre and to other layers' edges. */
export function snapToGuides(side: Side, moving: Layer, x: number, y: number, threshold = 1.2) {
  const xs = [0, side.page_width_mm / 2, side.page_width_mm, SAFE_AREA_MM, side.page_width_mm - SAFE_AREA_MM];
  const ys = [0, side.page_height_mm / 2, side.page_height_mm, SAFE_AREA_MM, side.page_height_mm - SAFE_AREA_MM];
  for (const other of side.layers) {
    if (other.id === moving.id || other.hidden) continue;
    xs.push(other.x_mm, other.x_mm + other.w_mm / 2, other.x_mm + other.w_mm);
    ys.push(other.y_mm, other.y_mm + other.h_mm / 2, other.y_mm + other.h_mm);
  }
  const guides: { axis: "x" | "y"; at: number }[] = [];
  const pick = (start: number, size: number, lines: number[], axis: "x" | "y") => {
    for (const offset of [0, size / 2, size]) {
      const hit = lines.find((line) => Math.abs(start + offset - line) <= threshold);
      if (hit !== undefined) {
        guides.push({ axis, at: hit });
        return round1(hit - offset);
      }
    }
    return start;
  };
  return { x: pick(x, moving.w_mm, xs, "x"), y: pick(y, moving.h_mm, ys, "y"), guides };
}

/** Keep a layer's box on the card (rotation ignored for the clamp; the server checks the exact box). */
export function clampToCard(side: Side, layer: Layer, x: number, y: number, safe = false) {
  const margin = safe ? SAFE_AREA_MM : 0;
  return {
    x: clamp(x, margin, Math.max(margin, side.page_width_mm - margin - layer.w_mm)),
    y: clamp(y, margin, Math.max(margin, side.page_height_mm - margin - layer.h_mm)),
  };
}

export function newLayerId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID()
    : "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
      (Number(c) ^ (Math.random() * 16 >> (Number(c) / 4))).toString(16));
}
