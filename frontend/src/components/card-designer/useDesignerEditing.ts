// Everything the designer does to the current selection, as one place the canvas, the layer
// list, the inspector, the align toolbar and the keyboard all call. Each action is ONE undo step.
import { useCallback, useRef } from "react";

import type { CardDocument, Layer, Side, SideName } from "./cardTypes";
import { round1 } from "./cardGeometry";
import { alignLayers, distributeLayers, type AlignEdge, type DistributeAxis } from "./alignment";
import { minimumSize, moveSelection } from "./canvasMath";
import { copyLayers, duplicateLayers, pasteLayers } from "./clipboard";
import { addLayer, moveLayer, moveLayerTo, setGroupMeta } from "./designDocument";
import { restack, type StackOp } from "./stacking";
import { groupLayers, moveUnits, patchLayers, removeLayers, selectAll, selectedLayers, ungroupLayers,
  type Patches } from "./selection";

type Update = (change: (current: CardDocument) => CardDocument, record?: boolean) => void;

export function useDesignerEditing({ update, sideName, side, stock, selection, setSelection, canEdit, safeMm }: {
  update: Update; sideName: SideName; side: Side; stock: string; selection: string[];
  setSelection: (ids: string[]) => void; canEdit: boolean; /** The document's safe zone (guides.safe_mm). */ safeMm?: number;
}) {
  const clipboard = useRef<Layer[]>([]);
  const patch = useCallback((patches: Patches, record = true) =>
    update((current) => patchLayers(current, sideName, patches), record), [update, sideName]);
  const movable = () => moveUnits(selectedLayers(side, selection).filter((layer) => !layer.hidden))
    .filter((unit) => unit.every((layer) => !layer.locked)).flat();

  return {
    patch,
    patchOne: (id: string, change: Partial<Layer>) => patch({ [id]: change }),
    selectAll: () => setSelection(selectAll(side)),
    clear: () => setSelection([]),
    add: (layer: Layer) => { update((current) => addLayer(current, sideName, layer)); setSelection([layer.id]); },
    groupMeta: (id: string, change: Partial<{ name: string; locked: boolean; hidden: boolean }>) => update((current) => setGroupMeta(current, sideName, id, change)),
    reorderTo: (id: string, to: number) => update((current) => moveLayerTo(current, sideName, id, to)),
    reorder: (id: string, direction: "up" | "down") => update((current) => moveLayer(current, sideName, id, direction)),
    group: () => { if (selection.length > 1) update((current) => groupLayers(current, sideName, selection)); },
    ungroup: () => update((current) => ungroupLayers(current, sideName, selection)),
    remove: (ids = selection) => {
      update((current) => removeLayers(current, sideName, ids));
      setSelection(selection.filter((id) => !ids.includes(id) || side.layers.find((layer) => layer.id === id)?.locked));
    },
    duplicate: (ids = selection) => {
      if (!ids.length) return;
      let created: string[] = [];
      update((current) => { const result = duplicateLayers(current, sideName, ids); created = result.ids; return result.document; });
      if (created.length) setSelection(created);
    },
    copy: () => { clipboard.current = copyLayers(side.layers, selection); return clipboard.current.length; },
    canPaste: () => clipboard.current.length > 0,
    paste: () => {
      if (!clipboard.current.length) return;
      let created: string[] = [];
      let pasted: Layer[] = [];
      update((current) => {
        const result = pasteLayers(current, sideName, clipboard.current);
        created = result.ids;
        pasted = result.document[sideName].layers.filter((layer) => result.ids.includes(layer.id));
        return result.document;
      });
      // The next paste lands a further 2 mm along, like most editors.
      if (created.length) { clipboard.current = pasted; setSelection(created); }
    },
    nudge: (dx: number, dy: number) => {
      const layers = movable();
      if (layers.length) patch(moveSelection(side, layers, dx, dy, { gridMm: 1, free: true }).patches);
    },
    resizeBy: (dw: number, dh: number) => {
      const patches: Patches = {};
      for (const layer of selectedLayers(side, selection).filter((item) => !item.locked && !item.hidden)) {
        const min = minimumSize(layer, stock, side);
        const square = layer.kind === "desk_qr" || layer.kind === "verify_qr";
        const w = Math.min(side.page_width_mm - layer.x_mm, Math.max(min.w, round1(layer.w_mm + (square ? dw || dh : dw))));
        const h = square ? w : Math.min(side.page_height_mm - layer.y_mm, Math.max(min.h, round1(layer.h_mm + dh)));
        patches[layer.id] = { w_mm: w, h_mm: h };
      }
      patch(patches);
    },
    align: (edge: AlignEdge, toSafeArea: boolean) => patch(alignLayers(side, selection, edge, toSafeArea, safeMm)),
    distribute: (axis: DistributeAxis) => patch(distributeLayers(side, selection, axis)),
    setFlag: (flag: "locked" | "hidden", value: boolean) =>
      patch(Object.fromEntries(selection.map((id) => [id, { [flag]: value }]))),
    /** Lock (or hide) the whole selection, or undo it when every selected layer already is. */
    toggleFlag: (flag: "locked" | "hidden") => {
      const chosen = selectedLayers(side, selection);
      const value = !chosen.every((layer) => layer[flag]);
      patch(Object.fromEntries(chosen.map((layer) => [layer.id, { [flag]: value }])));
    },
    restack: (op: StackOp) => { if (selection.length) update((current) => restack(current, sideName, selection, op)); },
    canEdit,
  };
}

export type DesignerEditing = ReturnType<typeof useDesignerEditing>;
