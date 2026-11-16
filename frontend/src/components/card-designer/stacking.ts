// Z-order for a selection (Canva "Position", Figma "Bring forward"): the layer list order IS the stacking order
// (later = on top), so these are pure reorders of `side.layers`. Selected layers keep their relative order.
import type { CardDocument, Layer, SideName } from "./cardTypes";
import { withSide } from "./designDocument";

export type StackOp = "forward" | "backward" | "front" | "back";

export function restackLayers(layers: Layer[], ids: string[], op: StackOp): Layer[] {
  const chosen = new Set(ids);
  if (!layers.some((layer) => chosen.has(layer.id))) return layers;
  if (op === "front" || op === "back") {
    const picked = layers.filter((layer) => chosen.has(layer.id));
    const rest = layers.filter((layer) => !chosen.has(layer.id));
    return op === "front" ? [...rest, ...picked] : [...picked, ...rest];
  }
  const next = [...layers];
  // Walk against the direction of travel so a run of selected layers moves as a block, one step past its neighbour.
  const indexes = next.map((_layer, index) => index);
  if (op === "forward") indexes.reverse();
  for (const index of indexes) {
    const target = op === "forward" ? index + 1 : index - 1;
    if (!chosen.has(next[index].id) || target < 0 || target >= next.length || chosen.has(next[target].id)) continue;
    [next[index], next[target]] = [next[target], next[index]];
  }
  return next;
}

/** The document with the selection restacked; the SAME document when nothing moves (so no empty undo step). */
export function restack(document: CardDocument, side: SideName, ids: string[], op: StackOp): CardDocument {
  const current = document[side].layers;
  const layers = restackLayers(current, ids, op);
  if (layers.every((layer, index) => layer === current[index])) return document;
  return withSide(document, side, (value) => ({ ...value, layers }));
}
