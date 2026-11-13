// Pure edits of a CardDocument: every change returns a new document so undo can keep the old one.
import { t } from "@lingui/core/macro";
import type { CardDocument, Layer, LayerKind, Side, SideName } from "./cardTypes";
import { newLayerId, qrMinimum, round1, stockSize } from "./cardGeometry";

/** Mirrors apps/card_designs layout (decision 314: 60 layers per side, up to 20 spans per text layer). */
export const MAX_LAYERS = 60;
export const MAX_SPANS = 20;
/** Mirrors apps/card_designs/layout_layers.py: Code128 at a 0.19 mm module. */
export const BARCODE_MIN_WIDTH_MM = { number: 30, desk: 75 } as const;
export const BARCODE_MIN_HEIGHT_MM = 6;

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

/** Move a layer to an absolute z-position (0 = bottom), for drag and drop in the layers panel. */
export function moveLayerTo(document: CardDocument, side: SideName, id: string, to: number) {
  return withSide(document, side, (current) => {
    const from = current.layers.findIndex((layer) => layer.id === id);
    const target = Math.max(0, Math.min(current.layers.length - 1, to));
    if (from < 0 || from === target) return current;
    const layers = [...current.layers];
    const [moving] = layers.splice(from, 1);
    layers.splice(target, 0, moving);
    return { ...current, layers };
  });
}

/** Name, lock or hide a group: the `groups` row (created when a legacy group has none) and, for lock and hide,
 *  every member, so the canvas and the keyboard honour it. A hidden group is hidden in every output. */
export function setGroupMeta(document: CardDocument, side: SideName, groupId: string,
  patch: Partial<{ name: string; locked: boolean; hidden: boolean }>) {
  return withSide(document, side, (current) => {
    const rows = current.groups ?? [];
    const row = rows.find((item) => item.id === groupId) ?? { id: groupId, name: "", locked: false, hidden: false };
    const next = { ...row, ...patch, name: (patch.name ?? row.name).slice(0, 40) };
    const members = ({ locked: patch.locked, hidden: patch.hidden });
    return { ...current, groups: rows.some((item) => item.id === groupId) ? rows.map((item) => (item.id === groupId ? next : item)) : [...rows, next],
      layers: current.layers.map((layer) => layer.group !== groupId ? layer : { ...layer,
        ...(members.locked === undefined ? {} : { locked: members.locked }), ...(members.hidden === undefined ? {} : { hidden: members.hidden }) }) };
  });
}

/** Drop a guide line (editor-only) at `atMm` from a ruler click; at most 20, never a duplicate. */
export function addRulerLine(document: CardDocument, axis: "x" | "y", atMm: number): CardDocument {
  const guides = { bleed_mm: 0, safe_mm: 3, margin_mm: 0, punch_slot: null, rulers: [], ...document.guides };
  if (guides.rulers.length >= 20 || guides.rulers.some((ruler) => ruler.axis === axis && ruler.at_mm === atMm)) return document;
  return { ...document, guides: { ...guides, rulers: [...guides.rulers, { axis, at_mm: atMm }] } };
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
  text: t`Text`, data_field: t`Data field`, image: t`Image`, logo: t`Logo`, photo: t`Photo`, desk_qr: t`Desk QR`,
  verify_qr: t`Check QR`, barcode: t`Barcode`, shape: t`Shape`, band: t`Band`, perforation: t`Perforation`, icon: t`Icon`,
  signature: t`Signature`, signature_row: t`Signature row`, seal: t`Seal`, certificate_id: t`Certificate number`,
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
  const text = { font_family: "Outfit", font_weight: 600, font_size_pt: 10, align: "left" as const,
    valign: "top" as const, colour: "#142C2A", uppercase: false, tracking_pt: 0, line_height: 1.2, shrink_to_fit: true };
  switch (kind) {
    case "text": return { ...base, ...at(width * 0.5, 7), ...text, text: t`Your text`, ...extra };
    case "data_field": {
      const field = extra.field ?? "name";
      return { ...base, ...at(width * 0.5, 7), ...text, field, text: `{{${field}}}`, ...extra };
    }
    case "image": return { ...base, ...at(width * 0.3, height * 0.3), fit: "contain", ...extra } as Layer;
    case "logo": return { ...base, ...at(14, 14), source: "space", tile: false, ...extra };
    case "photo": return { ...base, ...at(Math.min(22, width * 0.3), Math.min(28, height * 0.5)), shape: "rounded",
      filter: "none", duotone_dark: "#142C2A", duotone_light: "#DFFF8F", ...extra };
    case "desk_qr": case "verify_qr": { const size = qrMinimum(stock); return { ...base, ...at(size, size), ...extra }; }
    case "barcode": {
      const desk = extra.source === "desk";
      const w = Math.min(width - 6, desk ? BARCODE_MIN_WIDTH_MM.desk : Math.max(BARCODE_MIN_WIDTH_MM.number, width * 0.45));
      return { ...base, ...at(w, 9), source: "number", show_text: true, ...extra };
    }
    case "shape": return { ...base, ...at(width * 0.3, height * 0.2), shape: "rect", fill: "#E7F3F1", stroke: null,
      stroke_mm: 0.3, radius_mm: 0, ...extra };
    case "band": return { ...base, w_mm: width, h_mm: round1(height * 0.18), x_mm: 0, y_mm: 0, fill: "#006E63",
      radius_mm: 0, ...extra };
    case "signature": return { ...base, ...at(Math.min(60, width * 0.3), 22), ...text, font_size_pt: 11, align: "center",
      font_weight: 600, signatory_slot: 1, show_image: true, show_name: true, show_title: true,
      rule: { colour: "#142C2A", width_pt: 0.6 }, ...extra };
    case "signature_row": return { ...base, w_mm: round1(width - 40), h_mm: 24, x_mm: 20, y_mm: round1(height - 48), ...text,
      font_size_pt: 11, align: "center", font_weight: 600, slots: [1, 2], gap_mm: 12, show_image: true, show_name: true,
      show_title: true, rule: { colour: "#142C2A", width_pt: 0.6 }, ...extra };
    case "seal": return { ...base, ...at(28, 28), ...text, style: "scallop", fill: "#DFFF8F", stroke: "#142C2A", stroke_mm: 0.5,
      label: t`Seal`, ring_text: "", ring_text_colour: "#142C2A", font_weight: 800, font_size_pt: 9, ...extra };
    case "certificate_id": return { ...base, ...at(60, 6), ...text, font_size_pt: 8, font_weight: 400, shrink_to_fit: false,
      format: "full", ...extra };
    case "icon": { const size = Math.min(12, width * 0.2, height * 0.2); return { ...base, ...at(size, size), icon: "star",
      colour: "#142C2A", ...extra }; }
    case "perforation": return { ...base, w_mm: 1, h_mm: height, x_mm: round1(width * 0.75), y_mm: 0,
      colour: "#D5D0C6", orientation: "vertical", ...extra };
  }
}

export const LAYER_KIND_LABELS = NAMES;
