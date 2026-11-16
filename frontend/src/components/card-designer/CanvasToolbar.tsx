// The bar above the canvas: align, distribute, stack order, group, lock and hide. Align works on one layer
// (to the card) or several (to their bounds); "To safe area" aligns to the document's safe zone instead.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { AlignCenterHorizontal, AlignCenterVertical, AlignEndHorizontal, AlignEndVertical,
  AlignHorizontalDistributeCenter, AlignStartHorizontal, AlignStartVertical, AlignVerticalDistributeCenter, ArrowDownToLine,
  ArrowUpToLine, ChevronDown, ChevronUp, EyeOff, Group, Lock, Ungroup, type LucideIcon } from "lucide-react";

import type { Side } from "./cardTypes";
import { alignLabel, type AlignEdge } from "./alignment";
import { moveUnits, selectedLayers } from "./selection";
import type { StackOp } from "./stacking";
import type { DesignerEditing } from "./useDesignerEditing";

const ALIGN: { edge: AlignEdge; icon: LucideIcon }[] = [
  { edge: "left", icon: AlignStartVertical }, { edge: "centre", icon: AlignCenterVertical },
  { edge: "right", icon: AlignEndVertical }, { edge: "top", icon: AlignStartHorizontal },
  { edge: "middle", icon: AlignCenterHorizontal }, { edge: "bottom", icon: AlignEndHorizontal },
];
const tool = "desk-button-ghost min-h-11 min-w-11 px-2 disabled:opacity-40";
const Divider = () => <span aria-hidden="true" className="mx-1 h-6 w-px bg-line" />;

function stackButtons(): { op: StackOp; icon: LucideIcon; label: string }[] {
  return [
    { op: "front", icon: ArrowUpToLine, label: t`Bring to front (Shift + Ctrl or Cmd + ])` },
    { op: "forward", icon: ChevronUp, label: t`Bring forward (Ctrl or Cmd + ])` },
    { op: "backward", icon: ChevronDown, label: t`Send backward (Ctrl or Cmd + [)` },
    { op: "back", icon: ArrowDownToLine, label: t`Send to back (Shift + Ctrl or Cmd + [)` },
  ];
}

export function CanvasToolbar({ side, selection, editing }: {
  side: Side; selection: string[]; editing: DesignerEditing;
}) {
  const [toSafe, setToSafe] = useState(false);
  const layers = selectedLayers(side, selection).filter((layer) => !layer.hidden);
  const units = moveUnits(layers);
  const canMove = editing.canEdit && units.some((unit) => unit.every((layer) => !layer.locked));
  const target = toSafe ? "safe" : units.length > 1 ? "selection" : "card";
  const any = editing.canEdit && selection.length > 0;
  const allLocked = selection.length > 0 && selectedLayers(side, selection).every((layer) => layer.locked);
  return <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
    <div role="toolbar" aria-label={t`Arrange`} className="flex flex-wrap items-center gap-1">
      {ALIGN.map(({ edge, icon: Icon }) => <button key={edge} type="button" className={tool} disabled={!canMove}
        aria-label={alignLabel(edge, target)} title={alignLabel(edge, target)}
        onClick={() => editing.align(edge, toSafe)}><Icon size={18} aria-hidden="true" /></button>)}
      <Divider />
      <button type="button" className={tool} disabled={!canMove || units.length < 3} title={t`Space evenly across`}
        aria-label={t`Space evenly across (three or more)`} onClick={() => editing.distribute("horizontal")}>
        <AlignHorizontalDistributeCenter size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!canMove || units.length < 3} title={t`Space evenly down`}
        aria-label={t`Space evenly down (three or more)`} onClick={() => editing.distribute("vertical")}>
        <AlignVerticalDistributeCenter size={18} aria-hidden="true" /></button>
      <Divider />
      {stackButtons().map(({ op, icon: Icon, label }) => <button key={op} type="button" className={tool} disabled={!any}
        aria-label={label} title={label} onClick={() => editing.restack(op)}><Icon size={18} aria-hidden="true" /></button>)}
      <Divider />
      <button type="button" className={tool} disabled={!editing.canEdit || selection.length < 2} title={t`Group (Ctrl or Cmd + G)`}
        aria-label={t`Group the selection`} onClick={editing.group}><Group size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!editing.canEdit || !layers.some((layer) => layer.group)}
        title={t`Ungroup (Shift + Ctrl or Cmd + G)`} aria-label={t`Ungroup`} onClick={editing.ungroup}>
        <Ungroup size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!any} aria-pressed={allLocked}
        title={t`Lock or unlock (Shift + Ctrl or Cmd + L)`} aria-label={t`Lock the selection`} onClick={() => editing.toggleFlag("locked")}>
        <Lock size={18} aria-hidden="true" /></button>
      <button type="button" className={tool} disabled={!any}
        title={t`Hide (Shift + Ctrl or Cmd + H); show it again from the Layers list`} aria-label={t`Hide the selection`}
        onClick={() => editing.toggleFlag("hidden")}><EyeOff size={18} aria-hidden="true" /></button>
      <label className="flex min-h-11 items-center gap-2 px-1 text-sm text-ink">
        <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={toSafe}
          onChange={(event) => setToSafe(event.target.checked)} />
        {t`To safe area`}</label>
    </div>
  </div>;
}
