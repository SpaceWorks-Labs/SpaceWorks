import type { PositionedElement } from "../../../components/print-layout/positionedLayout";

export type Layer = {
  id: string; order: number; type: "text" | "image" | "logo" | "photo" | "certificate_id" | "certificate_qr" | "event_credential_qr";
  x_mm: number; y_mm: number; width_mm: number; height_mm: number; rotation: number;
  text?: string; font_family?: "Gilroy" | "Unbounded"; font_weight?: 400 | 500 | 600 | 700;
  font_size_pt?: number; align?: "left" | "center" | "right"; shrink_to_fit?: boolean;
  italic?: boolean; uppercase?: boolean; tracking_pt?: number; line_height?: number;
  opacity?: number; resource_id?: string; resource_slot?: string; colour_token?: string;
};
export type LayerDocument = { version: 2; page_width_mm: number; page_height_mm: number; layers: Layer[] };
export type LegacyDocument = { version: 1; page_width_mm: number; page_height_mm: number; name_box: PositionedElement };
export const MERGE_TAGS = ["name", "event", "eventDate", "organisation", "issueDate", "crewRole"] as const;
export const STOCKS = {
  "a6-portrait": [105, 148], "4x6": [101.6, 152.4], "3x4": [76.2, 101.6],
  "4x3": [101.6, 76.2], "cr80-portrait": [53.98, 85.6], "cr80-landscape": [85.6, 53.98],
} as const;
export type Stock = keyof typeof STOCKS;

export function upgradeDocument(input: LayerDocument | LegacyDocument): LayerDocument {
  if (input.version === 2) return structuredClone(input);
  const box = input.name_box;
  return { version: 2, page_width_mm: input.page_width_mm, page_height_mm: input.page_height_mm,
    layers: [{ id: crypto.randomUUID(), order: 0, type: "text", rotation: 0, text: "{{name}}",
      x_mm: box.x_mm, y_mm: box.y_mm, width_mm: box.width_mm, height_mm: box.height_mm,
      font_size_pt: box.font_size_pt, font_weight: box.bold ? 700 : 400, font_family: "Gilroy",
      align: box.align, shrink_to_fit: true }] };
}

export function newTextLayer(order: number): Layer {
  return { id: crypto.randomUUID(), order, type: "text", x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 12,
    rotation: 0, text: "{{name}}", font_family: "Gilroy", font_weight: 600, font_size_pt: 14,
    align: "left", shrink_to_fit: true, colour_token: "ink" };
}

export function reorder(layers: Layer[], from: number, to: number): Layer[] {
  if (to < 0 || to >= layers.length) return layers;
  const copy = [...layers]; const [moving] = copy.splice(from, 1); copy.splice(to, 0, moving);
  return copy.map((layer, order) => ({ ...layer, order }));
}

export function duplicate(layers: Layer[], id: string): Layer[] {
  if (layers.length >= 20) return layers;
  const layer = layers.find((item) => item.id === id);
  return layer ? [...layers, { ...layer, id: crypto.randomUUID(), order: layers.length }] : layers;
}

export function safeDesignExport(document: LayerDocument): string {
  // Designs contain typed slots. Never export print snapshots, owner photos or live QR values.
  return JSON.stringify(document, null, 2);
}
