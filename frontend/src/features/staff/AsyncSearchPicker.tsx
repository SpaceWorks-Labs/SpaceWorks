import { useEffect, useId, useRef, useState } from "react";

export type PickerOption = { id: number; label: string; detail?: string };

/** A search box that offers server results and keeps the chosen ones as removable chips.
 *
 * Presentational only: the caller owns the query (debounced term arrives via `onSearch`)
 * and the selection, so the same picker serves the create form, where nothing is saved
 * until submit, and the Team tab, where each change is a mutation.
 */
export function AsyncSearchPicker({ label, helper, placeholder, selected, options, loading = false, error,
  onSearch, onChange, disabled = false, emptyText = "No matches." }: {
  label: string; helper?: string; placeholder?: string; selected: PickerOption[]; options: PickerOption[];
  loading?: boolean; error?: string | null; onSearch: (term: string) => void;
  onChange: (next: PickerOption[]) => void; disabled?: boolean; emptyText?: string;
}) {
  const id = useId();
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const search = useRef(onSearch);
  search.current = onSearch;
  useEffect(() => {
    const timer = window.setTimeout(() => search.current(term.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [term]);
  const chosen = new Set(selected.map((row) => row.id));
  const choices = options.filter((row) => !chosen.has(row.id));
  const expanded = open && !disabled;
  const pick = (row: PickerOption) => { onChange([...selected, row]); setTerm(""); setActive(0); };
  const remove = (row: PickerOption) => onChange(selected.filter((entry) => entry.id !== row.id));

  return <div className="grid min-w-0 gap-2">
    <label className="text-sm font-semibold text-ink" htmlFor={`${id}-input`}>{label}</label>
    {helper ? <p className="text-sm text-muted" id={`${id}-helper`}>{helper}</p> : null}
    {selected.length ? <ul className="flex flex-wrap gap-2" aria-label={`Selected: ${label}`}>
      {selected.map((row) => <li key={row.id} className="flex min-h-9 items-center gap-1 rounded-full border border-line bg-surface py-1 pl-3 pr-1 text-sm text-ink">
        <span className="break-words">{row.label}</span>
        {!disabled ? <button type="button" className="grid size-7 place-items-center rounded-full text-muted hover:bg-hover hover:text-ink focus-visible:outline-2 focus-visible:outline-focus"
          aria-label={`Remove ${row.label}`} onClick={() => remove(row)}>×</button> : null}
      </li>)}
    </ul> : null}
    <div className="relative">
      <input id={`${id}-input`} className="desk-input w-full min-w-0" type="search" role="combobox" autoComplete="off"
        aria-expanded={expanded} aria-controls={`${id}-list`} aria-autocomplete="list"
        aria-describedby={helper ? `${id}-helper` : undefined}
        aria-activedescendant={expanded && choices[active] ? `${id}-option-${choices[active].id}` : undefined}
        placeholder={placeholder} value={term} disabled={disabled}
        onFocus={() => setOpen(true)} onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => { setTerm(event.target.value); setOpen(true); setActive(0); }}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") { event.preventDefault(); setOpen(true); setActive((value) => Math.min(value + 1, Math.max(choices.length - 1, 0))); }
          else if (event.key === "ArrowUp") { event.preventDefault(); setActive((value) => Math.max(value - 1, 0)); }
          else if (event.key === "Enter" && expanded && choices[active]) { event.preventDefault(); pick(choices[active]); }
          else if (event.key === "Escape") setOpen(false);
        }} />
      {expanded ? <ul id={`${id}-list`} role="listbox" aria-label={label}
        className="absolute inset-x-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-xl border border-line bg-panel p-1 shadow-lg">
        {loading ? <li className="p-3 text-sm text-muted" role="presentation">Searching…</li>
          : !choices.length ? <li className="p-3 text-sm text-muted" role="presentation">{emptyText}</li>
          : choices.map((row, index) => <li key={row.id} id={`${id}-option-${row.id}`} role="option" aria-selected={index === active}
            className={`flex min-h-11 cursor-pointer flex-col justify-center rounded-lg px-3 py-2 text-sm ${index === active ? "bg-hover" : ""}`}
            onMouseDown={(event) => { event.preventDefault(); pick(row); }} onMouseEnter={() => setActive(index)}>
            <span className="font-semibold text-ink">{row.label}</span>
            {row.detail ? <span className="code-text text-xs text-muted">{row.detail}</span> : null}
          </li>)}
      </ul> : null}
    </div>
    {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
  </div>;
}
