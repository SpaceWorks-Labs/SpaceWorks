// Align and distribute. Each group in the selection moves as one unit; a unit holding a
// locked layer never moves. One unit aligns to the card, several align to the selection's
// bounds; "to the safe area" aligns everything to the 3 mm safe area instead.
import { t } from "@lingui/core/macro";
import type { Layer, Side } from "./cardTypes";
import { round1, SAFE_AREA_MM } from "./cardGeometry";
import { boundsOf, moveUnits, selectedLayers, type Box, type Patches } from "./selection";

export type AlignEdge = "left" | "centre" | "right" | "top" | "middle" | "bottom";
export type DistributeAxis = "horizontal" | "vertical";

/** Button names, by target (a function so they follow the language switch). */
export function alignLabel(edge: AlignEdge, target: "card" | "selection" | "safe"): string {
  const labels: Record<AlignEdge, Record<typeof target, string>> = {
    left: { card: t`Align left edges to the card`, selection: t`Align left edges to the selection`, safe: t`Align left edges to the safe area` },
    centre: { card: t`Align centres to the card`, selection: t`Align centres to the selection`, safe: t`Align centres to the safe area` },
    right: { card: t`Align right edges to the card`, selection: t`Align right edges to the selection`, safe: t`Align right edges to the safe area` },
    top: { card: t`Align top edges to the card`, selection: t`Align top edges to the selection`, safe: t`Align top edges to the safe area` },
    middle: { card: t`Align middles to the card`, selection: t`Align middles to the selection`, safe: t`Align middles to the safe area` },
    bottom: { card: t`Align bottom edges to the card`, selection: t`Align bottom edges to the selection`, safe: t`Align bottom edges to the safe area` },
  };
  return labels[edge][target];
}

function shift(unit: Layer[], dx: number, dy: number, patches: Patches) {
  if (unit.some((layer) => layer.locked) || (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001)) return;
  for (const layer of unit) patches[layer.id] = { x_mm: round1(layer.x_mm + dx), y_mm: round1(layer.y_mm + dy) };
}

/** The safe area: the document's safe zone (`guides.safe_mm`, 3 mm by default, 10 mm on certificates). */
export function safeBox(side: Side, safeMm = SAFE_AREA_MM): Box {
  return { x: safeMm, y: safeMm, w: side.page_width_mm - 2 * safeMm, h: side.page_height_mm - 2 * safeMm };
}

export function alignTarget(side: Side, ids: string[], toSafeArea: boolean, safeMm = SAFE_AREA_MM): Box | null {
  const layers = selectedLayers(side, ids);
  if (!layers.length) return null;
  if (toSafeArea) return safeBox(side, safeMm);
  if (moveUnits(layers).length === 1) return { x: 0, y: 0, w: side.page_width_mm, h: side.page_height_mm };
  return boundsOf(layers);
}

export function alignLayers(side: Side, ids: string[], edge: AlignEdge, toSafeArea = false, safeMm = SAFE_AREA_MM): Patches {
  const target = alignTarget(side, ids, toSafeArea, safeMm);
  const patches: Patches = {};
  if (!target) return patches;
  for (const unit of moveUnits(selectedLayers(side, ids))) {
    const box = boundsOf(unit)!;
    const dx = edge === "left" ? target.x - box.x : edge === "right" ? target.x + target.w - (box.x + box.w)
      : edge === "centre" ? target.x + target.w / 2 - (box.x + box.w / 2) : 0;
    const dy = edge === "top" ? target.y - box.y : edge === "bottom" ? target.y + target.h - (box.y + box.h)
      : edge === "middle" ? target.y + target.h / 2 - (box.y + box.h / 2) : 0;
    shift(unit, dx, dy, patches);
  }
  return patches;
}

/** Equal gaps between three or more units; the outermost two stay put. Overlapping units spread their centres evenly. */
export function distributeLayers(side: Side, ids: string[], axis: DistributeAxis): Patches {
  const patches: Patches = {};
  const units = moveUnits(selectedLayers(side, ids)).map((unit) => ({ unit, box: boundsOf(unit)! }));
  if (units.length < 3) return patches;
  const start = (box: Box) => (axis === "horizontal" ? box.x : box.y);
  const size = (box: Box) => (axis === "horizontal" ? box.w : box.h);
  units.sort((a, b) => start(a.box) + size(a.box) / 2 - (start(b.box) + size(b.box) / 2));
  const first = units[0].box, last = units[units.length - 1].box;
  const span = start(last) + size(last) - start(first);
  const gap = (span - units.reduce((sum, item) => sum + size(item.box), 0)) / (units.length - 1);
  let cursor = start(first);
  const firstCentre = start(first) + size(first) / 2;
  const step = (start(last) + size(last) / 2 - firstCentre) / (units.length - 1);
  units.forEach((item, index) => {
    const at = gap >= 0 ? cursor : firstCentre + step * index - size(item.box) / 2;
    cursor += size(item.box) + gap;
    if (index === 0 || index === units.length - 1) return;
    const delta = at - start(item.box);
    shift(item.unit, axis === "horizontal" ? delta : 0, axis === "vertical" ? delta : 0, patches);
  });
  return patches;
}
