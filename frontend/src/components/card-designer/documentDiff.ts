// What changed between two versions of a design (decision 345(d)): per side, layers added, removed and changed (with
// the kinds of change), plus background, overlay, stacking-order and card-wide changes. Pure, so it is testable.
import { t } from "@lingui/core/macro";

import type { CardDocument, Layer, SideName } from "./cardTypes";
import { layerName } from "./designDocument";

export type ChangeKind = "position" | "size" | "rotation" | "text" | "colour" | "font" | "visibility" | "effects" | "other";
export type LayerChange = { id: string; name: string; kinds: ChangeKind[] };
export type SideDiff = { added: Layer[]; removed: Layer[]; changed: LayerChange[]; background: boolean; overlay: boolean;
  reordered: boolean };
export type DocumentDiff = { front: SideDiff; back: SideDiff; card: ("stock" | "two_sided" | "mono" | "watermark")[] };

const KIND_OF: Record<string, ChangeKind> = {
  x_mm: "position", y_mm: "position", w_mm: "size", h_mm: "size", rotation: "rotation",
  text: "text", spans: "text", field: "text", translations: "text", label: "text", ring_text: "text", format: "text",
  colour: "colour", fill: "colour", stroke: "colour", fill_gradient: "colour", duotone_dark: "colour", duotone_light: "colour",
  ring_text_colour: "colour", font_family: "font", font_weight: "font", font_size_pt: "font", tracking_pt: "font",
  line_height: "font", uppercase: "font", align: "font", valign: "font", hidden: "visibility", locked: "visibility",
  opacity: "visibility", shadow: "effects", outline: "effects", highlight: "effects", underline: "effects", mask: "effects",
  filter: "effects", zoom: "effects", focal_x_pct: "effects", focal_y_pct: "effects",
};
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

function layerChange(before: Layer, after: Layer): LayerChange | null {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  const kinds = new Set<ChangeKind>();
  for (const key of keys) {
    if (key === "id" || key === "name" || key === "group") continue;
    if (!same((before as Record<string, unknown>)[key], (after as Record<string, unknown>)[key])) kinds.add(KIND_OF[key] ?? "other");
  }
  if (!same(before.name, after.name)) kinds.add("other");
  return kinds.size ? { id: after.id, name: layerName(after), kinds: [...kinds].sort() } : null;
}

export function diffSide(a: CardDocument, b: CardDocument, side: SideName): SideDiff {
  const before = new Map(a[side].layers.map((layer) => [layer.id, layer]));
  const after = new Map(b[side].layers.map((layer) => [layer.id, layer]));
  const kept = b[side].layers.filter((layer) => before.has(layer.id)).map((layer) => layer.id);
  const keptBefore = a[side].layers.filter((layer) => after.has(layer.id)).map((layer) => layer.id);
  return {
    added: b[side].layers.filter((layer) => !before.has(layer.id)),
    removed: a[side].layers.filter((layer) => !after.has(layer.id)),
    changed: b[side].layers.flatMap((layer) => {
      const old = before.get(layer.id);
      const change = old ? layerChange(old, layer) : null;
      return change ? [change] : [];
    }),
    background: !same(a[side].background, b[side].background),
    overlay: !same(a[side].overlay, b[side].overlay),
    reordered: !same(kept, keptBefore),
  };
}

export function diffDocuments(a: CardDocument, b: CardDocument): DocumentDiff {
  const card: DocumentDiff["card"] = [];
  if (a.stock !== b.stock || a.page_width_mm !== b.page_width_mm || a.page_height_mm !== b.page_height_mm) card.push("stock");
  if (a.back_enabled !== b.back_enabled) card.push("two_sided");
  if (a.mono !== b.mono) card.push("mono");
  if (!same(a.watermark, b.watermark)) card.push("watermark");
  return { front: diffSide(a, b, "front"), back: diffSide(a, b, "back"), card };
}

export const isUnchanged = (diff: DocumentDiff) => !diff.card.length && (["front", "back"] as const).every((side) => {
  const d = diff[side];
  return !d.added.length && !d.removed.length && !d.changed.length && !d.background && !d.overlay && !d.reordered;
});

export function changeLabel(kind: ChangeKind) {
  return { position: t`moved`, size: t`resized`, rotation: t`turned`, text: t`text`, colour: t`colour`, font: t`type style`,
    visibility: t`shown, locked or opacity`, effects: t`effects or framing`, other: t`other settings` }[kind];
}
