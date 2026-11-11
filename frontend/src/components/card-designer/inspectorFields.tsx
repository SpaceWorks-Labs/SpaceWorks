// Small labelled inputs the inspector and background panel share.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

const HEX = /^#[0-9A-Fa-f]{6}$/;

export function NumberInput({ label, value, min, max, step = 0.5, unit, onChange, disabled }: {
  label: string; value: number; min: number; max: number; step?: number; unit?: string;
  onChange: (value: number) => void; disabled?: boolean;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  function commit(text: string) {
    const parsed = Number(text);
    if (text.trim() === "" || !Number.isFinite(parsed)) { setDraft(String(value)); return; }
    onChange(Math.min(max, Math.max(min, parsed)));
  }
  return <label className="grid gap-1 text-xs font-semibold text-muted">
    <span>{label}{unit ? <span className="font-normal"> ({unit})</span> : null}</span>
    <input className="desk-input min-h-11 tabular-nums" type="number" inputMode="decimal" min={min} max={max} step={step}
      value={draft} disabled={disabled} onChange={(event) => setDraft(event.target.value)}
      onBlur={(event) => commit(event.target.value)}
      onKeyDown={(event) => { if (event.key === "Enter") commit((event.target as HTMLInputElement).value); }} />
  </label>;
}

export function ColourInput({ label, value, onChange, allowNone, disabled }: {
  label: string; value: string | null | undefined; onChange: (value: string | null) => void;
  allowNone?: boolean; disabled?: boolean;
}) {
  const [draft, setDraft] = useState(value ?? "");
  useEffect(() => setDraft(value ?? ""), [value]);
  return <div className="grid gap-1 text-xs font-semibold text-muted">
    <span>{label}</span>
    <div className="flex items-center gap-2">
      <input type="color" aria-label={`${label} picker`} className="h-11 w-11 shrink-0 cursor-pointer rounded-control border border-line bg-panel p-1"
        value={HEX.test(draft) ? draft : "#FFFFFF"} disabled={disabled}
        onChange={(event) => { setDraft(event.target.value.toUpperCase()); onChange(event.target.value.toUpperCase()); }} />
      <input className="desk-input min-h-11 min-w-0 flex-1 code-text uppercase" aria-label={`${label} hex`} value={draft}
        placeholder={allowNone ? t`None` : "#RRGGBB"} maxLength={7} disabled={disabled}
        onChange={(event) => {
          const next = event.target.value.startsWith("#") ? event.target.value : `#${event.target.value}`;
          setDraft(next);
          if (HEX.test(next)) onChange(next.toUpperCase());
        }}
        onBlur={() => { if (!HEX.test(draft)) setDraft(value ?? ""); }} />
      {allowNone && value ? <button type="button" className="desk-button-ghost min-h-11" disabled={disabled}
        onClick={() => onChange(null)}>{t`None`}</button> : null}
    </div>
  </div>;
}

export function SelectInput<T extends string>({ label, value, options, onChange, disabled }: {
  label: string; value: T; options: { value: T; label: string }[]; onChange: (value: T) => void; disabled?: boolean;
}) {
  return <label className="grid gap-1 text-xs font-semibold text-muted">
    <span>{label}</span>
    <select className="desk-input min-h-11" value={value} disabled={disabled}
      onChange={(event) => onChange(event.target.value as T)}>
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  </label>;
}

export function Toggle({ label, checked, onChange, disabled }: {
  label: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean;
}) {
  return <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
    <input type="checkbox" className="h-5 w-5 accent-[rgb(var(--color-accent-ink))]" checked={checked} disabled={disabled}
      onChange={(event) => onChange(event.target.checked)} />
    {label}
  </label>;
}
