// The bar above the canvas: align, distribute, group and zoom. Align works on one layer
// (to the card) or several (to their bounds); "Safe area" aligns to the 3 mm safe area instead.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { AlignCenterHorizontal, AlignCenterVertical, AlignEndHorizontal, AlignEndVertical,
  AlignHorizontalDistributeCenter, AlignStartHorizontal, AlignStartVertical, AlignVerticalDistributeCenter, Group,
  Ungroup, type LucideIcon } from "lucide-react";

import { SegmentedControl } from "../ui/SegmentedControl";
import type { Side } from "./cardTypes";
import { ALIGN_LABELS, type AlignEdge } from "./alignment";
import { ZOOMS, type Zoom } from "./canvasMath";
import { moveUnits, selectedLayers } from "./selection";
import type { DesignerEditing } from "./useDesignerEditing";

const ALIGN: { edge: AlignEdge; icon: LucideIcon }[] = [
  { edge: "left", icon: AlignStartVertical }, { edge: "centre", icon: AlignCenterVertical },
  { edge: "right", icon: AlignEndVertical }, { edge: "top", icon: AlignStartHorizontal },
  { edge: "middle", icon: AlignCenterHorizontal }, { edge: "bottom", icon: AlignEndHorizontal },
];
const tool = "desk-button-ghost min-h-11 min-w-11 px-2 disabled:opacity-40";

export function CanvasToolbar({ side, selection, editing, zoom, onZoom }: {
  side: Side; selection: string[]; editing: DesignerEditing; zoom: Zoom; onZoom: (zoom: Zoom) => void;
}) {
  const [toSafe, setToSafe] = useState(false);
  const layers = selectedLayers(side, selection).filter((layer) => !layer.hidden);
  const units = moveUnits(layers);
  const canMove = editing.canEdit && units.some((unit) => unit.every((layer) => !layer.locked));
  const target = toSafe ? "the safe area" : units.length > 1 ? "the selection" : "the card";
  return <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
    <div role="toolbar" aria-label={t`Arrange`} className="flex flex-wrap items-center gap-1">
      {ALIGN.map(({ edge, icon: Icon }) => <button key={edge} type="button" className={tool} disabled={!canMove}
        aria-label={`${ALIGN_LABELS[edge]} to ${target}`} title={`${ALIGN_LABELS[edge]} to ${target}`}
        onClick={() => editing.align(edge, toSafe)}><Icon size={18} aria-hidden="true" /></button>)}
      <span aria-hidden="true" className="mx-1 h-6 w-px bg-line" />
      <button type="button" className={tool} disabled={!canMove || units.length < 3} title={t`Space evenly across`}
        aria-label={t`Space evenly across (three or more)`} onClick={() => editing.distribute("horizontal")}>
        <AlignHorizontalDistributeCenter size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!canMove || units.length < 3} title={t`Space evenly down`}
        aria-label={t`Space evenly down (three or more)`} onClick={() => editing.distribute("vertical")}>
        <AlignVerticalDistributeCenter size={18} aria-hidden="true" /></button>
      <span aria-hidden="true" className="mx-1 h-6 w-px bg-line" />
      <button type="button" className={tool} disabled={!editing.canEdit || selection.length < 2} title={t`Group (Ctrl or Cmd + G)`}
        aria-label={t`Group the selection`} onClick={editing.group}><Group size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!editing.canEdit || !layers.some((layer) => layer.group)}
        title={t`Ungroup (Shift + Ctrl or Cmd + G)`} aria-label={t`Ungroup`} onClick={editing.ungroup}>
        <Ungroup size={18} aria-hidden="true" /></button>
      <label className="flex min-h-11 items-center gap-2 px-1 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={toSafe}
          onChange={(event) => setToSafe(event.target.checked)} />
        {t`To safe area`}</label>
    </div>
    <div className="ml-auto">
      <SegmentedControl label={t`Zoom`} value={String(zoom)} onChange={(value) => onZoom(value === "fit" ? "fit" : Number(value) as Zoom)}
        options={ZOOMS.map((item) => ({ value: String(item.value), label: item.label }))} />
    </div>
  </div>;
}
