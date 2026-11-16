// Barcode symbologies (decision 345(c)): the TS twin of backend apps/card_designs/barcode_symbols.py. The SERVER
// encodes (one encoder for print and preview: the designer asks POST card-designs/{pk}/barcode); this file only turns
// an encoding into rectangles (`barcodeRects`, golden-fixture checked) and mirrors the minimum printed sizes.
import { useQuery } from "@tanstack/react-query";
import { t } from "@lingui/core/macro";

import { staffRequest } from "../../lib/api";
import type { Layer } from "./cardTypes";

export type Symbology = "code128" | "code39" | "ean13" | "upca" | "pdf417" | "datamatrix" | "aztec";
export const SYMBOLOGIES: Symbology[] = ["code128", "code39", "ean13", "upca", "pdf417", "datamatrix", "aztec"];
export type BarcodeEncoding =
  | { symbology: Symbology; kind: "linear"; bars: string; quiet: [number, number]; text: string }
  | { symbology: Symbology; kind: "matrix"; rows: string[] };

/** 1 pt in mm: half above the bars, half between bars and the text line (the original Code 128 look). */
export const BARCODE_GAP_MM = 25.4 / 72;
/** The human-readable line under a linear code: 6 pt x 1.25, in mm. */
export const BARCODE_TEXT_MM = (6 * 1.25 * 25.4) / 72;

/** Minimum box (mm) by symbology: [number width, desk width (null = refused)], height. Mirrors MINIMUM_MM. */
const MINIMUM: Record<Symbology, [[number, number | null], number]> = {
  code128: [[30, 75], 6], code39: [[40, null], 8], ean13: [[30, null], 10], upca: [[30, null], 10],
  pdf417: [[30, 45], 8], datamatrix: [[10, 12], 10], aztec: [[10, 12], 10],
};

export const symbologyOf = (layer: Layer): Symbology => layer.symbology ?? "code128";
export const isMatrixCode = (symbology: Symbology) => symbology === "pdf417" || symbology === "datamatrix" || symbology === "aztec";
export const carriesDesk = (symbology: Symbology) => MINIMUM[symbology][0][1] !== null;

export function barcodeMinimum(symbology: Symbology, source: Layer["source"]): { w: number; h: number } {
  const [[number, desk], h] = MINIMUM[symbology];
  return { w: source === "desk" ? desk ?? number : number, h };
}

export function symbologyLabel(symbology: Symbology) {
  return { code128: t`Code 128`, code39: t`Code 39`, ean13: t`EAN-13 (12 or 13 digits)`, upca: t`UPC-A (11 or 12 digits)`,
    pdf417: t`PDF417`, datamatrix: t`Data Matrix`, aztec: t`Aztec` }[symbology];
}

const r4 = (value: number) => Math.round(value * 10000) / 10000;

/** Dark rectangles [x, y, w, h] in a w x h box (top-left origin, same unit): the twin of barcode_symbols.rects. */
export function barcodeRects(encoded: BarcodeEncoding, width: number, height: number, textHeight = 0, gap = BARCODE_GAP_MM) {
  const out: [number, number, number, number][] = [];
  if (encoded.kind === "linear") {
    const [left, right] = encoded.quiet;
    const module = width / (encoded.bars.length + left + right);
    const barH = Math.max(gap / 4, height - textHeight - gap);
    let start: number | null = null;
    [...`${encoded.bars}0`].forEach((cell, index) => {
      if (cell === "1" && start === null) start = index;
      else if (cell !== "1" && start !== null) {
        out.push([r4((left + start) * module), r4(gap / 2), r4((index - start) * module), r4(barH)]);
        start = null;
      }
    });
    return out;
  }
  const rows = encoded.rows;
  const module = Math.min(width / rows[0].length, height / rows.length);
  const ox = (width - module * rows[0].length) / 2, oy = (height - module * rows.length) / 2;
  rows.forEach((row, r) => {
    let start: number | null = null;
    [...`${row}0`].forEach((cell, c) => {
      if (cell === "1" && start === null) start = c;
      else if (cell !== "1" && start !== null) {
        out.push([r4(ox + start * module), r4(oy + r * module), r4((c - start) * module), r4(module)]);
        start = null;
      }
    });
  });
  return out;
}

/** The value the designer previews: the sample number, or a placeholder of the desk code's length (never a real one). */
export const previewValue = (layer: Layer, values: Record<string, string>) =>
  layer.source === "desk" ? "SWDESKPREVIEW0000000000000000000" : (values.number || "SW-0000");

export function useBarcodeEncoding(designId: number, symbology: Symbology, value: string, enabled = true) {
  return useQuery({ queryKey: ["card-barcode", designId, symbology, value], enabled: enabled && designId > 0, staleTime: Infinity,
    retry: false, queryFn: () => staffRequest<BarcodeEncoding>(`/admin/card-designs/${designId}/barcode`, {
      method: "POST", body: JSON.stringify({ symbology, value }) }) });
}
