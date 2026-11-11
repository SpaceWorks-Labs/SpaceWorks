import { t } from "@lingui/core/macro";
// Desk-print stocks (decision 290): A6, 4x6, 3x4 and CR80, portrait or landscape. The keys are the
// server's (apps/card_designs/stocks.py STOCKS); the sizes let the print window open at true size.

export type Orientation = "portrait" | "landscape";
export type StockFamily = "a6" | "4x6" | "3x4" | "cr80";

type Size = { widthMm: number; heightMm: number };
const FAMILIES: Record<StockFamily, { portrait: [string, Size]; landscape: [string, Size] }> = {
  a6: { portrait: ["a6-portrait", { widthMm: 105, heightMm: 148 }], landscape: ["a6-landscape", { widthMm: 148, heightMm: 105 }] },
  "4x6": { portrait: ["4x6", { widthMm: 101.6, heightMm: 152.4 }], landscape: ["6x4", { widthMm: 152.4, heightMm: 101.6 }] },
  "3x4": { portrait: ["3x4", { widthMm: 76.2, heightMm: 101.6 }], landscape: ["4x3", { widthMm: 101.6, heightMm: 76.2 }] },
  cr80: { portrait: ["cr80-portrait", { widthMm: 53.98, heightMm: 85.6 }], landscape: ["cr80-landscape", { widthMm: 85.6, heightMm: 53.98 }] },
};

export const stockFamilies = (): { value: StockFamily; label: string }[] => [
  { value: "a6", label: t`A6 (105 × 148 mm)` }, { value: "4x6", label: t`4 × 6 in label` },
  { value: "3x4", label: t`3 × 4 in label` }, { value: "cr80", label: t`CR80 card (85.6 × 54 mm)` },
];

export function deskStock(family: StockFamily, orientation: Orientation) {
  const [key, size] = FAMILIES[family][orientation];
  return { key, ...size };
}
