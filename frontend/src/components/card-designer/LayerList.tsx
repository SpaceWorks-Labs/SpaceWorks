// The side's layers, top of the stack first: select, reorder, hide, lock, duplicate, delete.
import { ArrowDown, ArrowUp, Copy, Eye, EyeOff, Lock, LockOpen, Trash2 } from "lucide-react";

import type { Layer } from "./cardTypes";
import { layerName } from "./designDocument";

export function LayerList({ layers, selectedId, onSelect, onPatch, onMove, onDuplicate, onRemove, readOnly }: {
  layers: Layer[]; selectedId: string | null; onSelect: (id: string) => void;
  onPatch: (id: string, patch: Partial<Layer>) => void; onMove: (id: string, direction: "up" | "down") => void;
  onDuplicate: (id: string) => void; onRemove: (id: string) => void; readOnly: boolean;
}) {
  if (!layers.length) return <p className="text-sm text-muted">No layers on this side yet. Add one above.</p>;
  const ordered = [...layers].reverse();
  const tool = "grid h-11 w-11 place-items-center rounded-control text-muted hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-40";
  return <ol className="grid gap-1" aria-label="Layers, top first">
    {ordered.map((layer, position) => {
      const name = layerName(layer);
      const selected = layer.id === selectedId;
      return <li key={layer.id} className={`flex items-center gap-1 rounded-control border ${selected ? "border-accent-ink bg-accent-soft" : "border-transparent"}`}>
        <button type="button" aria-pressed={selected} onClick={() => onSelect(layer.id)}
          className={`min-h-11 min-w-0 flex-1 truncate px-2 text-left text-sm ${layer.hidden ? "text-muted line-through" : "text-ink"}`}>
          {name}
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
          <button type="button" className={tool} aria-label={`Duplicate ${name}`} disabled={layers.length >= 40}
            onClick={() => onDuplicate(layer.id)}><Copy size={16} aria-hidden="true" /></button>
          <button type="button" className={`${tool} hover:text-danger`} aria-label={`Delete ${name}`} disabled={layer.locked}
            onClick={() => onRemove(layer.id)}><Trash2 size={16} aria-hidden="true" /></button>
        </> : null}
      </li>;
    })}
  </ol>;
}
