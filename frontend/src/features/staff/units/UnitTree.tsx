import { t } from "@lingui/core/macro";
import { useState, type DragEvent } from "react";

import { OverflowMenu, StatusPill } from "../../../components/ui";
import { canMoveUnder, levelLabel, orderedUnits, usableLevels } from "./unitHierarchy";
import type { MemberUnit } from "./unitsApi";

export type UnitTreeActions = {
  onEdit: (unit: MemberUnit) => void; onAddChild: (unit: MemberUnit) => void; onMove: (unit: MemberUnit) => void;
  onDropMove: (unit: MemberUnit, parentId: number | null) => void; onArchive: (unit: MemberUnit) => void; onRestore: (unit: MemberUnit) => void;
};

/**
 * The unit tree as an indented list. With `editable`, a row can be dragged onto another unit (or the
 * top-level strip) to move it; drop targets light up only where the move can succeed. The same move is
 * available to keyboard and touch users from each row's menu ("Move…").
 */
export function UnitTree({ units, levels, editable, busy, actions }: {
  units: readonly MemberUnit[]; levels: readonly string[]; editable: boolean; busy: boolean; actions: UnitTreeActions;
}) {
  const [dragging, setDragging] = useState<MemberUnit | null>(null);
  const [over, setOver] = useState<number | "top" | null>(null);
  const rows = orderedUnits(units);
  const hasChildren = new Set(units.filter(unit => !unit.archived && unit.parent_id !== null).map(unit => unit.parent_id));
  const allowed = (parentId: number | null) => Boolean(dragging) && dragging!.parent_id !== parentId
    && canMoveUnder(units, levels, dragging!.id, parentId);
  const target = (parentId: number | null) => ({
    onDragOver: (event: DragEvent) => { if (allowed(parentId)) { event.preventDefault(); setOver(parentId ?? "top"); } },
    onDragLeave: () => setOver(null),
    onDrop: (event: DragEvent) => {
      event.preventDefault();
      if (dragging && allowed(parentId)) actions.onDropMove(dragging, parentId);
      setDragging(null); setOver(null);
    },
  });
  const wait = busy ? t`Wait for the last change to finish.` : undefined;
  const levelName = (level: number) => levelLabel(levels, level, n => t`Level ${n}`);
  return <div className="grid gap-2">
    {editable && dragging ? <div {...target(null)} aria-hidden
      className={`rounded-xl border border-dashed p-3 text-center text-sm ${over === "top" ? "border-accent bg-surface text-ink" : "border-line text-muted"}`}>
      {allowed(null) ? t`Drop here to make ${dragging.name} a top-level unit` : t`${dragging.name} can't move to the top level`}
    </div> : null}
    <ul className="grid gap-1" aria-label={t`Member units`}>
      {rows.map(unit => {
        const deepest = unit.level + 1 >= usableLevels(levels);
        const droppable = editable && dragging && allowed(unit.id);
        return <li key={unit.id} {...(editable ? target(unit.id) : {})}
          draggable={editable && !unit.archived && !busy}
          onDragStart={event => { event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", String(unit.id)); setDragging(unit); }}
          onDragEnd={() => { setDragging(null); setOver(null); }}
          style={{ marginInlineStart: `${unit.depth * 1.5}rem` }}
          className={`flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border px-3 py-2 ${over === unit.id ? "border-accent bg-surface" : "border-line"} ${droppable ? "outline-dashed outline-1 outline-line" : ""} ${unit.archived ? "opacity-70" : ""} ${editable && !unit.archived ? "cursor-grab active:cursor-grabbing" : ""}`}>
          <span className="grid min-w-0 flex-1 gap-0.5">
            <span className="flex min-w-0 flex-wrap items-center gap-2">
              <span className="font-semibold text-ink [overflow-wrap:anywhere]">{unit.name}</span>
              <code className="rounded border border-line px-1.5 text-xs tabular-nums text-muted">{unit.code}</code>
            </span>
            <span className="text-xs text-muted">{levelName(unit.level)}{unit.has_payment_instructions ? ` · ${t`Own payment instructions`}` : ""}</span>
          </span>
          {unit.archived ? <StatusPill tone="neutral" label={t`Archived`} /> : null}
          {editable ? <OverflowMenu label={t`Actions for ${unit.name}`} actions={unit.archived
            ? [{ label: t`Restore`, disabled: busy, disabledReason: wait, onClick: () => actions.onRestore(unit) }]
            : [
              { label: t`Edit`, onClick: () => actions.onEdit(unit) },
              ...(deepest ? [] : [{ label: t`Add ${levelName(unit.level + 1)} here`, onClick: () => actions.onAddChild(unit) }]),
              { label: t`Move…`, disabled: busy, disabledReason: wait, onClick: () => actions.onMove(unit) },
              { label: t`Archive`, tone: "danger" as const, disabled: busy || hasChildren.has(unit.id),
                disabledReason: hasChildren.has(unit.id) ? t`Archive the units beneath it first.` : wait,
                confirm: { title: t`Archive ${unit.name}?`, message: t`Members already in ${unit.name} keep it; nobody new can join it. You can restore it later.` },
                onClick: () => actions.onArchive(unit) },
            ]} /> : null}
        </li>;
      })}
    </ul>
  </div>;
}
