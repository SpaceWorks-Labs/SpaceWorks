// Preflight: what to fix before printing, checked as you edit. Errors are what the server
// refuses on publish (contrast, QR and barcode sizes); warnings are what tends to print badly.
import { plural, t } from "@lingui/core/macro";
import type { CardDocument, CardDomain, Layer, Side, SideName } from "./cardTypes";
import { qrMinimum, SAFE_AREA_MM } from "./cardGeometry";
import { layerContrast, MINIMUM_RATIO } from "./contrast";
import { BARCODE_MIN_HEIGHT_MM, BARCODE_MIN_WIDTH_MM, layerName } from "./designDocument";

export type Severity = "error" | "warn" | "info";
export type Issue = { id: string; severity: Severity; side: SideName; layerId: string | null; message: string };

const TEXT = new Set(["text", "data_field"]);
const isQr = (layer: Layer) => layer.kind === "desk_qr" || layer.kind === "verify_qr";
const visible = (side: Side) => side.layers.filter((layer) => !layer.hidden);
const quote = (layer: Layer) => `“${layerName(layer)}”`;

function overlaps(a: Layer, b: Layer) {
  const w = Math.min(a.x_mm + a.w_mm, b.x_mm + b.w_mm) - Math.max(a.x_mm, b.x_mm);
  const h = Math.min(a.y_mm + a.h_mm, b.y_mm + b.h_mm) - Math.max(a.y_mm, b.y_mm);
  return w > 0.3 && h > 0.3;
}

function hasName(layer: Layer) {
  return TEXT.has(layer.kind) && (layer.field === "name" || /{{\s*name\s*}}/.test(layer.text ?? ""));
}

function checkSide(side: Side, name: SideName, stock: string, assetColours: Record<string, string>): Issue[] {
  const issues: Issue[] = [];
  const add = (rule: string, severity: Severity, layer: Layer | null, message: string) =>
    issues.push({ id: `${rule}:${name}:${layer?.id ?? "side"}`, severity, side: name, layerId: layer?.id ?? null, message });
  const shown = visible(side);
  const texts: Layer[] = [];
  side.layers.forEach((layer, index) => {
    if (layer.hidden) return;
    if (TEXT.has(layer.kind)) {
      if (layer.x_mm < SAFE_AREA_MM - 0.05 || layer.y_mm < SAFE_AREA_MM - 0.05
        || layer.x_mm + layer.w_mm > side.page_width_mm - SAFE_AREA_MM + 0.05
        || layer.y_mm + layer.h_mm > side.page_height_mm - SAFE_AREA_MM + 0.05) {
        add("safe", "warn", layer, t`${quote(layer)} is outside the ${SAFE_AREA_MM} mm safe area, so the edge of the card may cut it.`);
      }
      const contrast = layerContrast(side, index, assetColours);
      if (contrast !== null && contrast < MINIMUM_RATIO) {
        add("contrast", "error", layer, t`${quote(layer)} is hard to read (${contrast.toFixed(1)}:1). Publishing needs ${MINIMUM_RATIO}:1.`);
      }
      const under = texts.find((other) => overlaps(other, layer));
      if (under) add("overlap", "warn", layer, t`${quote(layer)} overlaps ${quote(under)}.`);
      texts.push(layer);
    }
    if (isQr(layer)) {
      const minimum = qrMinimum(stock);
      if (Math.min(layer.w_mm, layer.h_mm) < minimum - 0.05) {
        add("qr-size", "error", layer, t`${quote(layer)} is smaller than ${minimum} mm, so some phones cannot read it.`);
      }
      if (layer.rotation % 90 !== 0) add("qr-angle", "error", layer, t`${quote(layer)} must be square-on: turn it by right angles only.`);
    }
    if (layer.kind === "barcode") {
      const minimum = BARCODE_MIN_WIDTH_MM[layer.source === "desk" ? "desk" : "number"];
      if (minimum > side.page_width_mm - 2 * SAFE_AREA_MM) {
        add("barcode-card", "error", layer, t`This card is too narrow for ${quote(layer)}: it needs ${minimum} mm. Use a landscape or larger card.`);
      } else if (layer.w_mm < minimum - 0.05 || layer.h_mm < BARCODE_MIN_HEIGHT_MM - 0.05) {
        add("barcode-size", "error", layer, t`${quote(layer)} needs at least ${minimum} × ${BARCODE_MIN_HEIGHT_MM} mm for a scanner to read it.`);
      }
    }
  });
  const hidden = side.layers.length - shown.length;
  if (hidden) {
    add("hidden", "info", null, name === "front"
      ? plural(hidden, { one: "# hidden layer on the front will not print.", other: "# hidden layers on the front will not print." })
      : plural(hidden, { one: "# hidden layer on the back will not print.", other: "# hidden layers on the back will not print." }));
  }
  return issues;
}

export function preflight(document: CardDocument, domain: CardDomain, assetColours: Record<string, string> = {}): Issue[] {
  const issues = checkSide(document.front, "front", document.stock, assetColours);
  if (document.back_enabled) {
    issues.push(...checkSide(document.back, "back", document.stock, assetColours));
    if (!visible(document.back).length) {
      issues.push({ id: "back-empty", severity: "warn", side: "back", layerId: null,
        message: t`The back is switched on but has nothing on it. Add layers or switch two-sided off.` });
    }
  }
  if (!visible(document.front).some(hasName)) {
    issues.push({ id: "no-name", severity: "warn", side: "front", layerId: null,
      message: t`The front has no name on it. Add a Name data field or {{name}} in a text layer.` });
  }
  if (domain === "member_cards") {
    const all = [...visible(document.front), ...(document.back_enabled ? visible(document.back) : [])];
    if (!all.some((layer) => isQr(layer) || layer.kind === "barcode")) {
      issues.push({ id: "no-code", severity: "warn", side: "front", layerId: null,
        message: t`Nothing on this card can be scanned. Add a desk QR or barcode for the desk, or a check QR.` });
    }
  }
  const order: Record<Severity, number> = { error: 0, warn: 1, info: 2 };
  return issues.sort((a, b) => order[a.severity] - order[b.severity]);
}

/** The number on the toolbar badge: errors and warnings (notes do not count). */
export function issueCount(issues: Issue[]) {
  return issues.filter((issue) => issue.severity !== "info").length;
}
