import { t } from "@lingui/core/macro";
import { ArrowDown, ArrowUp, GripVertical } from "lucide-react";
import { useState } from "react";

/** Move `from` to `to` in a copy of `items`. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return items;
  const next = items.slice();
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

type Props<K extends string> = { all: K[]; value: K[]; label: (key: K) => string; onChange: (next: K[]) => void; legend: string };

/**
 * Pick and order sections. Selected ones are the shown list, in order; drag a row by its handle, or use the
 * up/down buttons (the keyboard and touch path). Unselected ones sit below with only their checkbox.
 */
export function PanelOrderEditor<K extends string>({ all, value, label, onChange, legend }: Props<K>) {
  const [dragging, setDragging] = useState<number | null>(null);
  const rest = all.filter((key) => !value.includes(key));
  const toggle = (key: K, on: boolean) => onChange(on ? [...value, key] : value.filter((k) => k !== key));
  return <fieldset className="grid gap-1"><legend className="text-sm font-semibold text-ink">{legend}</legend>
    <ol className="grid gap-1">
      {value.map((key, index) => <li key={key} draggable onDragStart={() => setDragging(index)} onDragEnd={() => setDragging(null)}
        onDragOver={(event) => event.preventDefault()}
        onDrop={() => { if (dragging !== null) onChange(moveItem(value, dragging, index)); setDragging(null); }}
        className="flex min-h-11 items-center gap-2 rounded-lg border border-line bg-panel px-2">
        <GripVertical aria-hidden="true" size={18} className="shrink-0 cursor-grab text-muted" />
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3 text-sm">
          <input type="checkbox" className="h-5 w-5 accent-accent" checked onChange={() => toggle(key, false)} />
          <span className="truncate">{label(key)}</span>
        </label>
        <button type="button" className="desk-button min-w-11 px-2" aria-label={t`Move ${label(key)} up`} disabled={index === 0}
          onClick={() => onChange(moveItem(value, index, index - 1))}><ArrowUp aria-hidden="true" size={18} /></button>
        <button type="button" className="desk-button min-w-11 px-2" aria-label={t`Move ${label(key)} down`} disabled={index === value.length - 1}
          onClick={() => onChange(moveItem(value, index, index + 1))}><ArrowDown aria-hidden="true" size={18} /></button>
      </li>)}
    </ol>
    {rest.map((key) => <label key={key} className="flex min-h-11 items-center gap-3 px-2 text-sm text-muted">
      <input type="checkbox" className="h-5 w-5 accent-accent" checked={false} onChange={() => toggle(key, true)} />{label(key)}
    </label>)}
  </fieldset>;
}
