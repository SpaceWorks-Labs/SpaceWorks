// Pure edits of a CardDocument: every change returns a new document so undo can keep the old one.
import type { CardDocument, Layer, LayerKind, Side, SideName } from "./cardTypes";
import { newLayerId, qrMinimum, round1, stockSize } from "./cardGeometry";

export const MAX_LAYERS = 40;

export function withSide(document: CardDocument, side: SideName, change: (current: Side) => Side): CardDocument {
  return { ...document, [side]: change(document[side]) };
}

export function patchLayer(document: CardDocument, side: SideName, id: string, patch: Partial<Layer>) {
  return withSide(document, side, (current) => ({
    ...current, layers: current.layers.map((layer) => (layer.id === id ? { ...layer, ...patch } : layer)),
  }));
}

export function removeLayer(document: CardDocument, side: SideName, id: string) {
  return withSide(document, side, (current) => ({ ...current, layers: current.layers.filter((layer) => layer.id !== id) }));
}

/** Move one step in the z-order: "up" draws it later (on top). */
export function moveLayer(document: CardDocument, side: SideName, id: string, direction: "up" | "down") {
  return withSide(document, side, (current) => {
    const index = current.layers.findIndex((layer) => layer.id === id);
    const target = direction === "up" ? index + 1 : index - 1;
    if (index < 0 || target < 0 || target >= current.layers.length) return current;
    const layers = [...current.layers];
    [layers[index], layers[target]] = [layers[target], layers[index]];
    return { ...current, layers };
  });
}

export function addLayer(document: CardDocument, side: SideName, layer: Layer) {
  return withSide(document, side, (current) =>
    current.layers.length >= MAX_LAYERS ? current : { ...current, layers: [...current.layers, layer] });
}

export function duplicateLayer(document: CardDocument, side: SideName, id: string) {
  const source = document[side].layers.find((layer) => layer.id === id);
  if (!source) return { document, id: null };
  const copy: Layer = { ...source, id: newLayerId(), name: source.name ? `${source.name} copy`.slice(0, 40) : "",
    x_mm: round1(Math.min(source.x_mm + 2, document[side].page_width_mm - source.w_mm)),
    y_mm: round1(Math.min(source.y_mm + 2, document[side].page_height_mm - source.h_mm)) };
  return { document: addLayer(document, side, copy), id: copy.id };
}

/** Change the stock: both sides take the new size and layers scale to fit it. */
export function applyStock(document: CardDocument, stock: string, width?: number, height?: number): CardDocument {
  const size = stockSize(stock, width, height);
  const scaleSide = (side: Side): Side => {
    const sx = size.width / side.page_width_mm, sy = size.height / side.page_height_mm;
    const qr = qrMinimum(stock);
    return { ...side, page_width_mm: size.width, page_height_mm: size.height,
      layers: side.layers.map((layer) => {
        const isQr = layer.kind === "desk_qr" || layer.kind === "verify_qr";
        const w = isQr ? Math.max(qr, round1(Math.min(layer.w_mm * sx, layer.h_mm * sy))) : round1(layer.w_mm * sx);
        const h = isQr ? w : round1(layer.h_mm * sy);
        return { ...layer, w_mm: Math.min(w, size.width), h_mm: Math.min(h, size.height),
          x_mm: round1(Math.max(0, Math.min(layer.x_mm * sx, size.width - Math.min(w, size.width)))),
          y_mm: round1(Math.max(0, Math.min(layer.y_mm * sy, size.height - Math.min(h, size.height)))) };
      }) };
  };
  const next: CardDocument = { ...document, stock, front: scaleSide(document.front), back: scaleSide(document.back) };
  if (stock === "custom") return { ...next, page_width_mm: size.width, page_height_mm: size.height };
  const { page_width_mm: _w, page_height_mm: _h, ...rest } = next;
  return rest as CardDocument;
}

const NAMES: Record<LayerKind, string> = {
  text: "Text", data_field: "Data field", image: "Image", logo: "Logo", photo: "Photo", desk_qr: "Desk QR",
  verify_qr: "Check QR", shape: "Shape", band: "Band", perforation: "Perforation",
};

export function layerName(layer: Layer) {
  return layer.name || (layer.kind === "data_field" && layer.field ? `${NAMES.data_field}: ${layer.field}` : NAMES[layer.kind]);
}

/** A new layer of `kind`, centred and sized for the side, with the server's defaults. */
export function newLayer(kind: LayerKind, side: Side, stock: string, extra: Partial<Layer> = {}): Layer {
  const width = side.page_width_mm, height = side.page_height_mm;
  const base = { id: newLayerId(), kind, name: "", rotation: 0, opacity: 100, locked: false, hidden: false };
  const at = (w: number, h: number) => ({ w_mm: round1(w), h_mm: round1(h),
    x_mm: round1((width - w) / 2), y_mm: round1((height - h) / 2) });
  const text = { font_family: "Gilroy", font_weight: 600, font_size_pt: 10, align: "left" as const,
    valign: "top" as const, colour: "#142C2A", uppercase: false, tracking_pt: 0, line_height: 1.2, shrink_to_fit: true };
  switch (kind) {
    case "text": return { ...base, ...at(width * 0.5, 7), ...text, text: "Your text", ...extra };
    case "data_field": {
      const field = extra.field ?? "name";
      return { ...base, ...at(width * 0.5, 7), ...text, field, text: `{{${field}}}`, ...extra };
    }
    case "image": return { ...base, ...at(width * 0.3, height * 0.3), fit: "contain", ...extra } as Layer;
    case "logo": return { ...base, ...at(14, 14), source: "space", tile: false, ...extra };
    case "photo": return { ...base, ...at(Math.min(22, width * 0.3), Math.min(28, height * 0.5)), shape: "rounded", ...extra };
    case "desk_qr": case "verify_qr": { const size = qrMinimum(stock); return { ...base, ...at(size, size), ...extra }; }
    case "shape": return { ...base, ...at(width * 0.3, height * 0.2), shape: "rect", fill: "#E7F3F1", stroke: null,
      stroke_mm: 0.3, radius_mm: 0, ...extra };
    case "band": return { ...base, w_mm: width, h_mm: round1(height * 0.18), x_mm: 0, y_mm: 0, fill: "#006E63",
      radius_mm: 0, ...extra };
    case "perforation": return { ...base, w_mm: 1, h_mm: height, x_mm: round1(width * 0.75), y_mm: 0,
      colour: "#D5D0C6", orientation: "vertical", ...extra };
  }
}

export const LAYER_KIND_LABELS = NAMES;
