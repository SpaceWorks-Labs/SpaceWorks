// The side's layers, top of the stack first: select (Shift/Ctrl/Cmd adds, Alt picks one in a
// group), reorder, hide, lock, duplicate, delete. Grouped layers carry their group letter.
import type { MouseEvent } from "react";
import { ArrowDown, ArrowUp, Copy, Eye, EyeOff, Lock, LockOpen, Trash2 } from "lucide-react";

import type { Layer } from "./cardTypes";
import { layerName, MAX_LAYERS } from "./designDocument";
import { groupLabels } from "./selection";

export type PickModifiers = { additive: boolean; single: boolean };

export function LayerList({ layers, selection, onPick, onPatch, onMove, onDuplicate, onRemove, readOnly }: {
  layers: Layer[]; selection: string[]; onPick: (id: string, modifiers: PickModifiers) => void;
  onPatch: (id: string, patch: Partial<Layer>) => void; onMove: (id: string, direction: "up" | "down") => void;
  onDuplicate: (id: string) => void; onRemove: (id: string) => void; readOnly: boolean;
}) {
  if (!layers.length) return <p className="text-sm text-muted">No layers on this side yet. Add one above.</p>;
  const ordered = [...layers].reverse();
  const labels = groupLabels(layers);
  const tool = "grid h-11 w-11 shrink-0 place-items-center rounded-control text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-40";
  const pick = (id: string, event: MouseEvent) =>
    onPick(id, { additive: event.shiftKey || event.ctrlKey || event.metaKey, single: event.altKey });
  return <div className="grid gap-2">
    <p className="text-xs text-muted">Shift-click to select several. Grouped layers share a letter.</p>
    <ol className="@container grid gap-1" aria-label="Layers, top first">
      {ordered.map((layer, position) => {
        const name = layerName(layer);
        const selected = selection.includes(layer.id);
        const group = layer.group ? labels[layer.group] : null;
        return <li key={layer.id} className={`flex flex-wrap items-center justify-end gap-x-1 rounded-control border ${selected ? "border-accent-ink bg-accent-soft" : "border-transparent"}`}>
          <button type="button" aria-pressed={selected} onClick={(event) => pick(layer.id, event)}
            aria-label={`${name}${group ? `, group ${group}` : ""}${layer.hidden ? ", hidden" : ""}${layer.locked ? ", locked" : ""}`}
            className={`flex min-h-11 min-w-0 flex-1 basis-full items-center gap-2 px-2 text-left text-sm @md:basis-0 focus-visible:outline-2 focus-visible:outline-focus ${layer.hidden ? "text-muted line-through" : "text-ink"}`}>
            {group ? <span aria-hidden="true" title={`Group ${group}`}
              className="grid h-5 min-w-5 shrink-0 place-items-center rounded border border-accent-ink px-1 text-[11px] font-bold text-accent-ink">{group}</span> : null}
            <span className="truncate">{name}</span>
          </button>
          {!readOnly ? <>
            <button type="button" className={tool} aria-label={`Move ${name} up`} disabled={position === 0}
              onClick={() => onMove(layer.id, "up")}><ArrowUp size={16} aria-hidden="true" /></button>
            <button type="button" className={tool} aria-label={`Move ${name} down`} disabled={position === ordered.length - 1}
              onClick={() => onMove(layer.id, "down")}><ArrowDown size={16} aria-hidden="true" /></button>
            <button type="button" className={tool} aria-label={layer.hidden ? `Show ${name}` : `Hide ${name}`}
              onClick={() => onPatch(layer.id, { hidden: !layer.hidden })}>
              {layer.hidden ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}</button>
            <button type="button" className={tool} aria-label={layer.locked ? `Unlock ${name}` : `Lock ${name}`}
              onClick={() => onPatch(layer.id, { locked: !layer.locked })}>
              {layer.locked ? <Lock size={16} aria-hidden="true" /> : <LockOpen size={16} aria-hidden="true" />}</button>
            <button type="button" className={tool} aria-label={`Duplicate ${name}`} disabled={layers.length >= MAX_LAYERS}
              onClick={() => onDuplicate(layer.id)}><Copy size={16} aria-hidden="true" /></button>
            <button type="button" className={`${tool} hover:text-danger`} aria-label={`Delete ${name}`} disabled={layer.locked}
              onClick={() => onRemove(layer.id)}><Trash2 size={16} aria-hidden="true" /></button>
          </> : null}
        </li>;
      })}
    </ol>
  </div>;
}
