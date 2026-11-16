// Quick-mode edits: whole-design changes a non-expert makes without the canvas (colours, paper, orientation,
// what is shown). Pure functions of the document so each is one undo step and is testable.
import { t } from "@lingui/core/macro";
import type { CardDocument, Layer, SideName } from "./cardTypes";
import { stockSize } from "./cardGeometry";
import { applyStock, withSide } from "./designDocument";

/** The brand palette (SpaceWorks-Events) offered as swatches; any custom colour is allowed too. */
export const brandSwatches = (): { key: string; label: string; hex: string }[] => [
  { key: "ink", label: t`Ink`, hex: "#142C2A" }, { key: "teal", label: t`Maker Teal`, hex: "#006E63" },
  { key: "orange", label: t`Workshop Orange`, hex: "#FF7447" }, { key: "citron", label: t`Citron`, hex: "#DFFF8F" },
  { key: "sky", label: t`Sky`, hex: "#B5CDFF" }, { key: "yellow", label: t`Yellow`, hex: "#FFD447" },
  { key: "cream", label: t`Cream`, hex: "#FFF4E8" }, { key: "white", label: t`White`, hex: "#FFFFFF" },
];

const TEXT_KINDS = new Set(["text", "data_field", "signature", "signature_row", "certificate_id"]);

/** Set the side's background colour (replacing any image or gradient). */
export function setBackgroundColour(document: CardDocument, side: SideName, colour: string): CardDocument {
  return withSide(document, side, (current) => ({ ...current, background: { kind: "colour", colour } }));
}

/** Every text layer takes `colour`; rich spans keep their own explicit colours unless `spans` is true. */
export function setTextColour(document: CardDocument, side: SideName, colour: string, spans = false): CardDocument {
  return withSide(document, side, (current) => ({ ...current, layers: current.layers.map((layer) => TEXT_KINDS.has(layer.kind)
    ? { ...layer, colour, spans: spans && layer.spans ? layer.spans.map(({ colour: _drop, ...rest }) => rest) : layer.spans } : layer) }));
}

/** Bands and filled shapes take the accent colour. */
export function setAccentColour(document: CardDocument, side: SideName, colour: string): CardDocument {
  return withSide(document, side, (current) => ({ ...current, layers: current.layers.map((layer) =>
    layer.kind === "band" || (layer.kind === "shape" && layer.fill && !layer.fill_gradient) ? { ...layer, fill: colour } : layer) }));
}

/** The same preset turned the other way (cr80-portrait <-> cr80-landscape, 3x4 <-> 4x3, badge-90x130 <-> badge-130x90). */
export function turnedStock(stock: string): string {
  if (/-portrait$/.test(stock)) return stock.replace(/-portrait$/, "-landscape");
  if (/-landscape$/.test(stock)) return stock.replace(/-landscape$/, "-portrait");
  const pair = /^(\d)x(\d)$/.exec(stock);
  if (pair) return `${pair[2]}x${pair[1]}`;
  const badge = /^badge-(\d+)x(\d+)$/.exec(stock);
  return badge ? `badge-${badge[2]}x${badge[1]}` : stock;
}

export function turnPaper(document: CardDocument): CardDocument {
  if (document.stock === "custom") {
    const { width, height } = stockSize("custom", document.page_width_mm ?? document.front.page_width_mm, document.page_height_mm ?? document.front.page_height_mm);
    return applyStock(document, "custom", height, width);
  }
  const next = turnedStock(document.stock);
  return next === document.stock ? document : applyStock(document, next);
}

/** Layers a person recognises by what they are, for the show/hide list. */
export function quickItems(layers: Layer[]) {
  return layers.filter((layer) => layer.kind !== "band" && layer.kind !== "perforation" && layer.kind !== "shape");
}
