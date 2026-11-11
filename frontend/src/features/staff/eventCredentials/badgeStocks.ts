// Badge stocks and the badge design file (SPEC §3.1, G13). The six frozen stocks have packaged
// default designs; A6 landscape and a custom size (40-300 mm, 0.1 mm steps) start blank or
// from an imported file. Mirrors apps/events/certificates/layout.py DESIGN_STOCK_CHOICES.
import { t } from "@lingui/core/macro";
import { SAMPLE_LONG, SAMPLE_SHORT } from "../../../components/card-designer/dataFields";
import { STOCKS, type LayerDocument, type Stock } from "./layout";

export type DesignStock = Stock | "a6-landscape" | "custom";
export const DESIGN_STOCKS: Record<Exclude<DesignStock, "custom">, readonly [number, number]> = {
  ...STOCKS, "a6-landscape": [148, 105],
};
export const CUSTOM_RANGE_MM = [40, 300] as const;
export const DESIGN_FILE_KIND = "spaceworks-badge-design";

export const isSeedable = (stock: DesignStock): stock is Stock => stock in STOCKS;

export function stockSize(stock: DesignStock, custom: { width: number; height: number }) {
  return stock === "custom" ? [custom.width, custom.height] as const : DESIGN_STOCKS[stock];
}

export function validCustomSide(value: number) {
  return Number.isFinite(value) && value >= CUSTOM_RANGE_MM[0] && value <= CUSTOM_RANGE_MM[1]
    && Math.abs(value * 10 - Math.round(value * 10)) < 1e-6;
}

/** A blank badge: the name, the event and the typed check-in QR slot every desk badge needs. */
export function blankBadge(width: number, height: number): LayerDocument {
  const qr = Math.max(20, Math.min(30, Math.min(width, height) * 0.4));
  return { version: 2, page_width_mm: width, page_height_mm: height, layers: [
    { id: crypto.randomUUID(), order: 0, type: "text", x_mm: 5, y_mm: 5, width_mm: Math.max(10, width - 10), height_mm: 12,
      rotation: 0, text: "{{name}}", font_family: "Outfit", font_weight: 700, font_size_pt: 16, align: "left",
      shrink_to_fit: true, colour_token: "ink" },
    { id: crypto.randomUUID(), order: 1, type: "text", x_mm: 5, y_mm: 19, width_mm: Math.max(10, width - 10), height_mm: 8,
      rotation: 0, text: "{{event}}", font_family: "Outfit", font_weight: 500, font_size_pt: 9, align: "left",
      shrink_to_fit: true, colour_token: "ink" },
    { id: crypto.randomUUID(), order: 2, type: "event_credential_qr", x_mm: width - qr - 5, y_mm: height - qr - 5,
      width_mm: qr, height_mm: qr, rotation: 0, resource_slot: "event_credential_qr" },
  ] };
}

/** The versioned design file: kind, version, stock and the person-free document. */
export function badgeDesignFile(document: LayerDocument, stock: DesignStock) {
  return JSON.stringify({ kind: DESIGN_FILE_KIND, version: 2, stock, document }, null, 2);
}

/** Read a design file (or a bare version-2 document from before files had a kind). The server validates on save. */
export function parseBadgeDesignFile(text: string): { document: LayerDocument; stock: DesignStock | null } {
  let parsed: unknown;
  try { parsed = JSON.parse(text); } catch { throw new Error(t`Choose a valid JSON design file.`); }
  if (!parsed || typeof parsed !== "object") throw new Error(t`Choose a valid JSON design file.`);
  const value = parsed as { kind?: unknown; version?: unknown; stock?: unknown; document?: unknown; layers?: unknown };
  if (value.kind !== undefined) {
    if (value.kind !== DESIGN_FILE_KIND) throw new Error(t`This file is not a Space Works badge design.`);
    if (value.version !== 2) throw new Error(t`This design file is from a newer version. Update and try again.`);
    const stock = typeof value.stock === "string" && (value.stock in DESIGN_STOCKS || value.stock === "custom")
      ? value.stock as DesignStock : null;
    return { document: value.document as LayerDocument, stock };
  }
  if (value.version === 2 && Array.isArray(value.layers)) return { document: parsed as LayerDocument, stock: null };
  throw new Error(t`This file is not a Space Works badge design.`);
}

/** Preview values for the merge tags: a typical name and a very long one, to test fitting. */
export function badgeSampleValues(long: boolean): Record<string, string> {
  const sample = long ? SAMPLE_LONG : SAMPLE_SHORT;
  return { name: sample.name, event: sample.event, organisation: sample.organisation,
    eventDate: long ? "Saturday 18 October 2026" : "18 Oct 2026", issueDate: "18 Oct 2026" };
}

export function mergeTags(text: string, values: Record<string, string>) {
  return text.replace(/{{\s*([A-Za-z]+)\s*}}/g, (match, tag: string) => values[tag] ?? match);
}
