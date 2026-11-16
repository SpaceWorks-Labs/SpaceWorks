// Multi-select and groups on one side. A selection is an ordered list of layer ids; the
// last one is the "primary" layer the inspector shows. Layers sharing a `group` id select
// and move together; Alt-click reaches a single member.
import type { CardDocument, Layer, Side, SideName } from "./cardTypes";
import { newLayerId } from "./cardGeometry";
import { withSide } from "./designDocument";

export type Box = { x: number; y: number; w: number; h: number };
export type Patches = Record<string, Partial<Layer>>;

/** The ids that select together with `id`: its group, or just itself. */
export function groupMembers(layers: Layer[], id: string): string[] {
  const layer = layers.find((item) => item.id === id);
  if (!layer?.group) return layer ? [id] : [];
  return layers.filter((item) => item.group === layer.group).map((item) => item.id);
}

/** The selection after a click: plain replaces (keeping a selection the click is part of, so it
 *  can be dragged), Shift/Ctrl/Cmd toggles, Alt reaches one member of a group. */
export function clickSelection(layers: Layer[], current: string[], id: string,
  modifiers: { additive?: boolean; single?: boolean } = {}): string[] {
  const targets = modifiers.single ? [id] : groupMembers(layers, id);
  if (!targets.length) return current;
  if (modifiers.additive) {
    if (targets.every((target) => current.includes(target))) return current.filter((item) => !targets.includes(item));
    return [...current.filter((item) => !targets.includes(item)), ...targets.filter((t) => t !== id), id];
  }
  if (!modifiers.single && current.includes(id)) return current;
  return [...targets.filter((target) => target !== id), id];
}

/** Every visible layer on the side (locked ones too: they never move, but can be aligned to). */
export function selectAll(side: Side): string[] {
  return side.layers.filter((layer) => !layer.hidden).map((layer) => layer.id);
}

/** Drop ids that no longer exist on the side (after an undo, a delete or a side switch). */
export function pruneSelection(side: Side, ids: string[]): string[] {
  const present = new Set(side.layers.map((layer) => layer.id));
  const kept = ids.filter((id) => present.has(id));
  return kept.length === ids.length ? ids : kept;
}

export function selectedLayers(side: Side, ids: string[]): Layer[] {
  const wanted = new Set(ids);
  return side.layers.filter((layer) => wanted.has(layer.id));
}

/** The box around every layer (rotation ignored, as the snapping and the clamp do). */
export function boundsOf(layers: Layer[]): Box | null {
  if (!layers.length) return null;
  const left = Math.min(...layers.map((layer) => layer.x_mm));
  const top = Math.min(...layers.map((layer) => layer.y_mm));
  const right = Math.max(...layers.map((layer) => layer.x_mm + layer.w_mm));
  const bottom = Math.max(...layers.map((layer) => layer.y_mm + layer.h_mm));
  return { x: left, y: top, w: right - left, h: bottom - top };
}

export function patchLayers(document: CardDocument, side: SideName, patches: Patches): CardDocument {
  if (!Object.keys(patches).length) return document;
  return withSide(document, side, (current) => ({
    ...current, layers: current.layers.map((layer) => (patches[layer.id] ? { ...layer, ...patches[layer.id] } : layer)),
  }));
}

/** Remove the selected layers that are not locked. */
export function removeLayers(document: CardDocument, side: SideName, ids: string[]): CardDocument {
  const doomed = new Set(document[side].layers.filter((layer) => ids.includes(layer.id) && !layer.locked).map((layer) => layer.id));
  if (!doomed.size) return document;
  return withSide(document, side, (current) => ({ ...current, layers: current.layers.filter((layer) => !doomed.has(layer.id)) }));
}

/** Give the selection one fresh group id (needs two or more layers). */
export function groupLayers(document: CardDocument, side: SideName, ids: string[], groupId = newLayerId()): CardDocument {
  if (ids.length < 2) return document;
  return patchLayers(document, side, Object.fromEntries(ids.map((id) => [id, { group: groupId }])));
}

export function ungroupLayers(document: CardDocument, side: SideName, ids: string[]): CardDocument {
  const grouped = document[side].layers.filter((layer) => ids.includes(layer.id) && layer.group);
  if (!grouped.length) return document;
  return patchLayers(document, side, Object.fromEntries(grouped.map((layer) => [layer.id, { group: null }])));
}

/** Short names for the side's groups, in stacking order: "A", "B", … */
export function groupLabels(layers: Layer[]): Record<string, string> {
  const labels: Record<string, string> = {};
  for (const layer of layers) {
    if (layer.group && !labels[layer.group]) {
      const index = Object.keys(labels).length;
      labels[layer.group] = index < 26 ? String.fromCharCode(65 + index) : String(index + 1);
    }
  }
  return labels;
}

/** The selection as move units: each group (of selected members) is one unit, each loose layer another. */
export function moveUnits(layers: Layer[]): Layer[][] {
  const units = new Map<string, Layer[]>();
  for (const layer of layers) {
    const key = layer.group ? `g:${layer.group}` : `l:${layer.id}`;
    units.set(key, [...(units.get(key) ?? []), layer]);
  }
  return [...units.values()];
}
