// The certificate side of the Card Studio (decision 315, spec section 12): a v3 document with kind "certificate".
// Old v2 closed layouts are compiled to v3 on load (the TypeScript twin of backend certificate_compile.compile_v2);
// nothing stored is rewritten until the designer saves, and every issued certificate keeps its own frozen snapshot.
import { t } from "@lingui/core/macro";

import type { CardDocument, Layer, LayerKind, Side } from "../../../components/card-designer/cardTypes";
import { newLayerId } from "../../../components/card-designer/cardGeometry";
import { nameParts } from "../../../components/card-designer/dataFields";
import { certificateSampleValues, type CertificateKind } from "./designer/samples";
import { layerColour, type Layer as V2Layer, type LayerDocument } from "./layout";

/** v2 camelCase tags -> the v3 snake_case certificate tags. */
const TAG_MAP: Record<string, string> = { eventDate: "event_date", issueDate: "issue_date", crewRole: "role" };
const mapTags = (text: string) => text.replace(/{{\s*([^{}]*?)\s*}}/g, (_m, tag: string) => `{{${TAG_MAP[tag] ?? tag}}}`);

export const CERTIFICATE_FIELDS = (): { key: string; label: string }[] => [
  { key: "recipient", label: t`Recipient name` }, { key: "first_name", label: t`Recipient first name` }, { key: "last_name", label: t`Recipient last name` },
  { key: "event", label: t`Event` }, { key: "event_date", label: t`Event date` }, { key: "issue_date", label: t`Issue date` },
  { key: "organisation", label: t`Organisation` }, { key: "role", label: t`Role` }, { key: "kind", label: t`Certificate kind` },
  { key: "award", label: t`Award` }, { key: "place", label: t`Place` }, { key: "hours", label: t`Hours` },
  { key: "achievement", label: t`Achievement` }, { key: "serial", label: t`Serial number` }, { key: "serial_short", label: t`Short serial` },
  { key: "verify_url", label: t`Verification link` },
];

const base = (kind: LayerKind, extra: Partial<Layer>): Layer => ({ id: newLayerId(), kind, name: "", x_mm: 0, y_mm: 0, w_mm: 40, h_mm: 10,
  rotation: 0, opacity: 100, locked: false, hidden: false, ...extra });

function compileLayer(layer: V2Layer): Layer | null {
  const geometry = { x_mm: layer.x_mm, y_mm: layer.y_mm, w_mm: layer.width_mm, h_mm: layer.height_mm, rotation: layer.rotation ?? 0,
    opacity: Math.round((layer.opacity ?? 1) * 100), locked: Boolean(layer.locked), hidden: Boolean(layer.hidden), id: layer.id };
  const text = { font_family: layer.font_family === "Gilroy" ? "Outfit" : layer.font_family ?? "Outfit", font_weight: layer.font_weight ?? 400,
    font_size_pt: layer.font_size_pt ?? 14, align: layer.align ?? "left", valign: "top" as const, colour: layerColour(layer),
    uppercase: Boolean(layer.uppercase), tracking_pt: layer.tracking_pt ?? 0, line_height: layer.line_height ?? 1.2, shrink_to_fit: layer.shrink_to_fit !== false };
  switch (layer.type) {
    case "text": return base("text", { ...geometry, ...text, text: mapTags(layer.text ?? "") });
    case "certificate_id": return base("certificate_id", { ...geometry, ...text, format: "full" });
    case "certificate_qr": return base("verify_qr", geometry);
    case "signature": return base("signature", { ...geometry, ...text, signatory_slot: layer.signature_slot ?? 1, align: "center",
      show_image: true, show_name: true, show_title: true, rule: { colour: text.colour, width_pt: 0.6 } });
    case "image": case "logo": return layer.resource_id ? base("image", { ...geometry, asset_id: layer.resource_id, fit: "contain" })
      : base("logo", { ...geometry, source: "space", tile: false });
    case "photo": return base("photo", { ...geometry, shape: "rounded", filter: "none", variant: "original" });
    default: return null;
  }
}

/** A blank certificate side: A4 landscape, 10 mm print margin as the editor's guide. */
export function blankSide(width = 297, height = 210, background: Side["background"] = { kind: "colour", colour: "#FFFFFF" }): Side {
  return { page_width_mm: width, page_height_mm: height, background, layers: [], groups: [], overlay: null };
}

export function certificateDocument(side: Side, stock = "a4-landscape", source: CardDocument["source"] = null): CardDocument {
  return { version: 3, kind: "certificate", stock, back_enabled: false, mono: false, source,
    watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: -30, colour: "#142C2A" },
    guides: { bleed_mm: 0, safe_mm: 10, margin_mm: 10, punch_slot: null, rulers: [] }, front: side, back: blankSide(side.page_width_mm, side.page_height_mm) };
}

export function stockForSize(width: number, height: number) {
  const known: [string, number, number][] = [["a4-landscape", 297, 210], ["a4-portrait", 210, 297], ["letter-landscape", 279.4, 215.9], ["letter-portrait", 215.9, 279.4],
    ["a5-landscape", 210, 148], ["a5-portrait", 148, 210]];
  return known.find(([, w, h]) => Math.abs(w - width) < 0.1 && Math.abs(h - height) < 0.1)?.[0] ?? "custom";
}

/** Compile a stored v2 layout (and its legacy artwork) to a Studio document. Unknown layer types are dropped. */
export function compileCertificateV2(layout: LayerDocument, hasArtwork = false): CardDocument {
  const layers = [...layout.layers].sort((a, b) => a.order - b.order).map(compileLayer).filter((layer): layer is Layer => layer !== null);
  const background: Side["background"] = hasArtwork ? { kind: "image", asset_id: LEGACY_ARTWORK, fit: "cover", dim_pct: 0, fallback: "#FFFFFF" }
    : { kind: "colour", colour: "#FFFFFF" };
  const side: Side = { ...blankSide(layout.page_width_mm, layout.page_height_mm, background), layers };
  const stock = stockForSize(layout.page_width_mm, layout.page_height_mm);
  const document = certificateDocument(side, stock, { kind: "certificate_v2" });
  return stock === "custom" ? { ...document, page_width_mm: layout.page_width_mm, page_height_mm: layout.page_height_mm } : document;
}
/** The placeholder asset id the studio's asset loader resolves to the revision's legacy background artwork. */
export const LEGACY_ARTWORK = "legacy-artwork";

/** Sample values for the canvas: the v3 certificate tags plus the signatories (consented ones only). */
export function certificateStudioValues(name: string, kind: CertificateKind | "", signatures: Record<number, { name: string; title: string } | undefined>) {
  const old = certificateSampleValues(name, kind);
  const serial = "3f9c2e17-7b64-4d10-9c0e-5d2f8b6a1e37";
  const values: Record<string, string> = { ...old, recipient: name, ...nameParts(name), event_date: old.eventDate, issue_date: old.issueDate,
    hours: "6.5", achievement: old.award, serial, serial_short: serial.slice(0, 8).toUpperCase(), verify_url: "example.org/certificates/verify/…" }; // i18n-ignore: placeholder sample data
  for (const slot of [1, 2, 3]) {
    values[`signatory_${slot}_name`] = signatures[slot]?.name ?? "";
    values[`signatory_${slot}_title`] = signatures[slot]?.title ?? "";
  }
  return values;
}
