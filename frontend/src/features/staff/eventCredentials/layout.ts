import { t } from "@lingui/core/macro";
import type { PositionedElement } from "../../../components/print-layout/positionedLayout";

export type Layer = {
  id: string; order: number; type: "text" | "image" | "logo" | "photo" | "certificate_id" | "certificate_qr" | "event_credential_qr" | "signature";
  x_mm: number; y_mm: number; width_mm: number; height_mm: number; rotation: number;
  text?: string; font_family?: "Gilroy" | "Unbounded"; font_weight?: 400 | 500 | 600 | 700;
  font_size_pt?: number; align?: "left" | "center" | "right"; shrink_to_fit?: boolean;
  italic?: boolean; uppercase?: boolean; tracking_pt?: number; line_height?: number;
  opacity?: number; resource_id?: string; resource_slot?: string; colour_token?: string;
  /** Free #RRGGBB text colour; overrides colour_token. */ colour?: string;
  /** Signature layers print signatory 1, 2 or 3. */ signature_slot?: 1 | 2 | 3;
  locked?: boolean; hidden?: boolean;
};
/** Brand colour tokens (backend certificates/layout.py COLOURS): presets beside the free colour. */
export const COLOUR_TOKENS: Record<string, string> = { ink: "#142C2A", teal: "#006E63", orange: "#FF7447",
  citron: "#DFFF8F", sky: "#B5CDFF", yellow: "#FFD447", cream: "#FFF4E8" };
export const layerColour = (layer: Layer) => layer.colour ?? COLOUR_TOKENS[layer.colour_token ?? "ink"] ?? COLOUR_TOKENS.ink;
/** Page sizes in millimetres (width x height). Custom keeps 100-420 mm. */
export const PAGE_PRESETS = {
  "a4-landscape": { label: t`A4 landscape`, size: [297, 210] }, "a4-portrait": { label: t`A4 portrait`, size: [210, 297] },
  "letter-landscape": { label: t`US Letter landscape`, size: [279.4, 215.9] }, "letter-portrait": { label: t`US Letter portrait`, size: [215.9, 279.4] },
} as const;
export type PagePreset = keyof typeof PAGE_PRESETS | "custom";
export function pagePreset(width: number, height: number): PagePreset {
  const match = Object.entries(PAGE_PRESETS).find(([, value]) => Math.abs(value.size[0] - width) < 0.05 && Math.abs(value.size[1] - height) < 0.05);
  return (match?.[0] as PagePreset | undefined) ?? "custom";
}
/** Fit every layer inside a new page size: scale positions, keep sizes where they still fit. */
export function resizePage(document: LayerDocument, width: number, height: number): LayerDocument {
  const sx = width / document.page_width_mm, sy = height / document.page_height_mm;
  return { ...document, page_width_mm: width, page_height_mm: height, layers: document.layers.map((layer) => {
    const floor = layer.type.endsWith("qr") ? 20 : 0.1;  // Verification QR codes stay scannable.
    const w = Math.min(Math.max(floor, layer.width_mm * Math.min(sx, sy)), width);
    const h = Math.min(Math.max(floor, layer.height_mm * Math.min(sx, sy)), height);
    const round = (value: number) => Math.round(value * 10) / 10;
    return { ...layer, width_mm: round(w), height_mm: round(h),
      x_mm: round(Math.min(Math.max(0, layer.x_mm * sx), width - w)), y_mm: round(Math.min(Math.max(0, layer.y_mm * sy), height - h)) };
  }) };
}
export type LayerDocument = { version: 2; page_width_mm: number; page_height_mm: number; layers: Layer[] };
export type LegacyDocument = { version: 1; page_width_mm: number; page_height_mm: number; name_box: PositionedElement };
export const MERGE_TAGS = ["name", "event", "eventDate", "organisation", "issueDate", "crewRole"] as const;
/** Certificates also print the frozen kind, award, role and place labels. */
export const CERTIFICATE_MERGE_TAGS = ["name", "kind", "award", "place", "role", "event", "eventDate", "organisation", "issueDate"] as const;
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
