// The side's layers, top of the stack first: select (Shift/Ctrl/Cmd adds, Alt picks one in a
// group), reorder, hide, lock, duplicate, delete. Grouped layers carry their group letter.
import { t } from "@lingui/core/macro";
import { Fragment, useState, type DragEvent, type KeyboardEvent, type MouseEvent } from "react";
import { ArrowDown, ArrowUp, Copy, Eye, EyeOff, Lock, LockOpen, Pencil, Trash2 } from "lucide-react";

import type { Layer } from "./cardTypes";
import type { LayerGroup } from "./cardTypes";
import { layerName, MAX_LAYERS } from "./designDocument";
import { groupLabels } from "./selection";

export type PickModifiers = { additive: boolean; single: boolean };

export function LayerList({ groups = [], onGroupMeta, layers, selection, onPick, onPatch, onMove, onMoveTo, onDuplicate, onRemove, readOnly }: {
  groups?: LayerGroup[]; onGroupMeta?: (id: string, change: Partial<{ name: string; locked: boolean; hidden: boolean }>) => void;
  layers: Layer[]; selection: string[]; onPick: (id: string, modifiers: PickModifiers) => void;
  onPatch: (id: string, patch: Partial<Layer>) => void; onMove: (id: string, direction: "up" | "down") => void;
  onMoveTo?: (id: string, to: number) => void;
  onDuplicate: (id: string) => void; onRemove: (id: string) => void; readOnly: boolean;
}) {
  const [dragging, setDragging] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  if (!layers.length) return <p className="text-sm text-muted">{t`No layers on this side yet. Add one above.`}</p>;
  const ordered = [...layers].reverse();
  const labels = groupLabels(layers);
  const tool = "grid h-11 w-11 shrink-0 place-items-center rounded-control text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-40";
  const drop = (event: DragEvent, targetIndex: number) => {
    event.preventDefault();
    if (dragging && onMoveTo) onMoveTo(dragging, targetIndex);
    setDragging(null);
  };
  // Alt + Up/Down moves the focused layer in the stack: the keyboard twin of dragging.
  const keyMove = (event: KeyboardEvent, id: string) => {
    if (!event.altKey || readOnly || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
    event.preventDefault();
    onMove(id, event.key === "ArrowUp" ? "up" : "down");
  };
  const pick = (id: string, event: MouseEvent) =>
    onPick(id, { additive: event.shiftKey || event.ctrlKey || event.metaKey, single: event.altKey });
  return <div className="grid gap-2">
    <p className="text-xs text-muted">{t`Shift-click to select several. Grouped layers share a letter. Drag a row, or press Alt with the arrow keys, to reorder.`}</p>
    <ol className="@container grid gap-1" aria-label={t`Layers, top first`}>
      {ordered.map((layer, position) => {
        const name = layerName(layer);
        const selected = selection.includes(layer.id);
        const group = layer.group ? labels[layer.group] : null;
        const stackIndex = layers.length - 1 - position;
        const firstOfGroup = layer.group && ordered.findIndex((item) => item.group === layer.group) === position;
        const groupRow = layer.group ? groups.find((item) => item.id === layer.group) : undefined;
        const header = firstOfGroup && layer.group && onGroupMeta ? <li key={`group-${layer.group}`} role="presentation"
          className="mt-1 flex flex-wrap items-center gap-1 rounded-control bg-surface px-2">
          <span aria-hidden="true" className="grid h-5 min-w-5 place-items-center rounded border border-accent-ink px-1 text-[11px] font-bold text-accent-ink">{labels[layer.group]}</span>
          <input className="desk-input m-1 min-h-11 min-w-0 flex-1" maxLength={40} aria-label={t`Name of group ${labels[layer.group]}`} disabled={readOnly}
            defaultValue={groupRow?.name ?? ""} placeholder={t`Group ${labels[layer.group]}`}
            onBlur={(event) => { if (event.target.value !== (groupRow?.name ?? "")) onGroupMeta(layer.group as string, { name: event.target.value }); }} />
          {!readOnly ? <>
            <button type="button" className={tool} aria-label={groupRow?.hidden ? t`Show group ${labels[layer.group]}` : t`Hide group ${labels[layer.group]}`}
              onClick={() => onGroupMeta(layer.group as string, { hidden: !groupRow?.hidden })}>
              {groupRow?.hidden ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}</button>
            <button type="button" className={tool} aria-label={groupRow?.locked ? t`Unlock group ${labels[layer.group]}` : t`Lock group ${labels[layer.group]}`}
              onClick={() => onGroupMeta(layer.group as string, { locked: !groupRow?.locked })}>
              {groupRow?.locked ? <Lock size={16} aria-hidden="true" /> : <LockOpen size={16} aria-hidden="true" />}</button>
          </> : null}
        </li> : null;
        return <Fragment key={layer.id}>{header}<li draggable={!readOnly && !layer.locked}
          onDragStart={() => setDragging(layer.id)} onDragEnd={() => setDragging(null)}
          onDragOver={(event) => { if (dragging) event.preventDefault(); }} onDrop={(event) => drop(event, stackIndex)}
          className={`flex flex-wrap items-center justify-end gap-x-1 rounded-control border ${selected ? "border-accent-ink bg-accent-soft" : "border-transparent"} ${dragging === layer.id ? "opacity-50" : ""}`}>
          {renaming === layer.id ? <input autoFocus className="desk-input m-1 min-h-11 min-w-0 flex-1" maxLength={40} aria-label={t`Layer name`}
            defaultValue={layer.name} placeholder={name}
            onBlur={(event) => { onPatch(layer.id, { name: event.target.value }); setRenaming(null); }}
            onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); if (event.key === "Escape") setRenaming(null); }} />
          : <button type="button" aria-pressed={selected} onClick={(event) => pick(layer.id, event)} onKeyDown={(event) => keyMove(event, layer.id)}
            aria-label={`${name}${group ? `, group ${group}` : ""}${layer.hidden ? ", hidden" : ""}${layer.locked ? ", locked" : ""}`}
            className={`flex min-h-11 min-w-0 flex-1 basis-full items-center gap-2 px-2 text-left text-sm @md:basis-0 focus-visible:outline-2 focus-visible:outline-focus ${layer.hidden ? "text-muted line-through" : "text-ink"}`}>
            {group ? <span aria-hidden="true" title={t`Group ${group}`}
              className="grid h-5 min-w-5 shrink-0 place-items-center rounded border border-accent-ink px-1 text-[11px] font-bold text-accent-ink">{group}</span> : null}
            <span className="truncate">{name}</span>
          </button>}
          {!readOnly ? <>
            <button type="button" className={tool} aria-label={t`Rename ${name}`} onClick={() => setRenaming(layer.id)}>
              <Pencil size={16} aria-hidden="true" /></button>
            <button type="button" className={tool} aria-label={t`Move ${name} up`} disabled={position === 0}
              onClick={() => onMove(layer.id, "up")}><ArrowUp size={16} aria-hidden="true" /></button>
            <button type="button" className={tool} aria-label={t`Move ${name} down`} disabled={position === ordered.length - 1}
              onClick={() => onMove(layer.id, "down")}><ArrowDown size={16} aria-hidden="true" /></button>
            <button type="button" className={tool} aria-label={layer.hidden ? t`Show ${name}` : t`Hide ${name}`}
              onClick={() => onPatch(layer.id, { hidden: !layer.hidden })}>
              {layer.hidden ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}</button>
            <button type="button" className={tool} aria-label={layer.locked ? t`Unlock ${name}` : t`Lock ${name}`}
              onClick={() => onPatch(layer.id, { locked: !layer.locked })}>
              {layer.locked ? <Lock size={16} aria-hidden="true" /> : <LockOpen size={16} aria-hidden="true" />}</button>
            <button type="button" className={tool} aria-label={t`Duplicate ${name}`} disabled={layers.length >= MAX_LAYERS}
              onClick={() => onDuplicate(layer.id)}><Copy size={16} aria-hidden="true" /></button>
            <button type="button" className={`${tool} hover:text-danger`} aria-label={t`Delete ${name}`} disabled={layer.locked}
              onClick={() => onRemove(layer.id)}><Trash2 size={16} aria-hidden="true" /></button>
          </> : null}
        </li></Fragment>;
      })}
    </ol>
  </div>;
}
