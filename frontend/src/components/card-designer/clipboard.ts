// Copy, paste and duplicate for layers, inside the designer and across front and back.
// Every pasted layer gets a new id; groups get new ids too (copied together, they stay a
// group of their own; a lone member of a group pastes ungrouped), offset by 2 mm.
import type { CardDocument, Layer, SideName } from "./cardTypes";
import { newLayerId, round1 } from "./cardGeometry";
import { MAX_LAYERS, withSide } from "./designDocument";

export const PASTE_OFFSET_MM = 2;

/** Snapshots of the selected layers in stacking order. */
export function copyLayers(layers: Layer[], ids: string[]): Layer[] {
  const wanted = new Set(ids);
  return layers.filter((layer) => wanted.has(layer.id)).map((layer) => ({ ...layer }));
}

/** Add copies of `clip` to `side`. Returns the new document and the new ids (as many as fit under the layer cap). */
export function pasteLayers(document: CardDocument, side: SideName, clip: Layer[],
  options: { offsetMm?: number; rename?: boolean; makeId?: () => string } = {}): { document: CardDocument; ids: string[] } {
  const target = document[side];
  const room = Math.max(0, MAX_LAYERS - target.layers.length);
  const batch = clip.slice(0, room);
  if (!batch.length) return { document, ids: [] };
  const makeId = options.makeId ?? newLayerId;
  const offset = options.offsetMm ?? PASTE_OFFSET_MM;
  const groupSizes = new Map<string, number>();
  batch.forEach((layer) => { if (layer.group) groupSizes.set(layer.group, (groupSizes.get(layer.group) ?? 0) + 1); });
  const groupIds = new Map<string, string>();
  const copies = batch.map((layer): Layer => {
    let group: string | null = null;
    if (layer.group && (groupSizes.get(layer.group) ?? 0) > 1) {
      if (!groupIds.has(layer.group)) groupIds.set(layer.group, makeId());
      group = groupIds.get(layer.group)!;
    }
    return { ...layer, id: makeId(), group,
      name: options.rename && layer.name ? `${layer.name} copy`.slice(0, 40) : layer.name,
      x_mm: round1(Math.max(0, Math.min(layer.x_mm + offset, target.page_width_mm - layer.w_mm))),
      y_mm: round1(Math.max(0, Math.min(layer.y_mm + offset, target.page_height_mm - layer.h_mm))) };
  });
  return {
    document: withSide(document, side, (current) => ({ ...current, layers: [...current.layers, ...copies] })),
    ids: copies.map((layer) => layer.id),
  };
}

/** Duplicate the selection on its own side (Ctrl/Cmd+D). */
export function duplicateLayers(document: CardDocument, side: SideName, ids: string[]) {
  return pasteLayers(document, side, copyLayers(document[side].layers, ids), { rename: true });
}
