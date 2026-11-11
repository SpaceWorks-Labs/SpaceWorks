// Small controls the badge designer's panels share: a titled section, a labelled switch, a number with
// a slider, and a colour choice that always names the colour (never colour alone).
import { t } from "@lingui/core/macro";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { colourLabels } from "./badgeLabels";

export function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return <section aria-labelledby={id} className="grid gap-3">
    <h4 id={id} className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h4>
    {children}
  </section>;
}

export function SwitchLine({ label, hint, checked, disabled, onChange }: { label: string; hint?: string; checked: boolean;
  disabled?: boolean; onChange: (checked: boolean) => void }) {
  return <label className={`flex min-h-11 items-center justify-between gap-3 ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}>
    <span className="min-w-0">
      <span className={`block text-sm ${disabled ? "text-muted" : "text-ink"}`}>{label}</span>
      {hint ? <span className="block text-xs text-muted">{hint}</span> : null}
    </span>
    <input type="checkbox" role="switch" className="h-5 w-5 shrink-0 accent-accent" checked={checked} disabled={disabled}
      onChange={(event) => onChange(event.target.checked)} />
  </label>;
}

export function NumberSlider({ label, unit, min, max, step, value, onChange }: { label: string; unit: string; min: number;
  max: number; step: number; value: number; onChange: (value: number) => void }) {
  const id = useId();
  return <div className="grid gap-1.5">
    <div className="flex items-center justify-between gap-2">
      <label htmlFor={id} className="text-xs text-muted">{label}</label>
      <span className="flex items-center gap-1">
        <input aria-label={`${label} (${unit})`} type="number" min={min} max={max} step={step} value={value}
          className="desk-input min-h-9 w-20 px-2 text-right tabular-nums" onChange={(event) => onChange(Number(event.target.value))} />
        <span className="text-xs text-muted">{unit}</span>
      </span>
    </div>
    <input id={id} type="range" min={min} max={max} step={step} value={value} className="w-full accent-accent"
      onChange={(event) => onChange(Number(event.target.value))} />
  </div>;
}

export function SwatchGroup<T extends string>({ label, value, options, colourOf, onChange }: { label: string; value: T;
  options: readonly T[]; colourOf: (key: T) => string | null; onChange: (key: T) => void }) {
  const names = colourLabels();
  return <div className="grid gap-1.5">
    <p className="text-sm font-semibold text-ink">{label}</p>
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((key) => {
        const colour = colourOf(key);
        const active = key === value;
        return <button key={key} type="button" role="radio" aria-checked={active} onClick={() => onChange(key)}
          className={`inline-flex min-h-11 items-center gap-1.5 rounded-control border px-2.5 text-xs font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${active ? "border-outline bg-surface shadow-[inset_0_0_0_1px_var(--color-outline)]" : "border-line hover:bg-surface"}`}>
          {colour ? <span aria-hidden="true" className="size-4 shrink-0 rounded-full border border-line" style={{ background: colour }} /> : null}
          {names[key] ?? key}
        </button>;
      })}
    </div>
  </div>;
}

/** A millimetre value typed freely and applied on blur or Enter, so typing "1" on the way to "120" never clamps. */
export function CommitNumber({ label, value, min, max, step, onCommit }: { label: string; value: number; min: number; max: number;
  step: number; onCommit: (value: number) => void }) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const commit = () => {
    const number = Number(draft);
    if (Number.isFinite(number) && draft.trim() && number !== value) onCommit(Math.min(max, Math.max(min, number)));
    else setDraft(String(value));
  };
  return <label className="grid gap-1 text-xs font-semibold text-muted"><span>{label}</span>
    <input className="desk-input min-h-11 tabular-nums" type="number" inputMode="decimal" min={min} max={max} step={step} value={draft}
      onChange={(event) => setDraft(event.target.value)} onBlur={commit}
      onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); commit(); } }} /></label>;
}

/** Measures the space and hands the card the largest scale that fits (1.6–6 px per mm). */
export function FitArea({ widthMm, heightMm, children }: { widthMm: number; heightMm: number; children: (pxPerMm: number) => ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") { setBox({ width: 480, height: 480 }); return; }
    const observer = new ResizeObserver(([entry]) => { if (entry) setBox({ width: entry.contentRect.width, height: entry.contentRect.height }); });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const fit = box.width ? Math.min((box.width - 40) / widthMm, (Math.max(box.height, 320) - 40) / heightMm) : 0;
  const pxPerMm = Math.min(6, Math.max(1.6, fit || 3));
  return <div ref={ref} aria-label={t`Badge drawn to scale`} role="group"
    className="grid min-h-[380px] flex-1 place-items-center overflow-auto bg-surface p-5"
    style={{ backgroundImage: "radial-gradient(circle, rgb(20 44 42 / 14%) 1px, transparent 1px)", backgroundSize: "16px 16px" }}>
    {box.width ? children(pxPerMm) : null}
  </div>;
}
