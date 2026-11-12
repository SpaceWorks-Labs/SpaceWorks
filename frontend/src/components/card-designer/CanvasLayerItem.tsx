// One layer on the free canvas: the focusable, selectable box (a keyboard stop), its drawing, and for a single
// unlocked selection the resize (bottom-right) and rotate (top) handles. The canvas owns the drag logic.
import { t } from "@lingui/core/macro";
import type { PointerEvent as ReactPointerEvent } from "react";

import type { Layer } from "./cardTypes";
import { CardLayerView } from "./CardLayerView";
import { layerName } from "./designDocument";
import type { PhotoState } from "./photoVariant";

export type DragMode = "move" | "resize" | "rotate";
const handle = "absolute grid h-11 w-11 touch-none place-items-center";
const dot = "h-4 w-4 rounded-full border-2 border-white bg-accent-ink shadow";

function label(layer: Layer, group: string | null) {
  const name = layerName(layer);
  if (layer.locked && group) return t`${name} layer, locked, group ${group}`;
  if (layer.locked) return t`${name} layer, locked`;
  return group ? t`${name} layer, group ${group}` : t`${name} layer`;
}

export function CanvasLayerItem({ layer, px, values, designId, mono, photoState, selected, handles, readOnly, group, hintId,
  onBegin, onFocus }: {
  layer: Layer; px: number; values: Record<string, string>; designId: number; mono: boolean; photoState?: PhotoState;
  selected: boolean; handles: boolean; readOnly: boolean; group: string | null; hintId: string;
  onBegin: (event: ReactPointerEvent, layer: Layer, mode: DragMode) => void; onFocus: (layer: Layer) => void;
}) {
  return <div role="button" tabIndex={readOnly ? -1 : 0} aria-describedby={hintId} aria-label={label(layer, group)}
    aria-pressed={selected}
    className={`absolute touch-none focus-visible:outline-2 focus-visible:outline-focus ${selected ? "outline outline-2 outline-accent-ink" : ""} ${layer.locked ? "cursor-not-allowed" : "cursor-grab"}`}
    style={{ left: layer.x_mm * px, top: layer.y_mm * px, width: layer.w_mm * px, height: layer.h_mm * px,
      transform: `rotate(${layer.rotation}deg)`, opacity: (layer.opacity ?? 100) / 100 }}
    onPointerDown={(event) => onBegin(event, layer, "move")} onFocus={() => onFocus(layer)}>
    <CardLayerView layer={layer} px={px} values={values} designId={designId} mono={mono} photoState={photoState} />
    {handles ? <>
      <span aria-hidden="true" className={`${handle} -bottom-[22px] -right-[22px] cursor-nwse-resize`}
        onPointerDown={(event) => onBegin(event, layer, "resize")}><span className={dot} /></span>
      <span aria-hidden="true" className={`${handle} -top-[34px] left-1/2 -translate-x-1/2 cursor-grab`}
        onPointerDown={(event) => onBegin(event, layer, "rotate")}><span className={dot} /></span>
    </> : null}
  </div>;
}
